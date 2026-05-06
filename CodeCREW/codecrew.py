#!/usr/bin/env python3
"""
CodeCrew v4.20.19
Alternate screen buffer with scroll region.
Status bar stays at bottom. Content scrolls above it.
Tested before shipping.
"""

import asyncio
import json
import logging
import os
import sys
import time
import threading
import blessed
from datetime import datetime
from pathlib import Path

logging.disable(logging.CRITICAL)

term = blessed.Terminal()

CODEMOP_PATH = Path(os.getenv("CODEMOP_HOME", Path.home() / "CodeMAID"))
if not CODEMOP_PATH.exists():
    # Try sibling directory if default doesn't exist
    sibling = Path(__file__).parent.parent / "CodeMAID"
    if sibling.exists():
        CODEMOP_PATH = sibling

# Default paths (will be overridden if MOP is found)
APP_ROOT = Path(os.getenv("AGENTS_ROOT", Path.home() / ".agents")) / "app"
PERSONAS_DIR = APP_ROOT / "personas"
CONFIG_PATH = APP_ROOT / "config.yaml"

MOP_AVAILABLE = False
if CODEMOP_PATH.exists():
    sys.path.insert(0, str(CODEMOP_PATH))
    try:
        from codemop.api import OllamaAPI
        from codemop.walker import Walker
        from codemop.assembler import Assembler
        from codemop.utils import ChunkedReader
        from codemop import APP_ROOT as MOP_APP_ROOT, PERSONAS_DIR as MOP_PERSONAS_DIR, CONFIG_PATH as MOP_CONFIG_PATH
        APP_ROOT = MOP_APP_ROOT
        PERSONAS_DIR = MOP_PERSONAS_DIR
        CONFIG_PATH = MOP_CONFIG_PATH
        MOP_AVAILABLE = True
    except Exception:
        # Fallback to standalone mode if MOP imports fail
        pass

AGENTS_DIR   = APP_ROOT
PERSONAS_DIR = PERSONAS_DIR
CONFIG_PATH  = CONFIG_PATH

def get_config():
    try:
        import yaml
        return yaml.safe_load(CONFIG_PATH.read_text()) or {}
    except Exception:
        return {}

def get_ollama_url():
    if MOP_AVAILABLE:
        try:
            config = get_config()
            return config.get("ollama", {}).get("url", "http://localhost:11434")
        except Exception:
            pass

    # Try localhost first
    import subprocess
    try:
        # Quick check for local ollama
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", 11434)) == 0:
                return "http://127.0.0.1:11434"
    except Exception:
        # Fallback to standalone mode if MOP imports fail
        pass

    return get_config().get("ollama", {}).get("url", "http://localhost:11434")

def get_default_model():
    return get_config().get("ollama", {}).get("default_model", "qwen3.5:9b")

R     = term.normal
DIM   = term.dim
BOLD  = term.bold
CYAN  = term.color(110)
GREY  = term.color(245)
DGREY = term.color(238)
WHITE = term.color(252)
RED   = term.color(160)
YELLOW= term.color(178)
GREEN = term.color(71)
VAULT_COLOR = {"safe": YELLOW, "cage": GREEN, "free": RED}

def W():
    return term.width

def H():
    return term.height

# ─── Terminal setup/teardown ──────────────────────────────────────────────────

def setup_terminal():
    sys.stdout.write(term.enter_fullscreen)
    # 0-indexed: rows 0 to h-3 are the scroll region.
    # Rows h-2 and h-1 are protected for the status bar.
    sys.stdout.write(term.csr(0, term.height - 3))
    sys.stdout.write(term.move_yx(0, 0))
    sys.stdout.flush()

def cleanup_terminal():
    # Reset scroll region to the full screen
    sys.stdout.write(term.csr(0, term.height - 1))
    sys.stdout.write(term.exit_fullscreen)
    sys.stdout.write(term.normal_cursor)
    sys.stdout.flush()
    # Fallback to system reset if terminal state is corrupted
    import os
    os.system("stty sane")

