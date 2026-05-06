"""
CODEMAID Default Settings — Centralized configuration for models and providers.
"""

# Default provider and model when nothing is configured
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "qwen2.5:14b"  # Stable, widely used local model

# Default models per provider
PROVIDER_DEFAULTS = {
    "ollama":    "qwen2.5:14b",
    "openai":    "gpt-4o",
    "anthropic": "claude-3-5-sonnet-latest",
    "groq":      "llama-3.3-70b-versatile",
    "gemini":    "gemini-1.5-flash",
    "openwebui": "llama3.2",
}

# Environment variables for API keys
PROVIDER_ENV_VARS = {
    "openai":    "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq":      "GROQ_API_KEY",
    "gemini":    "GEMINI_API_KEY",
}

# Default model cycle list for ^P
DEFAULT_MODEL_CYCLE = ["qwen2.5:14b", "qwen2.5:7b", "llama3.2:3b"]

# Default hosts
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OPENWEBUI_HOST = "http://localhost:3000"
