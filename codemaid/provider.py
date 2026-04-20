"""
CODEMAID Providers — Unified interface for LLM APIs.
"""
import json
import os
from collections.abc import Callable
from typing import Any

import requests


class BaseProvider:
    """Base class for LLM Providers."""
    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key

    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> dict[str, Any]:
        """Send messages and tools to the LLM. Returns the response message dict."""
        raise NotImplementedError

    def _mask_key(self, key: str | None) -> str:
        """Mask an API key for safe display."""
        if not key or len(key) < 8:
            return "****"
        return f"{key[:4]}****{key[-4:]}"


class OllamaProvider(BaseProvider):
    """Provider for local Ollama models."""
    def __init__(self, model: str, host: str | None = None, **kwargs: Any) -> None:
        super().__init__(model)
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def _prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert messages to Ollama's expected format.

        The agent stores tool_call arguments as JSON strings (OpenAI format),
        but Ollama requires arguments to be a dict/object. This converts them
        back before sending. Ollama also does not accept the 'tool_call_id'
        field in tool-result messages.
        """
        prepared = []
        for m in messages:
            msg = dict(m)
            # Fix assistant messages with tool_calls: arguments must be dicts
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                fixed_calls = []
                for tc in msg["tool_calls"]:
                    tc = dict(tc)
                    fn = dict(tc.get("function", {}))
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            fn["arguments"] = json.loads(args)
                        except (json.JSONDecodeError, TypeError):
                            fn["arguments"] = {}
                    tc["function"] = fn
                    fixed_calls.append(tc)
                msg["tool_calls"] = fixed_calls
            # Fix tool-result messages: remove tool_call_id (Ollama doesn't use it)
            if msg.get("role") == "tool":
                msg.pop("tool_call_id", None)
            prepared.append(msg)
        return prepared

    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": self._prepare_messages(messages),
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=(10, 300),
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            return {"role": "assistant", "content": f"Error: Failed to connect to Ollama at {self.host}. Is it running? ({e})"}

        msg = data.get("message", {})
        content = msg.get("content", "")

        # Handle empty content (common with local models)
        if not content:
            # Retry once with the same timeout (slow local models need it)
            try:
                resp_retry = requests.post(
                    f"{self.host}/api/chat",
                    json=payload,
                    timeout=(10, 300),
                )
                resp_retry.raise_for_status()
                data_retry = resp_retry.json()
                msg = data_retry.get("message", {})
                content = msg.get("content", "")
            except (requests.exceptions.RequestException, json.JSONDecodeError):
                pass

        # If still empty after retry, return a graceful fallback
        if not content and "tool_calls" not in msg:
            return {"role": "assistant", "content": "..."}

        # Normalize tool_calls to match the format expected by Agent
        if "tool_calls" in msg and isinstance(msg["tool_calls"], list):
            normalized = []
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                if isinstance(fn.get("arguments"), str):
                    normalized.append(tc)
                elif isinstance(fn.get("arguments"), dict):
                    fn["arguments"] = json.dumps(fn["arguments"])
                    normalized.append(tc)
                else:
                    fn["arguments"] = "{}"
                    normalized.append(tc)
            msg["tool_calls"] = normalized
        return msg

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Stream response from Ollama, calling on_chunk(text) for each token.

        Returns the full response message dict when done.
        """
        payload = {
            "model": self.model,
            "messages": self._prepare_messages(messages),
            "stream": True,
            "think":  True,
        }
        if tools:
            payload["tools"] = tools

        content_parts = []
        think_parts   = []
        tool_calls_raw = []

        try:
            resp = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=(10, None),
                stream=True,
            )
            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = chunk.get("message", {})

                # Accumulate thinking tokens separately (wrap once at end)
                think = msg.get("thinking", "")
                if think:
                    think_parts.append(think)
                    if on_chunk:
                        on_chunk(think)

                token = msg.get("content", "")
                if token:
                    content_parts.append(token)
                    if on_chunk:
                        on_chunk(token)

                # Collect tool calls if present
                if "tool_calls" in msg and msg["tool_calls"]:
                    for tc in msg["tool_calls"]:
                        tool_calls_raw.append(tc)

                if chunk.get("done", False):
                    break

        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            return {"role": "assistant", "content": f"Streaming error: {e}"}

        text_body    = "".join(content_parts)
        full_content = (f"<think>{''.join(think_parts)}</think>{text_body}"
                        if think_parts else text_body)
        result_msg = {"role": "assistant", "content": full_content}

        # Normalize tool_calls
        if tool_calls_raw:
            normalized = []
            for tc in tool_calls_raw:
                fn = tc.get("function", {})
                if isinstance(fn.get("arguments"), dict):
                    fn["arguments"] = json.dumps(fn["arguments"])
                normalized.append(tc)
            result_msg["tool_calls"] = normalized

        return result_msg


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI-compatible APIs (OpenAI, DeepSeek, Qwen, etc.)."""
    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> dict[str, Any]:
        if not self.api_key:
            return {"role": "assistant", "content": "Error: API Key missing. Set OPENAI_API_KEY."}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t["function"]} for t in tools]

        try:
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            return message
        except requests.exceptions.RequestException as e:
            return {"role": "assistant", "content": f"OpenAI API Error: {str(e)}"}

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            return {"role": "assistant", "content": "Error: API Key missing."}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            payload["tools"] = [{"type": "function", "function": t["function"]} for t in tools]
        try:
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            resp = requests.post(f"{base_url}/chat/completions", headers=headers,
                                 json=payload, timeout=(10, None), stream=True)
            resp.raise_for_status()
            content_parts: list[str] = []
            tool_calls_acc: dict[int, dict] = {}
            for raw in resp.iter_lines():
                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                token = delta.get("content") or ""
                if token:
                    content_parts.append(token)
                    if on_chunk:
                        on_chunk(token)
                for tc in delta.get("tool_calls", []):
                    idx = tc.get("index", 0)
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": "", "type": "function",
                                               "function": {"name": "", "arguments": ""}}
                    if tc.get("id"):
                        tool_calls_acc[idx]["id"] = tc["id"]
                    fn = tc.get("function", {})
                    tool_calls_acc[idx]["function"]["name"] += fn.get("name", "")
                    tool_calls_acc[idx]["function"]["arguments"] += fn.get("arguments", "")
            result: dict[str, Any] = {"role": "assistant", "content": "".join(content_parts) or None}
            if tool_calls_acc:
                result["tool_calls"] = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
            return result
        except requests.exceptions.RequestException as e:
            return {"role": "assistant", "content": f"OpenAI streaming error: {e}"}


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic (Claude)."""

    def _convert_tool_result(self, message: dict[str, Any]) -> dict[str, Any]:
        """Convert an OpenAI tool-result message to an Anthropic tool_result content block.

        OpenAI: {"role": "tool", "tool_call_id": "...", "content": "..."}
        Anthropic: {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "...", "content": "..."}]}
        """
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": message["tool_call_id"],
                "content": message["content"],
            }]
        }

    def _convert_assistant_with_tools(self, message: dict[str, Any]) -> dict[str, Any]:
        """Convert an OpenAI assistant-message-with-tool_calls to Anthropic content blocks.

        OpenAI: {"role": "assistant", "content": "...", "tool_calls": [...]}
        Anthropic: {"role": "assistant", "content": [{"type": "text", ...}, {"type": "tool_use", ...}]}
        """
        blocks = []
        if message.get("content"):
            blocks.append({"type": "text", "text": message["content"]})
        for tc in message["tool_calls"]:
            fn = tc.get("function", {})
            try:
                input_obj = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
            except (json.JSONDecodeError, TypeError):
                input_obj = {}
            blocks.append({
                "type": "tool_use",
                "id": tc.get("id", "unknown"),
                "name": fn["name"],
                "input": input_obj,
            })
        return {"role": "assistant", "content": blocks}

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert a full list of OpenAI-format messages to Anthropic format."""
        converted = []
        for m in messages:
            if m["role"] == "tool":
                converted.append(self._convert_tool_result(m))
            elif m["role"] == "assistant" and "tool_calls" in m:
                converted.append(self._convert_assistant_with_tools(m))
            else:
                converted.append(m)
        return converted

    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> dict[str, Any]:
        if not self.api_key:
            return {"role": "assistant", "content": "Error: API Key missing. Set ANTHROPIC_API_KEY."}

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        system_msg = "You are CODEMAID, an expert AI coding assistant."
        filtered_messages = [m for m in messages if m["role"] != "system"]
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]

        # Convert messages to Anthropic format
        converted_messages = self._convert_messages(filtered_messages)

        payload = {
            "model": self.model,
            "system": system_msg,
            "messages": converted_messages,
            "max_tokens": 4096,
        }
        if tools:
            payload["tools"] = [{
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"]
            } for t in tools]

        try:
            resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()

            content_blocks = data.get("content", [])
            text_content = []
            tool_calls = []

            for block in content_blocks:
                if block.get("type") == "text":
                    text_content.append(block["text"])
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block.get("input", {}))
                        }
                    })

            return {
                "role": "assistant",
                "content": "\n".join(text_content) if text_content else None,
                **({"tool_calls": tool_calls} if tool_calls else {})
            }
        except requests.exceptions.RequestException as e:
            return {"role": "assistant", "content": f"Anthropic API Error: {str(e)}"}

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            return {"role": "assistant", "content": "Error: API Key missing."}
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        system_msg = "You are CODEMAID, an expert AI coding assistant."
        filtered = [m for m in messages if m["role"] != "system"]
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
        payload: dict[str, Any] = {
            "model": self.model,
            "system": system_msg,
            "messages": self._convert_messages(filtered),
            "max_tokens": 4096,
            "stream": True,
        }
        if tools:
            payload["tools"] = [{
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"],
            } for t in tools]
        try:
            resp = requests.post("https://api.anthropic.com/v1/messages",
                                 headers=headers, json=payload, timeout=(10, None), stream=True)
            resp.raise_for_status()
            content_parts: list[str] = []
            tool_calls: list[dict] = []
            current_tool: dict | None = None
            for raw in resp.iter_lines():
                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if not line.startswith("data: "):
                    continue
                try:
                    ev = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                etype = ev.get("type", "")
                if etype == "content_block_start":
                    blk = ev.get("content_block", {})
                    if blk.get("type") == "tool_use":
                        current_tool = {"id": blk["id"], "type": "function",
                                        "function": {"name": blk["name"], "arguments": ""}}
                elif etype == "content_block_delta":
                    delta = ev.get("delta", {})
                    if delta.get("type") == "text_delta":
                        token = delta.get("text", "")
                        content_parts.append(token)
                        if on_chunk and token:
                            on_chunk(token)
                    elif delta.get("type") == "input_json_delta" and current_tool:
                        current_tool["function"]["arguments"] += delta.get("partial_json", "")
                elif etype == "content_block_stop":
                    if current_tool:
                        tool_calls.append(current_tool)
                        current_tool = None
                elif etype == "message_stop":
                    break
            result: dict[str, Any] = {"role": "assistant", "content": "".join(content_parts) or None}
            if tool_calls:
                result["tool_calls"] = tool_calls
            return result
        except requests.exceptions.RequestException as e:
            return {"role": "assistant", "content": f"Anthropic streaming error: {e}"}


class GroqProvider(OpenAIProvider):
    """Provider for Groq (OpenAI-compatible fast inference)."""
    def __init__(self, model: str, api_key: str | None = None, **_: Any) -> None:
        super().__init__(model, api_key=api_key or os.environ.get("GROQ_API_KEY"))

    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> dict[str, Any]:
        os.environ.setdefault("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
        old = os.environ.get("OPENAI_BASE_URL")
        os.environ["OPENAI_BASE_URL"] = "https://api.groq.com/openai/v1"
        result = super().chat(messages, tools)
        if old:
            os.environ["OPENAI_BASE_URL"] = old
        return result

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        os.environ["OPENAI_BASE_URL"] = "https://api.groq.com/openai/v1"
        return super().chat_stream(messages, tools, on_chunk)


class GeminiProvider(BaseProvider):
    """Provider for Google Gemini (generativelanguage API)."""
    BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, model: str, api_key: str | None = None, **_: Any) -> None:
        super().__init__(model, api_key=api_key or os.environ.get("GEMINI_API_KEY"))

    def _to_gemini_messages(self, messages: list[dict[str, Any]]) -> tuple[str, list[dict]]:
        """Convert OpenAI-format messages → (system_instruction, gemini_contents)."""
        system_parts: list[str] = []
        contents: list[dict] = []
        for m in messages:
            role = m["role"]
            content = m.get("content") or ""
            if role == "system":
                system_parts.append(content)
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                if "tool_calls" in m:
                    parts = []
                    if content:
                        parts.append({"text": content})
                    for tc in m["tool_calls"]:
                        fn = tc.get("function", {})
                        try:
                            args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                        parts.append({"functionCall": {"name": fn["name"], "args": args}})
                    contents.append({"role": "model", "parts": parts})
                else:
                    contents.append({"role": "model", "parts": [{"text": content}]})
            elif role == "tool":
                try:
                    result_obj = json.loads(m["content"]) if isinstance(m["content"], str) else m["content"]
                except (json.JSONDecodeError, TypeError):
                    result_obj = {"result": m["content"]}
                contents.append({"role": "user", "parts": [
                    {"functionResponse": {"name": "tool", "response": result_obj}}
                ]})
        return "\n".join(system_parts), contents

    def _to_gemini_tools(self, tools: list[dict]) -> list[dict]:
        return [{"functionDeclarations": [
            {"name": t["function"]["name"],
             "description": t["function"]["description"],
             "parameters": t["function"]["parameters"]}
            for t in tools
        ]}]

    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> dict[str, Any]:
        if not self.api_key:
            return {"role": "assistant", "content": "Error: GEMINI_API_KEY not set."}
        system_text, contents = self._to_gemini_messages(messages)
        payload: dict[str, Any] = {"contents": contents}
        if system_text:
            payload["system_instruction"] = {"parts": [{"text": system_text}]}
        if tools:
            payload["tools"] = self._to_gemini_tools(tools)
        try:
            url = f"{self.BASE}/{self.model}:generateContent?key={self.api_key}"
            resp = requests.post(url, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            candidate = data.get("candidates", [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])
            text_parts, tool_calls = [], []
            for p in parts:
                if "text" in p:
                    text_parts.append(p["text"])
                elif "functionCall" in p:
                    fc = p["functionCall"]
                    tool_calls.append({
                        "id": f"gemini_{fc['name']}",
                        "type": "function",
                        "function": {"name": fc["name"], "arguments": json.dumps(fc.get("args", {}))},
                    })
            result: dict[str, Any] = {"role": "assistant", "content": "\n".join(text_parts) or None}
            if tool_calls:
                result["tool_calls"] = tool_calls
            return result
        except requests.exceptions.RequestException as e:
            return {"role": "assistant", "content": f"Gemini API Error: {e}"}

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            return {"role": "assistant", "content": "Error: GEMINI_API_KEY not set."}
        system_text, contents = self._to_gemini_messages(messages)
        payload: dict[str, Any] = {"contents": contents}
        if system_text:
            payload["system_instruction"] = {"parts": [{"text": system_text}]}
        if tools:
            payload["tools"] = self._to_gemini_tools(tools)
        try:
            url = f"{self.BASE}/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
            resp = requests.post(url, json=payload, timeout=(10, None), stream=True)
            resp.raise_for_status()
            content_parts: list[str] = []
            tool_calls: list[dict] = []
            for raw in resp.iter_lines():
                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if not line.startswith("data: "):
                    continue
                try:
                    ev = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                for p in ev.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    if "text" in p:
                        token = p["text"]
                        content_parts.append(token)
                        if on_chunk and token:
                            on_chunk(token)
                    elif "functionCall" in p:
                        fc = p["functionCall"]
                        tool_calls.append({
                            "id": f"gemini_{fc['name']}",
                            "type": "function",
                            "function": {"name": fc["name"], "arguments": json.dumps(fc.get("args", {}))},
                        })
            result: dict[str, Any] = {"role": "assistant", "content": "".join(content_parts) or None}
            if tool_calls:
                result["tool_calls"] = tool_calls
            return result
        except requests.exceptions.RequestException as e:
            return {"role": "assistant", "content": f"Gemini streaming error: {e}"}


class OpenWebUIProvider(OpenAIProvider):
    """Provider for OpenWebUI (OpenAI-compatible local API)."""
    def __init__(self, model: str, host: str | None = None,
                 api_key: str | None = None, **_: Any) -> None:
        super().__init__(model, api_key=api_key or os.environ.get("OPENWEBUI_API_KEY", ""))
        self._host = (host or os.environ.get("OPENWEBUI_HOST", "http://localhost:3000")).rstrip("/")

    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> dict[str, Any]:
        os.environ["OPENAI_BASE_URL"] = f"{self._host}/api"
        return super().chat(messages, tools)

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        os.environ["OPENAI_BASE_URL"] = f"{self._host}/api"
        return super().chat_stream(messages, tools, on_chunk)


def get_provider(name: str, model: str, **kwargs: Any) -> BaseProvider:
    """Factory function to get the correct provider instance."""
    name = name.lower()
    if name == "ollama":
        return OllamaProvider(model, **kwargs)
    elif name == "openai":
        return OpenAIProvider(model, api_key=kwargs.get("api_key") or os.environ.get("OPENAI_API_KEY"))
    elif name == "anthropic":
        return AnthropicProvider(model, api_key=kwargs.get("api_key") or os.environ.get("ANTHROPIC_API_KEY"))
    elif name == "groq":
        return GroqProvider(model, api_key=kwargs.get("api_key") or os.environ.get("GROQ_API_KEY"))
    elif name == "gemini":
        return GeminiProvider(model, api_key=kwargs.get("api_key") or os.environ.get("GEMINI_API_KEY"))
    elif name in ("openwebui", "open-webui"):
        return OpenWebUIProvider(model, host=kwargs.get("host") or os.environ.get("OPENWEBUI_HOST"),
                                 api_key=kwargs.get("api_key"))
    else:
        raise ValueError(f"Unknown provider: {name}. Options: ollama, openai, anthropic, groq, gemini, openwebui")