def draw_status():
    h = term.height
    w = term.width
    vc    = VAULT_COLOR.get(s.vault, GREEN)
    left  = f"  {s.cwd}"
    mid   = s.vault
    right = f"{s.model}  \u00b7  {s.persona_id}  "
    lpad  = max(0, w // 2 - len(left) - len(mid) // 2)
    rpad  = max(0, w - len(left) - lpad - len(mid) - len(right))

    personas = list_personas()
    quickhelp = DGREY + "  " + "  ".join("/" + p for p in personas) + "  /help  /clear  /reset" + R

    with term.location():
        # Status line (row h-2, 0-indexed)
        sys.stdout.write(term.move_yx(h - 2, 0) + term.clear_eol)
        sys.stdout.write(DGREY + left + " "*lpad + vc + mid + DGREY + " "*rpad + GREY + s.model + "  \u00b7  " + CYAN + BOLD + s.persona_id + R)

        # Quickhelp line (row h-1, 0-indexed)
        sys.stdout.write(term.move_yx(h - 1, 0) + term.clear_eol)
        sys.stdout.write(quickhelp)
        sys.stdout.flush()

# ─── State ────────────────────────────────────────────────────────────────────

class State:
    persona_id    = "kai"
    persona_data  = {}
    model         = ""
    vault         = "cage"
    cwd           = Path.cwd()
    streaming     = False
    interrupted   = False
    system_prompt = ""
    history       = []
    turn_count    = 0

s = State()

# ─── Persona ──────────────────────────────────────────────────────────────────

def load_persona(name):
    path = PERSONAS_DIR / f"{name}.md"
    if not path.exists():
        return {"voice": "", "model": None, "intro": "", "hints": [], "name": name}
    text = path.read_text(errors="replace")
    meta = {"model": None, "intro": "", "hints": [], "name": name, "voice": ""}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                fm = yaml.safe_load(parts[1]) or {}
                meta["model"] = fm.get("model")
                meta["intro"] = fm.get("introduction", "")
                meta["hints"] = fm.get("hints", [])
                meta["name"]  = fm.get("name", name)
            except Exception:
                pass
            meta["voice"] = parts[2].strip()
    else:
        meta["voice"] = text.strip()
    return meta

def list_personas():
    if not PERSONAS_DIR.exists():
        return []
    return [f.stem for f in sorted(PERSONAS_DIR.glob("*.md"))
            if ".bak" not in f.name and not f.stem.startswith(".")]

def switch_persona(pid, silent=False):
    data = load_persona(pid)
    s.persona_id    = pid
    s.persona_data  = data
    s.system_prompt = data["voice"]
    s.history       = []
    if data.get("model"):
        s.model = data["model"]
    if not silent:
        intro = data.get("intro", "")
        name  = data.get("name", pid)
        print(DIM + "  " + (f"{name}  \u00b7  {intro}" if intro else f"switched to {name}") + R)
    draw_status()

# ─── Hint scroller ────────────────────────────────────────────────────────────

def hint_scroller():
    hints = s.persona_data.get("hints", []) or ["processing"]
    start = last = time.time()
    idx = [0]
    while s.streaming and not s.interrupted:
        elapsed = int(time.time() - start)
        if time.time() - last >= 5:
            idx[0] += 1
            last = time.time()
        hint = hints[idx[0] % len(hints)]
        line = f"  \u2261  {hint}  ({elapsed}s  esc to interrupt)"
        pad  = max(0, term.width - len(line))
        # row h-3 is the last row of the scroll region (1 to h-2)
        with term.location(0, term.height - 3):
            sys.stdout.write(term.hide_cursor + term.clear_eol)
            sys.stdout.write(DIM + line + " " * pad + R)
            sys.stdout.flush()
        time.sleep(0.25)
    # Clear hint row
    with term.location(0, term.height - 3):
        sys.stdout.write(term.clear_eol)
        sys.stdout.flush()

# ─── MOP ──────────────────────────────────────────────────────────────────────

def mop_log(prompt, response):
    if not MOP_AVAILABLE: return
    try:
        ctx = {
            "profile": s.persona_id, "personas": [s.persona_id],
            "persona_names": [s.persona_data.get("name", s.persona_id)],
            "model": s.model, "fallback_model": s.model, "min_context": 4096,
            "project": s.cwd.name, "cwd": str(s.cwd), "status": "active",
            "git": False, "tools": [], "instructions": s.system_prompt,
            "session_dir": str(APP_ROOT / "sessions" / "codecrew"),
            "decisions": [], "assembled_at": datetime.now().isoformat(),
            "rtfm_files": [], "notes": "", "vault": s.vault,
        }
        OllamaAPI()._log_exchange(ctx, prompt, response)
    except Exception:
        # Fallback to standalone mode if MOP imports fail
        pass

# ─── Stream ───────────────────────────────────────────────────────────────────

async def stream(prompt):
    import httpx
    s.streaming   = True
    s.interrupted = False

    t = threading.Thread(target=hint_scroller, name="HintScroller", daemon=True)
    t.start()

    msgs = []
    if s.system_prompt:
        msgs.append({"role": "system", "content": s.system_prompt})
    msgs.extend(s.history)
    msgs.append({"role": "user", "content": prompt})
    s.history.append({"role": "user", "content": prompt})

    resp_text = ""
    first     = True

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST", f"{get_ollama_url()}/api/chat",
                json={"model": s.model, "messages": msgs, "stream": True}
            ) as resp:
                async for line in resp.aiter_lines():
                    if s.interrupted: break
                    if not line.strip(): continue
                    try: data = json.loads(line)
                    except: continue
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        for mk in ["<|endoftext|>", "<|im_start|>", "<|im_end|>"]:
                            if mk in chunk:
                                chunk = chunk[:chunk.index(mk)]
                                s.interrupted = True
                        if first:
                            s.streaming = False
                            t.join(timeout=0.5)
                            ts   = datetime.now().strftime("%H:%M")
                            name = s.persona_data.get("name", s.persona_id)
                            # Ensure we start on a clean line within the scroll region
                            sys.stdout.write(f"{DGREY}  {ts}  {CYAN}{BOLD}{name}{R}  ")
                            sys.stdout.flush()
                            first = False
                        resp_text += chunk
                        sys.stdout.write(WHITE + chunk + R)
                        sys.stdout.flush()
                    if data.get("done") or s.interrupted: break

        sys.stdout.write("\n")
        sys.stdout.flush()

        if resp_text:
            s.history.append({"role": "assistant", "content": resp_text})
            s.turn_count += 1
            threading.Thread(target=mop_log, args=(prompt, resp_text), daemon=True).start()

    except Exception as e:
        print(RED + f"  \u2717 ollama: {e}" + R)
    finally:
        s.streaming   = False
        s.interrupted = False
        t.join(timeout=0.5)
        draw_status()

