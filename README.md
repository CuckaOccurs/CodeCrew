# CodeMAID

<p align="center">
  <img src="assets/mascot.png" alt="CodeMAID mascot" width="480"/>
</p>

A local-first terminal AI coding assistant with a full agentic loop. Runs fully offline with Ollama. Edits files, runs commands, searches the web, uses git — all from a clean hacker-grade terminal UI.

## Philosophy

Most terminal AI tools are ugly, cloud-dependent, or can't reliably modify files. CodeMAID is built differently:

- **Local-first** — works fully offline with Ollama. No telemetry, no cloud required.
- **Actually edits files** — SEARCH/REPLACE with exact → fuzzy fallback, not just suggestions.
- **Clean TUI** — streaming output, Knight Rider spinner, color-coded vault status bar.
- **Agentic** — full tool-use loop with parallel tool execution, not just chatting.

## Features

- Rich terminal UI with real-time streaming token display
- Multi-provider: Ollama (local), OpenAI-compatible APIs, Anthropic/Claude
- Intelligent file editing with cascading fallback strategies
- Shell command execution with 3-layer safety system (Vault)
- Web search and page scraping
- Git integration — status, diff, log, add, commit
- Persistent memory across sessions
- Session logging, checkpoints, and rewind
- Skills system — extend agent behavior via plain Markdown files
- Gateway mode — connect to Telegram, Discord, Slack, Signal
- Prompt guard — detects and flags suspicious prompt injection
- Slash commands, `!shell` passthrough, `@file` injection

## Quick Start

```bash
git clone https://github.com/your-username/codemaid.git
cd codemaid
pip install -e .
maid .                        # start in current directory
maid --model qwen3:14b        # specific model
maid --provider anthropic     # use Claude
```

### Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally (for local/offline mode)
- `rich` — installed automatically via pip

## Usage

```
maid [dir]                    # start in directory (default: current)
maid --provider ollama        # local Ollama (default)
maid --provider anthropic     # Anthropic/Claude API
maid --provider openai        # OpenAI-compatible API
maid --model qwen3:14b        # override model
maid -p "fix the tests"       # non-interactive one-shot mode
```

### Key Bindings

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Tab` | Toggle shell / chat mode |
| `Ctrl+P` | Cycle model |
| `Ctrl+S` | Toggle sudo mode |
| `Ctrl+D` | Toggle dry run |
| `Ctrl+T` | Toggle thinking display |
| `Ctrl+G` | Toggle prompt guard |
| `Ctrl+O` | Expand / collapse tool call detail |
| `ESC` | Interrupt AI / clear input |

### Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Command list |
| `/persona [name]` | Show or switch MOP persona |
| `/model [name]` | Show or switch model |
| `/provider [name]` | Show or switch provider |
| `/focus <pattern>` | Deep codebase search |
| `/grep <pattern>` | Grep files |
| `/plan` | Toggle plan mode |
| `/vault` | Toggle command vault |
| `/checkpoint` | Save checkpoint |
| `/restore [n]` | Restore checkpoint |
| `/rewind [n]` | Step back N turns |
| `/compress` | Trim conversation history |
| `/copy` | Copy last response to clipboard |
| `/stats` | Session statistics |
| `/clear` | Clear conversation |
| `/trace` | Toggle trace mode |
| `/exit` | Quit |

## Architecture

```
┌─────────────────────────────────────┐
│  CLI / TUI  (codemaid/cli/)         │
│  Raw keypress loop · Rich rendering │
│  Slash commands · Streaming display │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  Agent  (codemaid/agent.py)         │
│  Tool-use loop · Parallel exec      │
│  Checkpoint / rewind · Plan mode    │
└────────────┬──────────────┬─────────┘
             │              │
             ▼              ▼
    ┌──────────────┐  ┌────────────────────┐
    │  Providers   │  │  Tools             │
    │  Ollama      │  │  file · search     │
    │  OpenAI      │  │  web · git         │
    │  Anthropic   │  │  system · memory   │
    └──────────────┘  └────────────────────┘
                               │
                               ▼
                      ┌────────────────┐
                      │  Vault         │
                      │  Denylist mode │
                      │  Allowlist     │
                      │  Firejail opt. │
                      └────────────────┘
```

Full technical reference in [MOP.md](MOP.md).

## Safety

CodeMAID sandboxes all shell commands through the Vault system:

- **Denylist mode** (default) — blocks known-dangerous patterns: `rm -rf /`, `curl | sh`, reverse shells, credential harvesting
- **Allowlist mode** — only permits explicitly approved command patterns
- **Firejail** — optional container isolation if installed
- **Sudo mode** — explicit toggle required, shown in status bar

## Acknowledgments

Built by studying what works in the ecosystem:

- **Aider** — SEARCH/REPLACE edit format and cascading edit strategies (exact → whitespace-flexible → fuzzy)
- **OpenCode** — clean terminal UI concept and local-first philosophy
- **Goose** — agent tool-calling workflows

Developed in close collaboration with **Claude** (the AI, not the CLI — though also the CLI).

Built from scratch. No code copied.

## License

MIT
