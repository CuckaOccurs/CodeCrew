# codemaid/cli/ — CLI / TUI Layer

**Path:** `codemaid/cli/`
**Last Audit:** 2026-04-17

---

## Overview

The terminal user interface and command handling layer. Built with Python's `termios`/`tty` for raw keypress capture and `rich` for all rendering. Handles the full input loop, rendering pipeline, slash commands, and special input modes.

---

## Files

### `main.py` — Entry Point & Input Loop

**Entry:** `main()` → called by `codemaid` CLI command

**Subcommands:**
| Command | Action |
|---------|--------|
| `codemaid terminal [dir]` | Launch TUI (default) |
| `codemaid onboard` | Run interactive setup wizard |
| `codemaid gateway start/setup/stop` | Manage messaging gateway |

**Input Loop Modes:**
| Prefix | Behavior |
|--------|---------|
| `/command` | Slash command — dispatched to `commands.py` |
| `!shell cmd` | Direct shell passthrough (subprocess) |
| `@filename prompt` | Inject file contents into prompt |
| plain text | AI chat via `agent.chat()` |

**TUI Features:**
- Raw keypress capture (`termios.setcbreak`)
- Two-row footer: input line + status bar
- Live streaming: `on_chunk` callback updates "thinking..." to the last 80 tokens of the stream
- Sensitive command confirmation modal (Y/N prompt for sudo, rm -rf, etc.)
- Thread-safe draw lock (`_draw_lock`)
- Status bar shows: working dir, litterbox state, model name

---

### `commands.py` — Slash Command Handlers

`handle_slash_command(cmd, arg, state)` — returns `"exit"`, `"continue"`, or `None`

**Available Slash Commands:**

| Command | Action |
|---------|--------|
| `/exit` `/quit` `/q` | Exit CodeMAID |
| `/help` | Show help table |
| `/cat` | Random cat joke |
| `/clear` | Clear history and agent context |
| `/trace` | Toggle LLM trace output |
| `/plan` | Toggle plan mode (forces edit_plan before edits) |
| `/litterbox` | Toggle command sandboxing on/off |
| `/litterbox allowlist` | Switch to allowlist mode |
| `/litterbox denylist` | Switch to denylist mode |
| `/model <name>` | Switch LLM model |
| `/provider <name>` | Switch provider (ollama/openai/anthropic) |
| `/focus <pattern>` | Run a codebase search directly |
| `/rewind [n]` | Undo last N conversation turns |
| `/checkpoint` | Save conversation snapshot |
| `/restore [n]` | Restore from checkpoint |
| `/autocommit` | Toggle auto git commit after file edits |
| `/memory` | Show/clear persistent memory |
| `/skills` | List loaded skills |
| `/session` | Show session stats (uptime, message count) |

State dict passed to each handler contains: `history`, `agent`, `work_dir`, `litterbox_on`, `provider_name`, `session_start`, `host_url`, `api_key`, `add_fn`, `draw_fn`, `render_fn`, `execute_tool`, `TOOLS`, `THEME`, `get_provider`

---

### `config.py` — Theme & Configuration

**THEME dict** — color palette (hex values) for the TUI:
- Keys: `blue`, `red`, `green`, `dim`, `white`, `brown`, etc.

**`load_config()`** — reads `~/.config/codemaid/config.json`
Config keys: `provider`, `model`, `api_key`

**`console`** — shared Rich `Console` instance

**`_render(renderable)`** — converts Rich renderable to ANSI string (for history buffer)

**`_build_help_table()`** — builds the `/help` Rich table

---

### `__init__.py`
Package init — exports `main` for the CLI entry point.
