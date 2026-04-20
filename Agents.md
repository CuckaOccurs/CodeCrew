# CODEMAID — Core Architecture

**Version:** 4.2.0
**Stack:** Python 3, Rich, Requests, Ollama/OpenAI/Anthropic
**Last Audit:** 2026-04-17
**Audit Score:** 8.7/10 (A-) — Production-ready

---

## What Is CODEMAID?

A **local-first terminal AI coding assistant** with a full agentic tool-use loop. No telemetry, no cloud dependency (works fully offline with Ollama). Users interact via a Rich-powered TUI, and the agent can read/write files, run shell commands (sandboxed), search the web, use git, and remember facts across sessions.

**Run it:** `maid` or `codemaid` or `python -m codemaid`

---

## Architecture Overview

```
┌──────────────────────────────────────────────┐
│  CLI / TUI  (codemaid/cli/)                  │
│  - Raw keypress input loop                    │
│  - Rich terminal rendering                    │
│  - Slash command dispatch                     │
│  - Streaming token display                    │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Agent  (codemaid/agent.py)                  │
│  - Tool-use loop (up to 20 iterations)        │
│  - Parallel tool execution (ThreadPoolExec)  │
│  - Context window management (truncation)    │
│  - Checkpoint / rewind support               │
│  - Auto-commit on file edits (optional)      │
└──────────────────────┬───────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌─────────────────┐     ┌──────────────────────┐
│  Providers       │     │  Tools               │
│  provider.py     │     │  tools/__init__.py   │
│  - Ollama        │     │  - file_tools        │
│  - OpenAI        │     │  - search_tools      │
│  - Anthropic     │     │  - web_tools         │
└─────────────────┘     │  - git_tools         │
                        │  - system_tools      │
                        │  - memory_tools      │
                        └──────────────────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │  Litterbox           │
                        │  litterbox.py        │
                        │  - Denylist mode     │
                        │  - Allowlist mode    │
                        │  - Firejail wrapper  │
                        └──────────────────────┘
```

---

## Module Reference

### `codemaid/agent.py`
The brain. Runs the tool-use loop:
1. Sends messages + tools to the provider
2. Executes tool calls (parallel via `ThreadPoolExecutor`)
3. Feeds results back to the LLM
4. Loops until plain text response or 20 iterations
5. Detects stuck loops, empty responses, and handles gracefully

Key features: `checkpoint()`, `restore_checkpoint()`, `rewind()`, `auto_commit`, `plan_mode`, `litterbox_on`

---

### `codemaid/cli/`
The interface layer.

| File | Role |
|------|------|
| `main.py` | Entry point, raw keypress input loop, TUI rendering, streaming display |
| `commands.py` | Slash command handler (`/help`, `/model`, `/provider`, `/trace`, `/litterbox`, `/focus`, etc.) |
| `config.py` | Theme (THEME dict), console setup, config file loading |

Special input modes:
- `!command` — shell passthrough
- `@filename` — inject file contents into prompt
- `/slash` — slash commands

---

### `codemaid/provider.py`
Unified LLM interface. Three providers:

| Provider | Class | Notes |
|----------|-------|-------|
| Ollama | `OllamaProvider` | Local, default. Handles streaming. Normalizes Ollama's dict-format tool args to JSON strings |
| OpenAI | `OpenAIProvider` | OpenAI-compatible APIs (DeepSeek, Qwen API, etc.) |
| Anthropic | `AnthropicProvider` | Claude. Converts OpenAI-format messages to Anthropic content blocks |

Factory: `get_provider(name, model, **kwargs)`

---

### `codemaid/tools/`
22 tools across 6 modules. See `tools/Agents.md` for full list.

| Module | Tools |
|--------|-------|
| `file_tools.py` | read_file, write_file, edit_file, list_directory, delete_file |
| `search_tools.py` | search_files, grep_files, find_files |
| `web_tools.py` | web_search, fetch_url, scrape_page |
| `git_tools.py` | git_status, git_diff, git_log, git_commit, git_add |
| `system_tools.py` | run_command (sandboxed) |
| `memory_tools.py` | remember_fact, recall_facts, forget_fact |

---

### `codemaid/litterbox.py`
Three-layer command safety system:
1. **Denylist** (default): blocks known-dangerous patterns (rm -rf /, curl | sh, eval, reverse shells, credential harvest)
2. **Allowlist** mode: only permits patterns in `ALLOWED_COMMANDS`
3. **Firejail** wrapper: optional container isolation if firejail is installed

---

### `codemaid/memory.py`
Persistent JSON memory. Stores facts in `.agents/codemaid_memory.json` in the working directory. Injects the last 10 facts into the system prompt on each session start.

---

### `codemaid/gateway.py`
Multi-platform messaging bridge. Connects CODEMAID to Telegram, Discord, Slack, Signal. Config stored at `~/.config/codemaid/gateway_config.json`. Run with `codemaid gateway start`.

---

### `codemaid/skills_loader.py`
Loads skill files (Markdown prompt fragments) from `.codemaid/skills/` and assembles the system prompt. Allows extending the agent's persona/behavior without code changes.

---

### `codemaid/onboarder.py`
Interactive onboarding wizard for first-time setup (provider selection, API keys, model choice).

---

### `codemaid/cat.py`
ASCII cat banner and random cat jokes for the TUI.

---

## Data Directories

### `.codemaid/` (runtime data)
| Folder | Contents |
|--------|---------|
| `agents/` | `agent.md` (system prompt), `instructions.md` |
| `conversations/` | `chunk_001.md`, `contexts.md` — conversation history |
| `memory/` | `active_session.md`, `preferences.md`, `project_state.md`, `deletion_queue.md` |
| `scripts/` | Shell scripts (see `README.md`) |
| `skills/` | Skill prompt fragments (see `README.md`) |
| `tools/` | `memory-manager.sh`, tool helpers |
| `SafeToDelete/` | Files staged for cleanup |

---

## Supporting Directories

| Folder | Purpose |
|--------|---------|
| `Audits-and-Edits/` | Previous audit reports, stress tests, edit logs |
| `BrainStormingSuggestions/` | UI screenshots and feature brainstorm |
| `Resources/` | Old builds, instructions, archived versions |
| `Setup-HowTo-Manual/` | HTML setup guide (`index.html`) |
| `tests/` | pytest test suite (78 tests, 100% pass) |
| `venv/` | Python virtual environment |

---

## Security Model

| Layer | Mechanism |
|-------|---------|
| Command filtering | Litterbox denylist/allowlist |
| Path confinement | `_check_confinement()` in tools/common.py |
| Container isolation | Optional Firejail wrapping |
| Sensitive tool confirmation | CLI prompts user Y/N for sudo/rm -rf etc. |
| Token storage warning | `gateway.py` warns about plaintext token storage |

---

## Sub-level Agents.md Files

- `codemaid/Agents.md` — Python package modules
- `codemaid/tools/Agents.md` — Tool definitions (all 22 tools)
- `codemaid/cli/Agents.md` — CLI/TUI layer
- `.codemaid/Agents.md` — Runtime data directories
