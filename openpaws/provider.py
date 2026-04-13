"""
OpenPaws Providers — Unified interface for LLM APIs.
"""
import json
import os
import subprocess
import requests

class BaseProvider:
    """Base class for LLM Providers."""
    def __init__(self, model, api_key=None):
        self.model = model
        self.api_key = api_key

    def chat(self, messages, tools=None):
        """Send messages and tools to the LLM. Returns the response message dict."""
        raise NotImplementedError

    def _mask_key(self, key):
        """Mask an API key for safe display."""
        if not key or len(key) < 8:
            return "****"
        return f"{key[:4]}****{key[-4:]}"


class OllamaProvider(BaseProvider):
    """Provider for local Ollama models."""
    def __init__(self, model, host="http://localhost:11434", **kwargs):
        super().__init__(model)
        self.host = host

    def chat(self, messages, tools=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        resp = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{self.host}/api/chat",
             "-H", "Content-Type: application/json",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=180,
        )

        try:
            data = json.loads(resp.stdout)
            msg = data.get("message", {"role": "assistant", "content": "Error: Empty response from Ollama."})
            # Normalize tool_calls to match the format expected by Agent
            if "tool_calls" in msg and isinstance(msg["tool_calls"], list):
                normalized = []
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    if isinstance(fn.get("arguments"), str):
                        normalized.append(tc)  # Already correct format
                    elif isinstance(fn.get("arguments"), dict):
                        fn["arguments"] = json.dumps(fn["arguments"])
                        normalized.append(tc)
                    else:
                        fn["arguments"] = "{}"
                        normalized.append(tc)
                msg["tool_calls"] = normalized
            return msg
        except (json.JSONDecodeError, TypeError):
            return {"role": "assistant", "content": f"Error: Failed to parse Ollama response. Stdout: {resp.stdout[:500]}"}


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI-compatible APIs (OpenAI, DeepSeek, Qwen, etc.)."""
    def chat(self, messages, tools=None):
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
            resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            return message
        except requests.exceptions.RequestException as e:
            return {"role": "assistant", "content": f"OpenAI API Error: {str(e)}"}


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic (Claude)."""
    def chat(self, messages, tools=None):
        if not self.api_key:
            return {"role": "assistant", "content": "Error: API Key missing. Set ANTHROPIC_API_KEY."}

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2024-01-01",
            "content-type": "application/json"
        }

        system_msg = "You are OpenPaws, an expert AI coding assistant."
        filtered_messages = [m for m in messages if m["role"] != "system"]
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]

        payload = {
            "model": self.model,
            "system": system_msg,
            "messages": filtered_messages,
            "max_tokens": 4096,
        }
        if tools:
            payload["tools"] = [{
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"]
            } for t in tools]

        try:
            resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=180)
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
                "tool_calls": tool_calls if tool_calls else None
            }
        except requests.exceptions.RequestException as e:
            return {"role": "assistant", "content": f"Anthropic API Error: {str(e)}"}


def get_provider(name, model, **kwargs):
    """Factory function to get the correct provider instance."""
    name = name.lower()
    if name == "ollama":
        return OllamaProvider(model, **kwargs)
    elif name == "openai":
        return OpenAIProvider(model, api_key=kwargs.get("api_key") or os.environ.get("OPENAI_API_KEY"))
    elif name == "anthropic":
        return AnthropicProvider(model, api_key=kwargs.get("api_key") or os.environ.get("ANTHROPIC_API_KEY"))
    else:
        raise ValueError(f"Unknown provider: {name}")