# ─── Input ────────────────────────────────────────────────────────────────────

def read_line():
    # Force cursor to the last line of the scroll region
    sys.stdout.write(term.move_yx(term.height - 3, 0) + DGREY + "  > " + R)
    sys.stdout.flush()
    buf = []

    with term.cbreak():
        while True:
            val = term.inkey(timeout=0.1)
            if not val:
                continue

            if val.name == "KEY_ENTER" or val == "\r" or val == "\n":
                sys.stdout.write("\n")
                sys.stdout.flush()
                return "".join(buf)

            if val == "\x03":  # Ctrl+C
                if s.streaming:
                    s.interrupted = True
                    s.streaming   = False
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    return None
                sys.stdout.write("\n")
                sys.stdout.flush()
                return "__EXIT__"

            if val == "\x04":  # Ctrl+D
                sys.stdout.write("\n")
                sys.stdout.flush()
                return "__EXIT__"

            if val.name == "KEY_ESCAPE":
                # Plain ESC — interrupt streaming only
                if s.streaming:
                    s.interrupted = True
                    s.streaming   = False
                continue

            if val.name in ("KEY_BACKSPACE", "KEY_DELETE") or val == "\x7f" or val == "\x08":
                if buf:
                    buf.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                continue

            if not val.is_sequence and val.isprintable():
                buf.append(val)
                sys.stdout.write(WHITE + val + R)
                sys.stdout.flush()

# ─── Commands ─────────────────────────────────────────────────────────────────

