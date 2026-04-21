# codemaid/cli/ — CLI / TUI Layer

**Path:** `codemaid/cli/`

---

## Overview

Terminal user interface and command handling. Built with Python `termios`/`tty` for raw keypress capture and `rich` for rendering. Handles the full input loop, rendering pipeline, slash commands, and special input modes.

---

## Files

### `main.py` — Entry Point & Input Loop

**Subcommands:**

| Command | Action |
|---------|--------|
| `codemaid [dir]` | Launch TUI (default) |
| `codemaid terminal [dir]` | Launch TUI explicitly |
| `codemaid onboard` | Run interactive setup wizard |
| `codemaid gateway start/setup/stop` | Manage messaging gateway |

**Input Modes:**

| Prefix | Behavior |
|--------|---------|
| `/command` | Slash command → `commands.py` |
| `!cmd` | Direct shell passthrough |
| `@filename [text]` | Inject file contents into prompt |
| plain text | AI chat via `agent.chat()` |

**TUI Layout:**
- Row 1: header bar (persona, load indicators, clock) — pinned
- Rows 2–N: scrolling history area
- Separator line (muted)
- Input prompt (❯)
- Vault bar (color-coded by state)
- Status bar (dir · vault · model · mode · stats)

**Key features:**
- Raw keypress capture (`termios.setcbreak`)
- `\033[3A` cursor-up for scroll-proof input line positioning
- Live streaming via `on_chunk` callback
- Thread-safe draw lock (`_draw_lock`)
- Knight Rider animation on separator while thinking

**Keybinds:**

| Key | Action |
|-----|--------|
| Enter | Send / confirm |
| Backspace | Delete character |
| Ctrl+C | Cancel |
| Ctrl+D | Finish multi-line edit |
| Ctrl+S | One-off sudo bypass |

---

### `commands.py` — Slash Command Handlers

`handle_slash_command(cmd, arg, state)` → `"exit"` · `"continue"` · `None`

**Commands:**

| Command | Action |
|---------|--------|
| `/exit` `/quit` `/q` | Exit CodeMAID |
| `/help` | Show command reference |
| `/cat` | Random cat joke |
| `/clear` | Clear history and agent context |
| `/trace` | Toggle LLM trace output |
| `/plan` | Toggle plan mode |
| `/autocommit` | Toggle auto git commit on edits |
| `/vault` | Toggle vault on/off |
| `/allowlist` | Toggle allowlist/denylist mode |
| `/model [name]` | Show or switch model |
| `/provider [name]` | Show or switch provider |
| `/models` | List Ollama models |
| `/persona [name]` | Show or switch MOP persona |
| `/files` | List working directory |
| `/tools` | List available tools |
| `/loaded` | Show loaded context layers |
| `/stats` | Session stats |
| `/about` | Version info |
| `/focus <pattern>` | Deep codebase search |
| `/grep <pattern>` | Grep files |
| `/copy` | Copy last response to clipboard |
| `/compress` | Trim history to last 10 messages |
| `/subcompress` | Compress large tool outputs |
| `/checkpoint [name]` | Save conversation snapshot |
| `/restore [n\|name]` | Restore from checkpoint |
| `/rewind [n]` | Undo last N turns |

---

### `config.py` — Theme & Configuration

**Color palette** (ANSI 24-bit):
- `_A` blue accent · `_A2` input text · `_T` chat text
- `_M` muted gray · `_D` dim · `_I` ghost
- `_G` green (loaded/allowlist) · `_Y` amber (warning) · `_R` red (blocked)

**`load_config()`** — reads `~/.config/codemaid/config.json`

**`save_config()`** — writes config back

**`_build_help_table()`** — builds the `/help` Rich table

**`console`** — shared Rich `Console` instance
