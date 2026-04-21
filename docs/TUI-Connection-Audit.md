# TUI ↔ App Connection Audit
**Date:** 2026-04-19
**Source Scans:** Projects/CodeMAID, Projects/Airmy, Projects/ToDo

---

## The Core Problem

You have:
- A **Textual TUI** (being built — DeepSeek/Grok skeleton)
- **CodeMAID** — the agent backend that does the actual AI work

They need to talk. Right now they don't — because CodeMAID's TUI is baked into the CLI loop (`codemaid/cli/main.py`), not separated from the agent logic.

---

## What Already Exists Across Your Projects

### 1. RPC Protocol (Pi — `Projects/ToDo`)
**File:** `ToDo/Pi/pi-mono-main/packages/coding-agent/src/modes/rpc/`

This is the most important find. Pi already has a complete **JSONL over stdin/stdout RPC protocol** that does exactly what you need:

```
TUI process  →  stdin (JSON line)  →  Agent process
TUI process  ←  stdout (JSON line) ←  Agent process
```

Supported commands already designed:
- `prompt` — send message
- `steer` — interrupt and redirect
- `follow_up` — continue conversation
- `abort` — cancel in-flight request
- `new_session` — start fresh
- `get_state` — query current session state
- `set_model` — switch AI backend
- `compact` — compress context
- `branch` / `switch_session` — session branching (the git idea)

**Files to read:**
- `rpc-mode.ts` — the headless server side (what CodeMAID needs to become)
- `rpc-client.ts` — the client side (what your TUI needs)
- `rpc-types.ts` — the protocol interfaces
- `docs/rpc.md` — full protocol spec with examples

**This is your bridge design. Copy the protocol, implement it in Python.**

---

### 2. Persistent Shell IPC (CodeMAID — `Projects/CodeMAID`)
**File:** `codemaid/tools/system_tools.py` — `_ShellSession` class

CodeMAID already has proven subprocess IPC:
- Spawns `/bin/bash` once per working directory
- Communicates via stdin/stdout pipes with a sentinel echo pattern
- Thread-safe with a lock
- Output collected via daemon thread + queue

This is the implementation pattern for the RPC bridge — the same approach but with JSON lines instead of bash commands.

---

### 3. HTTP REST Bridge (Airmy — `Projects/Airmy`)
**File:** `Airmy/tools/voice-proxy/voice_proxy.py` — port 8899

If you'd rather use HTTP than stdin/stdout:
- `GET /transcript` — poll for latest input
- `POST /speak` — send output to render
- `GET /status` — health check
- `GET /history` — last 50 entries

This pattern works for voice but adapts directly to text. The TUI calls `POST /prompt`, the agent calls `GET /response`.

**Simpler to debug than stdin/stdout. Slightly more setup.**

---

### 4. Session Logger (CodeMAID + Airmy — already built)
**Files:**
- `codemaid/sessions/storage.py` — SQLite at `~/.agents/sessions/codemaid.db`
- `codemaid/sessions/logger.py` — `SessionLogger` class
- `Airmy/Ai-Tools/Sessions-Exporter/scripts/agent_runner.py` — subprocess wrapper

The session infrastructure is already done. The TUI just needs to:
1. Call `SessionLogger.start_session("cuckaoccurs")` on launch
2. Read from `storage.py` to display history
3. Everything else is already being logged

---

### 5. EventBus (Pi — `Projects/ToDo`)
**File:** `ToDo/Pi/pi-mono-main/packages/coding-agent/src/core/event-bus.ts`

Simple pub/sub: `emit(channel, data)` / `on(channel, handler)`.

In Python this is just `asyncio.Queue` or `threading.Event`. CodeMAID's `main.py` already uses threading for the confirm modal (lines 152-168) — same pattern applies to TUI ↔ agent communication.

---

