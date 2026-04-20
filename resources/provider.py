"""
CodeMAID Providers — Unified interface for LLM APIs.
"""
import json
import os
import subprocess

# Standard OpenAI-style tool definitions (compatible with Ollama, OpenAI, Anthropic, etc.)
# We import this here to avoid circular dependencies if tools.py imports provider.py later.
from codemaid.tools import TOOLS

class BaseProvider:
    """Base class for LLM Providers."""
    def __init__(self, model, api_key=None):
        self.model = model
        self.api_key = api_key

    def chat(self, messages, tools=None):
        """Send messages and tools to the LLM. Returns the response message dict."""
        raise NotImplementedError

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
            return data.get("message", {"role": "assistant", "content": "Error: Empty response from Ollama."})
        except Exception:
            return {"role": "assistant", "content": f"Error: Failed to parse Ollama response. Stdout: {resp.stdout}"}

class OpenAIProvider(BaseProvider):
    """Provider for OpenAI-compatible APIs (OpenAI, DeepSeek, Qwen, etc.)."""
    def chat(self, messages, tools=None):
        if not self.api_key:
            return {"role": "assistant", "content": "Error: API Key missing. Set OPENAI_API_KEY."}
            
        import requests
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
            # Default to OpenAI, but allow override via env var OPENAI_BASE_URL
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            # Ensure tool_calls are in the format the Agent expects
            if "tool_calls" in message:
                # OpenAI format is usually fine, but we can normalize if needed
                pass
            
            return message
        except Exception as e:
            return {"role": "assistant", "content": f"OpenAI API Error: {str(e)}"}

class AnthropicProvider(BaseProvider):
    """Provider for Anthropic (Claude)."""
    def chat(self, messages, tools=None):
        if not self.api_key:
            return {"role": "assistant", "content": "Error: API Key missing. Set ANTHROPIC_API_KEY."}

        import requests
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Anthropic uses a slightly different message structure (system prompt is separate)
        system_msg = "You are CodeMAID..." 
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
            payload["tools"] = [{"name": t["function"]["name"], "description": t["function"]["description"], "input_schema": t["function"]["parameters"]} for t in tools]

        try:
            resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            
            # Parse tool calls
            content_blocks = data.get("content", [])
            text_content = []
            tool_calls = []
            
            for block in content_blocks:
                if block["type"] == "text":
                    text_content.append(block["text"])
                elif block["type"] == "tool_use":
                    tool_calls.append({
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"])
                        }
                    })
            
            return {
                "role": "assistant",
                "content": "\n".join(text_content) if text_content else None,
                "tool_calls": tool_calls if tool_calls else None
            }
        except Exception as e:
            return {"role": "assistant", "content": f"Anthropic API Error: {str(e)}"}

def get_provider(name, model, **kwargs):
    """Factory function to get the correct provider instance."""
    name = name.lower()
    if name == "ollama":
        return OllamaProvider(model, **kwargs)
    elif name == "openai":
        # Default to env var for API key
        return OpenAIProvider(model, api_key=kwargs.get("api_key") or os.environ.get("OPENAI_API_KEY"))
    elif name == "anthropic":
        # Default to env var for API key
        return AnthropicProvider(model, api_key=kwargs.get("api_key") or os.environ.get("ANTHROPIC_API_KEY"))
    else:
        raise ValueError(f"Unknown provider: {name}")
