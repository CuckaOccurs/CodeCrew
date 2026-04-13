# OpenPaws

A beautiful terminal-based AI coding assistant that actually edits files.

## Philosophy

- Terminal AI assistants exist, but most look like they were designed in 1995 or can't actually edit files.
- OpenPaws combines a clean terminal UI with reliable file editing and local LLM support.

## Features

- Rich terminal UI with cat animations
- Intelligent file editing (SEARCH/REPLACE parsing + fuzzy fallback)
- Local LLM support via Ollama
- Non-interactive mode for automation
- Interactive chat with tool calling

## Acknowledgments

OpenPaws was built by studying what works in existing tools:

- **Aider** — The SEARCH/REPLACE edit format and cascading edit strategies (exact → whitespace-flexible → fuzzy)
- **OpenCode** — The clean terminal UI concept and local-first approach
- **Goose** — Agent tool-calling workflows

We built OpenPaws from scratch to be lightweight, beautiful, and reliable. No code was copied.

## Quick Start

### From Source
```bash
cd ~/Projects/tools/OpenPaws
pip install -e . --break-system-packages  # or use a venv
openpaws .                    # Start in current directory
openpaws --model gemma4:latest  # Specific model
```

## Requirements

- Python 3.10+
- Ollama running locally
- Rich for the UI