### 6. Agent Session Branching (Pi — `Projects/ToDo`)
**Files:**
- `coding-agent/src/core/agent-session.ts` — branching support
- `coding-agent/src/core/session-manager.ts` — JSONL-based session files with branch IDs

The git-style session branching from ChatGPT's suggestion is already built in Pi's TypeScript codebase. The SQLite schema you need:

```sql
ALTER TABLE sessions ADD COLUMN parent_session_id TEXT REFERENCES sessions(id);
ALTER TABLE sessions ADD COLUMN branch_label TEXT;
```

One column addition to CodeMAID's existing schema.

---

## Recommended Architecture

```
┌─────────────────────────────────┐
│   Textual TUI (new)             │
│   - Session list sidebar        │
│   - Chat display                │
│   - Input bar                   │
│   - Persona switcher            │
└────────────┬────────────────────┘
             │  JSONL over stdin/stdout
             │  (Pi's RPC protocol, ported to Python)
┌────────────▼────────────────────┐
│   CodeMAID --rpc mode (new flag)│
│   - Headless (no Rich rendering)│
│   - Reads JSON commands         │
│   - Emits JSON events           │
│   - All existing tools work     │
└────────────┬────────────────────┘
             │
┌────────────▼────────────────────┐
│   ~/.agents/ (existing)         │
│   sessions/codemaid.db          │
│   codemaid_memory.json          │
│   skills/                       │
│   profiles/cuckaoccurs.md       │
└─────────────────────────────────┘
```

---

## What Needs to Be Built

### Step 1 — Add `--rpc` mode to CodeMAID (`codemaid/cli/main.py`)

When launched with `--rpc`, CodeMAID skips the Rich TUI and instead:
```python
# stdin → JSON command
cmd = json.loads(sys.stdin.readline())
# stdout → JSON event
sys.stdout.write(json.dumps({"type": "token", "content": chunk}) + "\n")
sys.stdout.flush()
```

**Reference:** `ToDo/Pi/pi-mono-main/packages/coding-agent/src/modes/rpc/rpc-mode.ts`

### Step 2 — TUI spawns CodeMAID as subprocess

```python
import subprocess, json, threading

proc = subprocess.Popen(
    ["codemaid", "--rpc", "/path/to/workdir"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True
)

def send(cmd: dict):
    proc.stdin.write(json.dumps(cmd) + "\n")
    proc.stdin.flush()

def listen():
    for line in proc.stdout:
        event = json.loads(line)
        # dispatch to TUI via asyncio queue

threading.Thread(target=listen, daemon=True).start()
```

### Step 3 — Wire the existing session DB to the TUI sidebar

The `storage.py` `list_sessions()` method already returns everything the sidebar needs. Import it directly — no network call, no subprocess needed for history.

---

## Files to Port/Reuse Directly

| Source | File | What to take |
|--------|------|-------------|
| ToDo/Pi | `rpc-mode.ts` | Protocol design — port commands/events to Python |
| ToDo/Pi | `rpc-client.ts` | Client subprocess wrapper — port to Python |
| ToDo/Pi | `rpc-types.ts` | JSON schema for all messages |
| CodeMAID | `sessions/storage.py` | Use as-is — import directly into TUI |
| CodeMAID | `sessions/logger.py` | Use as-is |
| CodeMAID | `tools/system_tools.py` | `_ShellSession` pattern for subprocess IPC |
| Airmy | `voice-proxy/voice_proxy.py` | HTTP bridge pattern (alternative to stdin/stdout) |
| Airmy | `Sessions-Exporter/agent_runner.py` | Subprocess wrapper pattern |

---

## What NOT to Use

- **`codemaid/cli/main.py` raw keypress loop** — this gets replaced by Textual. Don't try to wrap it.
- **`codemaid/cli/config.py` Rich console** — Textual has its own rendering. Keep only `load_config()` and `THEME`.
- **The gateway.py messaging bridges** — Telegram/Discord/Slack integration is orthogonal to TUI work. Leave it alone for now.