def handle_cmd(text):
    personas = list_personas()
    parts = text.strip().split()
    cmd   = parts[0].lower().lstrip("/")

    if cmd in personas:
        switch_persona(cmd)
        return True
    if cmd in ("safe", "cage", "free"):
        s.vault = cmd
        sys.stdout.write(DIM + f"  vault: {cmd}\n" + R)
        draw_status()
        return True
    if cmd == "clear":
        sys.stdout.write(term.clear)
        sys.stdout.flush()
        draw_status()
        return True
    if cmd == "reset":
        s.history = []
        s.turn_count = 0
        sys.stdout.write(DIM + "  context cleared\n" + R)
        return True
    if cmd == "help":
        sys.stdout.write(DIM + "  personas : " + "  ".join(f"/{p}" for p in personas) + "\n" + R)
        sys.stdout.write(DIM + "  vault    : /safe  /cage  /free\n" + R)
        sys.stdout.write(DIM + "  context  : /clear  /reset\n" + R)
        sys.stdout.write(DIM + "  files    : /read <path>\n" + R)
        sys.stdout.write(DIM + "  clip     : /copy [text]  /paste\n" + R)
        sys.stdout.write(DIM + "  keys     : esc interrupt   ctrl+c exit\n" + R)
        return True
    if cmd == "copy":
        import subprocess
        text = " ".join(parts[1:])
        if not text and s.history:
            # Copy last assistant response
            for msg in reversed(s.history):
                if msg["role"] == "assistant":
                    text = msg["content"]
                    break
        if text:
            try:
                subprocess.run(["wl-copy"], input=text.encode(), check=True)
                print(DIM + "  copied to clipboard" + R)
            except Exception as e:
                print(RED + f"  copy failed: {e}" + R)
        return True
    if cmd == "paste":
        import subprocess
        try:
            res = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True, check=True)
            pasted = res.stdout
            if pasted:
                # We can't easily inject into the current input buffer of read_line
                # but we can treat it as a new user message or just print it.
                # For now, let's just print it so the user can see it's working
                # and maybe in a future update we'll handle it better.
                print(DIM + "  pasted: " + R + pasted[:50] + ("..." if len(pasted) > 50 else ""))
                s.history.append({"role": "user", "content": f"[Pasted from clipboard]\n{pasted}"})
            else:
                print(DIM + "  clipboard empty" + R)
        except Exception as e:
            print(RED + f"  paste failed: {e}" + R)
        return True
    if cmd == "read":
        if len(parts) < 2:
            print(RED + "  usage: /read <path> [chunk_index]" + R)
            return True
        path = Path(parts[1]).expanduser()
        if not path.exists():
            print(RED + f"  not found: {path}" + R)
            return True
        
        chunk_idx = int(parts[2]) if len(parts) > 2 else 0
        
        if MOP_AVAILABLE:
            reader = ChunkedReader()
            content = reader.read_file(path, chunk_idx)
            info = reader.get_info(path)
            if content is not None:
                s.history.append({"role": "user", "content": f"[File: {path} (Chunk {chunk_idx}/{info['total_chunks']-1})]\n\n{content}"})
                print(DIM + f"  loaded: {path} [Chunk {chunk_idx}/{info['total_chunks']-1}] ({len(content)} chars)" + R)
            else:
                print(RED + f"  read failed: {path}" + R)
        else:
            content = path.read_text(errors="replace")
            s.history.append({"role": "user", "content": f"[File: {path}]\n\n{content}"})
            print(DIM + f"  loaded: {path}  ({len(content)} chars)" + R)
        return True
    return False

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    s.model = get_default_model()

    setup_terminal()

    personas = list_personas()
    default = "kai" if "kai" in personas else (personas[0] if personas else None)
    if default:
        switch_persona(default, silent=True)

    if MOP_AVAILABLE:
        try:
            files = Walker().walk(s.cwd)
            if files:
                ctx = Assembler().assemble(files, s.cwd)
                rtfm = ctx.get("instructions", "")
                if rtfm:
                    s.system_prompt = (s.system_prompt + "\n\n" + rtfm) if s.system_prompt else rtfm
                print(DIM + f"  context: {len(files)} rtfm file(s) loaded" + R)
        except Exception:
            pass

    draw_status()
    loop = asyncio.get_event_loop()

    while True:
        try:
            text = await loop.run_in_executor(None, read_line)
        except KeyboardInterrupt:
            break

        if text is None:
            continue
        if text == "__EXIT__":
            break

        text = text.strip()
        if not text:
            continue

        personas = list_personas()
        bare = text.lower().lstrip("/")
        if text.startswith("/") or bare in personas:
            handle_cmd(text if text.startswith("/") else "/" + text)
            continue

        ts = datetime.now().strftime("%H:%M")
        sys.stdout.write(f"\n{DGREY}  {ts}  {GREY}{text}{R}\n")
        sys.stdout.flush()
        await stream(text)

import os
import sys

def run_terminal():
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        cleanup_terminal()
        os._exit(0)
    except Exception as e:
        cleanup_terminal()
        print(f"\nError: {e}")
        os._exit(1)
    finally:
        cleanup_terminal()
        os._exit(0)

if __name__ == "__main__":
    run_terminal()
