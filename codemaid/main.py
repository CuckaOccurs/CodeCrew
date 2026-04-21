"""
CODEMAID CLI — Clean terminal UI.
"""

import getpass
import os
import re
import select
import signal
import shutil
import subprocess
import sys
import termios
import threading
import time
import tty
from pathlib import Path

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text
except ImportError:
    print("Error: 'rich' is required. Install with: pip install rich")
    sys.exit(1)

from .agent import Agent
from .tools import execute_tool, TOOLS
from .provider import get_provider
from .skills_loader import build_system_prompt, get_load_status
from .memory import Memory
from .gateway import Gateway
from .defaults import (
    DEFAULT_PROVIDER, DEFAULT_MODEL, PROVIDER_DEFAULTS,
    DEFAULT_MODEL_CYCLE, DEFAULT_OLLAMA_HOST
)
from .vault import validate_command, FREE, CAGE, SAFE, VAULT

from .config import THEME, console, _render, load_config, _A, _T, _I, _G, _R, _Y, _P, _D, _Z
from .commands import handle_slash_command
from .ui_state import UIState
from .renderer import Renderer



def _build_project_context(work_dir: Path) -> str:
    lines = ["\n\n## Project Context (auto)"]
    try:
        r = subprocess.run(["git", "status", "--short", "--branch"],
                           capture_output=True, text=True, cwd=str(work_dir), timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            lines.append("```\n" + r.stdout.strip()[:600] + "\n```")
    except Exception:
        pass
    try:
        entries = sorted(
            p.name for p in work_dir.iterdir()
            if not p.name.startswith(".") and p.name not in ("node_modules", "venv", "__pycache__")
        )[:20]
        if entries:
            lines.append("Files: " + "  ".join(entries))
    except Exception:
        pass
    return "\n".join(lines) if len(lines) > 1 else ""


def _run_rpc(args):
    """Headless JSONL-over-stdio mode for SIDE and other front-ends.

    Protocol:
      stdin  → {"id":"1","type":"chat","text":"..."}
               {"id":"2","type":"set_model","model":"qwen3:14b"}
               {"id":"3","type":"ping"}
      stdout ← {"id":"1","type":"chunk","text":"..."}   (streaming)
               {"id":"1","type":"tool_call","name":"...","args":{}}
               {"id":"1","type":"vault","severity":"CAGE","cmd":"..."}
               {"id":"1","type":"done","text":"full response"}
               {"id":"1","type":"error","text":"..."}
               {"type":"ready","model":"..."}
               {"type":"pong"}
    """
    import json

    work_dir    = Path(getattr(args, "dir", ".")).resolve()
    cfg         = load_config()
    prov_name   = args.provider or cfg.get("provider", DEFAULT_PROVIDER)
    model_name  = args.model    or cfg.get("model",    DEFAULT_MODEL)
    api_key     = args.api_key  or cfg.get("api_key")
    host_url    = args.host     or DEFAULT_OLLAMA_HOST

    try:
        provider = get_provider(name=prov_name, model=model_name,
                                host=host_url, api_key=api_key)
    except ValueError as e:
        sys.stderr.write(f"provider error: {e}\n"); sys.exit(1)

    memory        = Memory(work_dir=str(work_dir))
    system_prompt = build_system_prompt() + "\n\n" + memory.get_context()
    agent         = Agent(provider, str(work_dir), system_prompt=system_prompt)

    def emit(obj):
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()

    emit({"type": "ready", "model": model_name})

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        msg_id   = msg.get("id", "0")
        msg_type = msg.get("type")

        if msg_type == "ping":
            emit({"type": "pong"})

        elif msg_type == "set_model":
            agent.provider.model = msg.get("model", agent.provider.model)
            emit({"type": "model_set", "model": agent.provider.model})

        elif msg_type == "chat":
            text = msg.get("text", "").strip()
            if not text:
                continue

            def _chunk(token, _id=msg_id):
                emit({"id": _id, "type": "chunk", "text": token})

            def _confirm(name, a, _id=msg_id):
                cmd = str(a.get("command", ""))
                sev, note = validate_command(cmd)
                emit({"id": _id, "type": "vault", "severity": sev, "cmd": cmd, "msg": note})
                return sev != VAULT

            def _tool_call(name, a, _id=msg_id):
                emit({"id": _id, "type": "tool_call", "name": name, "args": a})

            def _tool_result(name, r, _id=msg_id):
                emit({"id": _id, "type": "tool_result", "name": name,
                      "result": str(r)[:500]})

            try:
                result = agent.chat(
                    text,
                    on_chunk=_chunk,
                    on_confirm=_confirm,
                    on_tool_call=_tool_call,
                    on_tool_result=_tool_result,
                )
                emit({"id": msg_id, "type": "done", "text": result or ""})
            except KeyboardInterrupt:
                emit({"id": msg_id, "type": "error", "text": "interrupted"})
            except Exception as e:
                emit({"id": msg_id, "type": "error", "text": str(e)})


def main():
    _subs = {"onboard", "terminal", "gateway", "rpc"}
    if not any(a in _subs for a in sys.argv[1:]):
        sys.argv.insert(1, "terminal")

    import argparse
    parser = argparse.ArgumentParser(description="CODEMAID")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model",    default=None)
    parser.add_argument("--api-key",  default=None)
    parser.add_argument("-p", "--prompt")
    parser.add_argument("--host",     default=None)
    parser.add_argument("--persona", "--profile", default=None, dest="persona")

    subs = parser.add_subparsers(dest="command")
    subs.add_parser("onboard")

    tp = subs.add_parser("terminal")
    tp.add_argument("dir", nargs="?", default=".")
    tp.add_argument("--provider", default=None); tp.add_argument("--model", default=None)
    tp.add_argument("--api-key",  default=None); tp.add_argument("-p", "--prompt")
    tp.add_argument("--host",     default=None); tp.add_argument("--persona", "--profile", default=None, dest="persona")

    gp = subs.add_parser("gateway")
    gp.add_argument("action", choices=["start", "setup", "stop"])

    rp = subs.add_parser("rpc")
    rp.add_argument("dir",        nargs="?", default=".")
    rp.add_argument("--provider", default=None)
    rp.add_argument("--model",    default=None)
    rp.add_argument("--api-key",  default=None)
    rp.add_argument("--host",     default=None)

    args = parser.parse_args()

    if args.command == "rpc":
        _run_rpc(args); return

    if args.command == "onboard":
        Onboarder().run(); return

    if args.command == "gateway":
        gw = Gateway()
        {"start": gw.start_all, "setup": gw.setup_wizard, "stop": gw.stop}.get(
            args.action, lambda: None)()
        return

    # ── Bootstrap ────────────────────────────────────────────────────────────
    try:
        work_dir = Path(getattr(args, "dir", ".")).resolve()
    except FileNotFoundError:
        work_dir = Path.home()

    cfg          = load_config()
    profile_name = getattr(args, "persona", None) or cfg.get("default_profile")
    profile_cfg  = cfg.get("profiles", {}).get(profile_name, {}) if profile_name else {}
    _prov_name   = args.provider or profile_cfg.get("provider") or cfg.get("provider", DEFAULT_PROVIDER)
    
    # Priority: 1. CLI Arg --model, 2. Profile setting, 3. Config provider_defaults[provider], 4. Factory provider default, 5. Factory global default
    model_name   = args.model or profile_cfg.get("model") or cfg.get("provider_defaults", {}).get(_prov_name) or PROVIDER_DEFAULTS.get(_prov_name, DEFAULT_MODEL)
    
    api_key      = args.api_key or profile_cfg.get("api_key") or cfg.get("api_key")
    host_url     = args.host or profile_cfg.get("host") or cfg.get("providers", {}).get(_prov_name, {}).get("host") or os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
    prompt_mode  = getattr(args, "prompt", None)

    # Model cycle list — reads from config key "model_cycle", falls back to sensible default
    _model_list = cfg.get("model_cycle", DEFAULT_MODEL_CYCLE)
    if model_name not in _model_list:
        _model_list.insert(0, model_name)
    _model_idx_init = _model_list.index(model_name)

    try:
        provider = get_provider(name=_prov_name, model=model_name,
                                host=host_url, api_key=api_key)
    except ValueError as e:
        console.print(f"[red]{e}[/red]"); sys.exit(1)

    memory        = Memory(work_dir=str(work_dir))

    # MOP created early so persona can be restored before system prompt is built
    from .sessions.logger import SessionLogger
    from .sessions.mop import MOPController
    user_id        = getpass.getuser()
    session_logger = SessionLogger()
    mop            = MOPController(user_id, session_logger.storage)

    profile_name  = args.persona or cfg.get("default_profile") or mop.last_persona() or "default"
    profile_cfg   = cfg.get("profiles", {}).get(profile_name, {})
    persona_name  = profile_cfg.get("persona", profile_name)
    _load_cfg     = cfg.get("load", {})
    system_prompt = build_system_prompt(profile_name=persona_name, load_cfg=_load_cfg) + "\n\n" + memory.get_context() + _build_project_context(work_dir)
    _load_status  = get_load_status(_load_cfg)

    session_logger.start_session(user_id, profile=persona_name)
    prior_context = mop.hydrate()
    if prior_context:
        system_prompt += f"\n\n{prior_context}"

    # ── State ────────────────────────────────────────────────────────────────
    history         = []       # [(renderable | None, ansi_str)]
    _ui_cfg         = cfg.get("ui", {})
    _vault_cfg      = cfg.get("vault", {})
    _agent_cfg      = cfg.get("agent", {})
    _draw_lock      = threading.Lock()
    _interrupt      = threading.Event()

    st = UIState(
        vault_on      = _vault_cfg.get("enabled", True),
        dry_run       = _ui_cfg.get("dry_run", False),
        guard_mode    = _ui_cfg.get("guard_mode", True),
        prov_name     = _prov_name,
        model_idx     = _model_idx_init,
        last_vault    = FREE,
    )

    # TODO list — [(text, done)] — loaded from DB, survives sessions
    _todos     = mop.load_todos()
    # Message queue — filled while thinking, drained after each response
    _msg_queue = []

    # ── Renderer ─────────────────────────────────────────────────────────────
    rnd = Renderer(
        st           = st,
        draw_lock    = _draw_lock,
        history      = history,
        todos        = _todos,
        agent        = None,       # set after Agent() is created below
        work_dir     = work_dir,
        profile_name = profile_name,
        load_status  = _load_status,
        render_fn    = _render,
    )

    def _add(text, style=None, raw=False):
        if raw:
            s = text if text.endswith("\n") else text + "\n"
            history.append((None, s))
        else:
            r = Text(text, style=style or THEME["dim"])
            history.append((r, _render(r)))

    def _on_trace(label, content):
        with _draw_lock:
            history.append((None, f"{_D}[{label}] {content[:120]}{_Z}\n"))
        rnd.draw()

    agent = Agent(
        provider, str(work_dir),
        system_prompt=system_prompt,
        trace_callback=_on_trace,
        max_iterations=_agent_cfg.get("max_iterations", 20),
        context_token_limit=_agent_cfg.get("context_limit", 24000),
        tool_limits=_agent_cfg.get("tool_limits", {}),
        summary_keep_turns=_agent_cfg.get("summary_keep_turns", 6),
    )
    rnd.agent = agent   # now wire up the agent reference

    if prompt_mode:
        console.print(Markdown(agent.chat(prompt_mode))); return

    signal.signal(signal.SIGWINCH, lambda *_: rnd.on_resize())

    # ── Vault confirm ────────────────────────────────────────────────────────
    def _on_confirm(name, a):
        cmd = str(a.get("command", ""))

        severity, msg = validate_command(cmd, allowlist=st.allowlist_mode, sudo_mode=st.sudo_mode)
        st.last_vault = severity

        if severity == SAFE:
            _add(f"  {_R}■ blocked{_Z}  {cmd[:72]}", raw=True)
            return False

        return True

    # ── Command state ────────────────────────────────────────────────────────
    # Register CPU-side auto-save task with MOP (every 10 turns)
    from .tools.session_tools import auto_save_history
    def _auto_save():
        auto_save_history(list(agent.history), label=st.session_name or persona_name)
    mop.schedule("auto-save", 10, _auto_save)

    def _poll_services():
        import subprocess as _sp
        try:
            r = _sp.run(["pgrep", "-x", "ollama"], capture_output=True, timeout=2)
            st.svc_ollama = r.returncode == 0
        except Exception:
            st.svc_ollama = False
        try:
            r = _sp.run(["pgrep", "-f", "pi-coding-agent"], capture_output=True, timeout=2)
            st.svc_pi = r.returncode == 0
        except Exception:
            st.svc_pi = False

    _poll_services()                          # initial check at startup
    mop.schedule("svc-poll", 3, _poll_services)   # re-check every 3 turns

    _cmd_state = {
        "history": history, "agent": agent, "work_dir": work_dir,
        "ui": st, "session_logger": session_logger, "mop": mop,
        "session_start": time.time(),
        "host_url": host_url, "api_key": api_key,
        "add_fn": _add, "draw_fn": rnd.draw, "render_fn": _render,
        "execute_tool": execute_tool, "TOOLS": TOOLS, "THEME": THEME,
        "get_provider": get_provider,
    }

    # ── Input loop ───────────────────────────────────────────────────────────
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        rnd.draw()

        try:
          while True:
            if select.select([sys.stdin], [], [], 0.05) != ([sys.stdin], [], []):
                if st.is_thinking:
                    now = time.time()
                    if now - st.last_draw_t >= 0.1:
                        st.last_draw_t = now
                        st.spin_frame += 1
                        rnd.draw()
                    continue

                # No stdin input — drain queue if pending
                if st.pending_msg is not None:
                    st.input_buffer = st.pending_msg
                    st.pending_msg  = None
                    char = "\n"
                else:
                    continue
            else:
                char = sys.stdin.read(1)

            if char == "\x1b":                           # ESC / arrow keys
                seq = ""
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    seq += sys.stdin.read(1)
                    if seq == "[" and select.select([sys.stdin], [], [], 0.05)[0]:
                        seq += sys.stdin.read(1)
                if seq == "[A":                          # Up arrow — scroll up
                    st.scroll_offset += 3; rnd.draw()
                elif seq == "[B":                        # Down arrow — scroll down
                    st.scroll_offset = max(0, st.scroll_offset - 3); rnd.draw()
                elif seq == "[5~":                       # PgUp
                    st.scroll_offset += 10; rnd.draw()
                elif seq == "[6~":                       # PgDn
                    st.scroll_offset = max(0, st.scroll_offset - 10); rnd.draw()
                elif not seq:                            # bare ESC
                    if st.is_thinking: _interrupt.set()
                    else: st.input_buffer = ""; rnd.draw()
                continue

            if char == "\x0f":                           # ^O — tool expand
                st.tool_expanded = not st.tool_expanded
                rnd.draw(); continue

            if char == "\t":                             # TAB — mode toggle
                st.shell_mode = not st.shell_mode; rnd.draw(); continue

            if char == "\x13":                           # ^S — sudo
                if st.sudo_mode:
                    st.sudo_mode = False
                    agent.sudo_mode = False
                    _add("  sudo off", raw=True)
                    rnd.draw()
                else:
                    # Restore terminal to get password input
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    sys.stdout.write("\n  sudo password: ")
                    sys.stdout.flush()
                    try:
                        pw = getpass.getpass("")
                        ok = subprocess.run(
                            ["sudo", "-S", "-v"],
                            input=pw + "\n", capture_output=True, text=True
                        ).returncode == 0
                    except Exception:
                        ok = False
                    tty.setcbreak(fd)
                    if ok:
                        st.sudo_mode = True
                        agent.sudo_mode = True
                        _add("  SUDO ON  all vault checks bypassed", raw=True)
                    else:
                        _add("  sudo denied", raw=True)
                    rnd.draw()
                continue

            if char == "\x04":                           # ^D — dry run
                st.dry_run = not st.dry_run
                agent.dry_run = st.dry_run; rnd.draw(); continue

            if char == "\x14":                           # ^T — thinking on/off
                st.show_thinking = not st.show_thinking
                _state = "on" if st.show_thinking else "off"
                _add(f"  thinking display {_state}", raw=True)
                rnd.draw(); continue

            if char == "\x07":                           # ^G — guard toggle
                st.guard_mode = not st.guard_mode
                _state = "on" if st.guard_mode else "off"
                _add(f"  prompt guard {_state}", raw=True)
                rnd.draw(); continue

            if char == "\x10":                           # ^P — cycle model
                st.model_idx = (st.model_idx + 1) % len(_model_list)
                new_model = _model_list[st.model_idx]
                agent.provider.model = new_model
                _add(f"  ⇄  {new_model}", raw=True)
                rnd.draw(); continue

            if char in ("\r", "\n"):
                user_input = st.input_buffer.strip()
                st.input_buffer = ""
                if not user_input: rnd.draw(); continue

                if st.is_thinking:
                    _msg_queue.append(user_input)
                    rnd.push_tool_log("⏎", f"queued  {user_input[:55]}")
                    rnd.draw(); continue

                st.scroll_offset = 0
                history.append((None, rnd.bubble_right(user_input)))
                if not mop.is_paused:
                    session_logger.log_input(user_input)

                # Slash commands
                if user_input.startswith("/"):
                    parts = user_input.split(None, 1)
                    cmd   = parts[0].lower()
                    arg   = parts[1].strip() if len(parts) > 1 else ""

                    # /todo — inline handling
                    if cmd == "/todo":
                        sub = arg.split(None, 1)
                        op  = sub[0].lower() if sub else ""
                        txt = sub[1] if len(sub) > 1 else ""
                        if op == "add" and txt:
                            _todos.append((txt, False))
                            st.todo_idx = next(
                                (i for i, (_, d) in enumerate(_todos) if not d),
                                len(_todos) - 1)
                            _add(f"  {_A}+{_Z}  {txt}", raw=True)
                        elif op in ("done", "next"):
                            if _todos:
                                idx = st.todo_idx
                                _todos[idx] = (_todos[idx][0], True)
                                nxt = next(
                                    (i for i in range(idx+1, len(_todos)) if not _todos[i][1]),
                                    next((i for i, (_, d) in enumerate(_todos) if not d), -1))
                                st.todo_idx = max(0, nxt)
                                _add(f"  {_D}✓ done{_Z}", raw=True)
                        elif op == "clear":
                            _todos.clear(); st.todo_idx = 0
                            _add(f"  {_D}todo cleared{_Z}", raw=True)
                        elif op == "prev":
                            if st.todo_idx > 0:
                                st.todo_idx -= 1
                        else:
                            for i, (t, d) in enumerate(_todos):
                                sym = f"{_D}✓{_Z}" if d else (f"{_A}►{_Z}" if i == st.todo_idx else f"{_M}○{_Z}")
                                _add(f"  {sym}  {t}", raw=True)
                        rnd.draw(); continue

                    action = handle_slash_command(cmd, arg, _cmd_state)
                    if action == "exit": break
                    continue

                # Shell execution (TAB mode or ! prefix)
                if st.shell_mode or user_input.startswith("!"):
                    import shlex
                    cmd_raw = user_input[1:].strip() if user_input.startswith("!") else user_input
                    severity, msg = validate_command(cmd_raw, allowlist=st.allowlist_mode, sudo_mode=st.sudo_mode)
                    st.last_vault = severity
                    if severity == VAULT:
                        _add(f"  {_R}■ blocked{_Z}  {cmd_raw[:72]}", raw=True)
                        rnd.draw(); continue
                    if severity == CAGE:
                        _add(f"  {_Y}⚠ cage{_Z}  {cmd_raw[:72]}", raw=True)
                    try:
                        cmd_args = shlex.split(cmd_raw)
                        proc = subprocess.run(cmd_args, capture_output=True, text=True,
                                              cwd=str(work_dir), timeout=30)
                        out = (proc.stdout + proc.stderr).strip()
                        _add(out or "(no output)")
                    except Exception as e:
                        _add(f"  {e}", style=THEME["red"])
                    rnd.draw(); continue

                # Syntax guard — catch bare shell commands and "Dirty Code" before sending to AI
                if st.guard_mode:
                    from codemaid.prompt_guard import scan_prompt
                    # Estimate current history size for context guard
                    hist_size = sum(len(str(m).encode()) for m in agent.history)
                    issues = scan_prompt(user_input, hist_size)
                    if issues:
                        for issue in issues:
                            color = _R if issue.severity == "CRITICAL" else _Y
                            _add(f"  {color}⚠ {issue.description}{_Z}", raw=True)
                            _add(f"    {_D}Suggestion: {issue.suggestion}{_Z}", raw=True)
                        rnd.draw()
                        if any(i.severity == "CRITICAL" for i in issues):
                            continue # Block critical breaches
                        # For warnings, we let them through but they've been flagged


                # AI mode — run in thread so animation loop stays alive
                with _draw_lock:
                    st.is_thinking = True
                    st.spin_frame  = 0
                st.think_start  = time.time()
                st.verb_t       = st.think_start
                st.current_tool = None
                rnd.draw()
                _interrupt.clear()

                _result   = [None]
                _chat_err = [None]
                _done_evt = threading.Event()

                def _on_tool_call(name, args):
                    label, path = rnd.tool_summary(name, args)
                    st.current_tool  = (label, path)
                    st.tool_expanded = False
                    if not mop.is_paused:
                        session_logger.log_tool_call(name, args)

                def _on_tool_result(name, result):
                    if st.current_tool:
                        rnd.push_tool_log("⚒", st.current_tool[0])
                    st.current_tool = None
                    if not mop.is_paused:
                        session_logger.log_tool_result(name, result)

                st.turn_tokens  = 0
                st.rate_t       = time.time()
                st.rate_tokens  = 0

                def _chat_worker():
                    try:
                        def _chunk(token):
                            if _interrupt.is_set(): raise KeyboardInterrupt()
                            st.token_count += 1
                            st.turn_tokens += 1
                            st.rate_tokens += 1
                            now = time.time()
                            dt  = now - st.rate_t
                            if dt >= 0.5:
                                st.token_rate  = st.rate_tokens / dt
                                st.rate_tokens = 0
                                st.rate_t      = now
                            # Feed live buffer — track think vs content
                            if token.startswith("<think>"):
                                st.live_is_think = True
                                token = token[7:]
                            if token.endswith("</think>"):
                                st.live_is_think = False
                                token = token[:-8]
                            st.live_buf += token
                        _result[0] = agent.chat(
                            user_input,
                            on_tool_call=_on_tool_call,
                            on_tool_result=_on_tool_result,
                            on_confirm=_on_confirm,
                            on_chunk=_chunk,
                        )
                    except KeyboardInterrupt:
                        _add(f"  {_D}interrupted{_Z}", raw=True)
                    except Exception as e:
                        _chat_err[0] = str(e)
                    finally:
                        _done_evt.set()

                threading.Thread(target=_chat_worker, daemon=True).start()

                try:
                    while not _done_evt.is_set():
                        _done_evt.wait(0.08)
                        now = time.time()
                        if now - st.last_draw_t >= 0.08:
                            st.last_draw_t = now
                            st.spin_frame += 1
                            rnd.draw()
                        # Read keys during thinking
                        if select.select([sys.stdin], [], [], 0)[0]:
                            k = sys.stdin.read(1)
                            if k == "\x1b":
                                _interrupt.set()
                            elif k == "\x0f":            # ^O — expand/collapse tool call
                                st.tool_expanded = not st.tool_expanded
                            elif k == "\x10":            # ^P — cycle model mid-stream
                                st.model_idx = (st.model_idx + 1) % len(_model_list)
                                agent.provider.model = _model_list[st.model_idx]
                                _add(f"  {_I}⇄  {agent.provider.model}{_Z}", raw=True)
                                rnd.draw()
                except KeyboardInterrupt:
                    _interrupt.set()
                    _done_evt.wait(2.0)

                with _draw_lock:
                    st.is_thinking = False
                st.token_rate    = 0.0
                st.live_buf      = ""
                st.live_is_think = False
                st.current_tool  = None
                rnd.clear_tool_log()
                result = f"Error: {_chat_err[0]}" if _chat_err[0] else _result[0]

                if result:
                    import re as _re
                    # Model self-name declaration
                    name_match = _re.match(r'^\[NAME:\s*(.+?)\]\s*\n?', result)
                    if name_match:
                        st.session_name = name_match.group(1).strip().capitalize()
                        result = result[name_match.end():]

                    # Extract and strip thinking blocks (support both <think> and <thought>)
                    think_match = _re.search(r'<(think|thought)>(.*?)</\1>', result, _re.DOTALL)
                    clean = _re.sub(r'<(think|thought)>.*?</\1>', '', result, flags=_re.DOTALL).strip()
                    
                    if think_match and st.show_thinking:
                        # Only show if show_thinking is ON, but keep it brief
                        think_text = f"{_D}[thinking: {len(think_match.group(2))} chars]{_Z}\n"
                        history.append((None, think_text))
                    
                    display = clean or result
                    if display:
                        r = Markdown(display)
                        history.append((r, _render(r)))
                        if not mop.is_paused:
                            session_logger.log_output(display)
                    mop.tick(agent._turn_count)

                rnd.draw()

                if _msg_queue:
                    st.pending_msg = _msg_queue.pop(0)

                continue

            if char in ("\x7f", "\x08"):
                if st.input_buffer:
                    st.input_buffer = st.input_buffer[:-1]
                    rnd.draw()
            elif ord(char) > 31:
                st.input_buffer += char
                rnd.draw()

        except KeyboardInterrupt:
            pass

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[2J\033[H")

        elapsed = time.time() - _cmd_state["session_start"]
        mins, secs = divmod(int(elapsed), 60)
        turns  = getattr(agent, "_turn_count", 0)
        w      = shutil.get_terminal_size().columns
        done_t = [t for t, d in _todos if d]
        open_t = [t for t, d in _todos if not d]

        # Save rolling summary to session before closing
        try:
            if agent.history:
                summary = agent._summarize_turns(agent.history)
                if summary:
                    session_logger.save_summary(summary)
        except (KeyboardInterrupt, Exception):
            pass
        mop.save_todos(_todos)
        session_logger.end_session()

        sys.stdout.write(f"\n{'─' * w}\n")
        sys.stdout.write(f"  session ended\n\n")
        sys.stdout.write(f"  turns       {turns}\n")
        sys.stdout.write(f"  tokens      {st.token_count}\n")
        sys.stdout.write(f"  model       {agent.provider.model}\n")
        sys.stdout.write(f"  provider    {st.prov_name}\n")
        sys.stdout.write(f"  time        {mins}m {secs:02d}s\n")
        sys.stdout.write(f"  dir         {work_dir}\n")
        sys.stdout.write(f"  thinking    {'on' if st.show_thinking else 'off'}\n")
        sys.stdout.write(f"  sudo        {'on' if st.sudo_mode else 'off'}\n")
        if done_t or open_t:
            sys.stdout.write(f"\n  todos\n")
            for t in done_t:
                sys.stdout.write(f"  ✓  {t}\n")
            for t in open_t:
                sys.stdout.write(f"  ○  {t}\n")
        sys.stdout.write(f"\n{'─' * w}\n\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
