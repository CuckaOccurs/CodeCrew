"""
CODEMAID CLI — Clean terminal UI.
"""

import getpass
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

from codemaid.agent import Agent
from codemaid.tools import execute_tool, TOOLS
from codemaid.provider import get_provider
from codemaid.skills_loader import build_system_prompt, get_load_status
from codemaid.memory import Memory
from codemaid.gateway import Gateway
from codemaid.onboarder import Onboarder
from codemaid.vault import validate_command, FREE, CAGE, SAFE, VAULT

from .config import THEME, console, _render, load_config
from .commands import handle_slash_command


# ── Palette ──────────────────────────────────────────────────────────────────
_A  = "\033[38;2;95;122;175m"    # blue          (accent, prompt ❯, active bars)
_A2 = "\033[38;2;75;98;150m"     # deep blue     (input text)
_T  = "\033[38;2;100;106;128m"   # slate gray    (chat text)
_D  = "\033[38;2;28;33;50m"      # near-black    (idle bars, subtle)
_I  = "\033[38;2;44;50;68m"      # ghost         (near-invisible on black)
_M  = "\033[38;2;65;70;90m"      # dim slate     (labels, brackets)
_G  = "\033[38;2;72;105;152m"    # calm blue     (loaded dots, allowlist)
_Y  = "\033[38;2;112;90;145m"    # dim violet    (cage warning)
_R  = "\033[38;2;145;38;38m"     # deep red      (vault blocked, sudo)
_Z  = "\033[0m"                   # reset
_B  = "\033[1m"                   # bold


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
    prov_name   = args.provider or cfg.get("provider", "ollama")
    model_name  = args.model    or cfg.get("model",    "qwen3:27b")
    api_key     = args.api_key  or cfg.get("api_key")
    host_url    = args.host     or "http://localhost:11434"

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
    parser.add_argument("--profile",  default=None)

    subs = parser.add_subparsers(dest="command")
    subs.add_parser("onboard")

    tp = subs.add_parser("terminal")
    tp.add_argument("dir", nargs="?", default=".")
    tp.add_argument("--provider", default=None); tp.add_argument("--model", default=None)
    tp.add_argument("--api-key",  default=None); tp.add_argument("-p", "--prompt")
    tp.add_argument("--host",     default=None); tp.add_argument("--profile", default=None)

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
    profile_name = getattr(args, "profile", None) or cfg.get("default_profile")
    profile_cfg  = cfg.get("profiles", {}).get(profile_name, {}) if profile_name else {}
    _defaults    = {"ollama": "qwen3.5:27b", "openai": "gpt-4o",
                    "anthropic": "claude-sonnet-4-6", "gemini": "gemini-2.0-flash"}
    prov_name    = [args.provider or profile_cfg.get("provider") or cfg.get("provider", "ollama")]
    model_name   = args.model or profile_cfg.get("model") or _defaults.get(prov_name[0], "qwen3:27b")
    api_key      = args.api_key or profile_cfg.get("api_key") or cfg.get("api_key")
    host_url     = args.host or profile_cfg.get("host") or cfg.get("providers", {}).get(prov_name[0], {}).get("host") or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    prompt_mode  = getattr(args, "prompt", None)

    # Model cycle list — reads from config key "model_cycle", falls back to sensible default
    _model_list = cfg.get("model_cycle", [model_name, "qwen3:14b", "qwen3.5:9b"])
    if model_name not in _model_list:
        _model_list.insert(0, model_name)
    _model_idx  = [_model_list.index(model_name)]

    try:
        provider = get_provider(name=prov_name[0], model=model_name,
                                host=host_url, api_key=api_key)
    except ValueError as e:
        console.print(f"[red]{e}[/red]"); sys.exit(1)

    memory        = Memory(work_dir=str(work_dir))
    profile_name  = args.profile or cfg.get("default_profile", "default")
    profile_cfg   = cfg.get("profiles", {}).get(profile_name, {})
    persona_name  = profile_cfg.get("persona", profile_name)
    _load_cfg     = cfg.get("load", {})
    system_prompt = build_system_prompt(profile_name=persona_name, load_cfg=_load_cfg) + "\n\n" + memory.get_context() + _build_project_context(work_dir)
    _load_status  = get_load_status(_load_cfg)

    # ── State ────────────────────────────────────────────────────────────────
    history         = []       # [(renderable | None, ansi_str)]
    input_buffer    = ""
    _ui_cfg         = cfg.get("ui", {})
    _vault_cfg      = cfg.get("vault", {})
    _agent_cfg      = cfg.get("agent", {})
    is_thinking     = False
    vault_on        = [_vault_cfg.get("enabled", True)]
    sudo_mode       = [False]
    dry_run         = [_ui_cfg.get("dry_run", False)]
    shell_mode      = [False]
    allowlist_mode  = [False]
    guard_mode      = [_ui_cfg.get("guard_mode", True)]
    _draw_lock      = threading.Lock()
    _last_draw_t    = [0.0]
    _spin_frame     = [0]
    _interrupt      = threading.Event()
    _drawn_count    = [0]
    _last_vault     = [FREE]

    # Token tracking
    _token_count    = [0]        # total tokens this session
    _turn_tokens    = [0]        # tokens in current turn
    _rate_tokens    = [0]        # tokens since last rate sample
    _rate_t         = [0.0]      # time of last rate sample
    _token_rate     = [0.0]      # tokens/sec (smoothed)
    show_thinking   = [True]     # display model's <think> reasoning

    # TODO list — [(text, done)]
    _todos          = []
    _todo_idx       = [0]        # current active item

    # Message queue — filled while thinking, drained after each response
    _msg_queue      = []
    _pending_msg    = [None]   # next message to auto-submit

    # Live streaming buffer — shown during thinking, cleared after response
    _live_buf       = [""]
    _live_is_think  = [False]  # True while inside <think> block

    from codemaid.sessions.logger import SessionLogger
    session_logger = SessionLogger()
    session_logger.start_session(getpass.getuser(), profile=profile_name)

    # Inject last session summary into system prompt if available
    last_summary = session_logger.resume_last(getpass.getuser())
    if last_summary:
        system_prompt += f"\n\n## Last Session Summary\n{last_summary}"

    def _on_trace(label, content):
        r = Panel(f"[dim]{content}[/dim]", title=label, border_style="dim")
        with _draw_lock:
            history.append((r, _render(r)))
        _draw()

    agent = Agent(
        provider, str(work_dir),
        system_prompt=system_prompt,
        trace_callback=_on_trace,
        max_iterations=_agent_cfg.get("max_iterations", 20),
        context_token_limit=_agent_cfg.get("context_limit", 24000),
        tool_limits=_agent_cfg.get("tool_limits", {}),
        summary_keep_turns=_agent_cfg.get("summary_keep_turns", 6),
    )
    if prompt_mode:
        console.print(Markdown(agent.chat(prompt_mode))); return

    # ── Helpers ──────────────────────────────────────────────────────────────
    _strip_ansi = lambda s: re.sub(r'\033\[[0-9;]*m', '', s)

    def _cols():
        return shutil.get_terminal_size().columns

    def _add(text, style=None, raw=False):
        if raw:
            s = text if text.endswith("\n") else text + "\n"
            history.append((None, s))
        else:
            r = Text(text, style=style or THEME["dim"])
            history.append((r, _render(r)))

    def _sep(thinking=False, frame=0):
        """Top bar: KR animation while thinking, dim separator when idle."""
        w = _cols()
        if not thinking:
            return f"{_D}{'─' * w}{_Z}\n"
        # Knight Rider blue gradient — bounces
        cycle = w * 2
        pos   = frame % cycle
        if pos >= w: pos = cycle - pos

        _gc = [
            "\033[38;2;20;40;140m",   # deep blue (edge)
            "\033[38;2;40;80;210m",   # blue
            "\033[38;2;80;40;200m",   # blue-purple
            "\033[38;2;150;30;170m",  # purple
            "\033[38;2;220;30;120m",  # pink
            "\033[38;2;255;30;30m",   # red (center)
            "\033[38;2;220;30;120m",  # pink
            "\033[38;2;150;30;170m",  # purple
            "\033[38;2;80;40;200m",   # blue-purple
            "\033[38;2;40;80;210m",   # blue
            "\033[38;2;20;40;140m",   # deep blue (edge)
        ]
        _glyph = "──━━━━━━━──"
        half   = len(_gc) // 2

        parts = []
        for i in range(w):
            d = i - pos
            if -half <= d <= half:
                idx = d + half
                parts.append(f"{_gc[idx]}{_glyph[idx]}")
            else:
                parts.append(f"{_D}─")
        return "".join(parts) + f"{_Z}\n"

    def _vault_bar():
        """Bottom bar — solid color showing vault state."""
        w = _cols()
        if sudo_mode[0]:
            return f"{_R}{'━' * w}{_Z}\n"
        elif not vault_on[0]:
            return f"{_D}{'─' * w}{_Z}\n"
        elif _last_vault[0] == SAFE:
            return f"{_R}{'━' * w}{_Z}\n"
        elif _last_vault[0] == CAGE:
            return f"{_Y}{'━' * w}{_Z}\n"
        elif allowlist_mode[0]:
            return f"{_G}{'─' * w}{_Z}\n"
        else:
            return f"{_M}{'─' * w}{_Z}\n"

    def _todo_overlay():
        if not _todos:
            return ""
        w     = _cols()
        lines = []
        for i, (text, done) in enumerate(_todos):
            if done:
                marker = f"{_D}✓{_Z}"
                body   = f"{_D}{text[:w-8]}{_Z}"
            elif i == _todo_idx[0]:
                marker = f"{_A}{_B}►{_Z}"
                body   = f"{_T}{text[:w-8]}{_Z}"
            else:
                marker = f"{_M}○{_Z}"
                body   = f"{_M}{text[:w-8]}{_Z}"
            lines.append(f"  {marker}  {body}")
        return "\n".join(lines) + "\n"

    def _header_bar():
        """Pinned top bar — profile, load indicators, clock. Redrawn in place at row 1."""
        import datetime
        w    = _cols()
        rows = shutil.get_terminal_size().lines

        # Profile / role
        role_label = f"{_A}⬡ codemaid{_Z}  {_M}◆{_Z} {_T}{profile_name}{_Z}"

        # Load dots  ●=loaded  ○=not loaded
        def dot(loaded, label):
            return f"{_G}●{_Z}{_T}{label}{_Z}" if loaded else f"{_I}○{_T}{label}{_Z}"

        s  = _load_status
        sc = f"({s['skill_count']})" if s.get('skill_count', 0) > 1 else ""
        rc = f"({s['rule_count']})"  if s.get('rule_count',  0) > 1 else ""
        dicts = ",".join(s.get("dicts", [])) or "—"

        indicators = "  ".join([
            dot(s.get("instructions"), "I"),
            dot(s.get("rules"),        f"R{rc}"),
            dot(s.get("skills"),       f"S{sc}"),
            dot(bool(s.get("dicts")),  f"D:{dicts}"),
        ])

        # Clock
        clock = f"{_M}{datetime.datetime.now().strftime('%H:%M')}{_Z}"

        # Compose — left: role  center: indicators  right: clock
        left_raw  = _strip_ansi(role_label)
        mid_raw   = _strip_ansi(indicators)
        right_raw = _strip_ansi(clock)
        gap1 = max(1, (w - len(left_raw) - len(mid_raw) - len(right_raw)) // 2)
        gap2 = max(1, w - len(left_raw) - len(mid_raw) - len(right_raw) - gap1)
        bar  = f"  {role_label}" + " " * gap1 + indicators + " " * gap2 + f"{clock}  "

        # Write at row 1, restore cursor, reset scroll region to rows 2..bottom
        return (
            f"\033[s"                       # save cursor
            f"\033[1;1H"                    # move to row 1 col 1
            f"\033[2K"                      # clear line
            f"{_D}{'─' * w}{_Z}\r"         # dim underline
            f"\033[1;1H{bar}"              # write bar over it
            f"\033[2;{rows}r"              # scroll region: row 2 to bottom
            f"\033[u"                       # restore cursor
        )

    def _3col(left, mid, right, w):
        """Render three strings: left-aligned, centered, right-aligned."""
        lw = len(_strip_ansi(left))
        mw = len(_strip_ansi(mid))
        rw = len(_strip_ansi(right))
        mid_pos   = (w - mw) // 2
        left_pad  = max(1, mid_pos - lw - 2)
        right_pad = max(1, w - (mid_pos + mw) - rw - 2)
        return f"  {left}" + " " * left_pad + mid + " " * right_pad + f"{right}  "

    def _status():
        w = _cols()

        # Dir
        d = str(work_dir)
        home = str(Path.home())
        d = "~" + d[len(home):] if d.startswith(home) else d

        # Vault — cyan when free, loud when triggered
        if sudo_mode[0]:             vlt = f"{_R}{_B}SUDO{_Z}"
        elif not vault_on[0]:        vlt = f"{_I}vault·off{_Z}"
        elif allowlist_mode[0]:      vlt = f"{_G}allow{_Z}"
        elif _last_vault[0] == SAFE: vlt = f"{_R}■ safe{_Z}"
        elif _last_vault[0] == CAGE: vlt = f"{_Y}⚠ cage{_Z}"
        else:                        vlt = f"{_M}free{_Z}"

        # Token rate — only shown when streaming
        rate     = _token_rate[0]
        rate_str = (f"{_A}{rate/1000:.1f}k/s{_Z}" if rate >= 1000
                    else f"{_A}{rate:.0f}/s{_Z}" if rate > 0 else "")

        # Tokens — ghost until non-zero
        tc       = _token_count[0]
        tok_str  = f"{_M}{tc}tok{_Z}" if tc > 0 else ""

        # Turns — ghost until turn 1
        turns    = getattr(agent, '_turn_count', 0)
        turn_str = f"{_M}t:{turns}{_Z}" if turns > 0 else ""

        # Mode — ghost when default chat, loud when shell
        mode = f"{_A}shell{_Z}" if shell_mode[0] else f"{_I}chat{_Z}"

        # Thinking — ghost when on (default), visible when off
        think_str = f"{_I}think{_Z}" if show_thinking[0] else f"{_Y}think·off{_Z}"

        # Guard — ghost when on (default), visible when off
        guard_str = f"{_I}guard{_Z}" if guard_mode[0] else f"{_Y}guard·off{_Z}"

        # Dry run — hidden unless active
        dry_str = f"{_Y}dry·run{_Z}" if dry_run[0] else ""

        stats = "  ".join(p for p in [rate_str, tok_str, turn_str] if p)
        flags = "  ".join(p for p in [think_str, dry_str] if p)

        # vault + guard sit together in center
        vlt_guard = vlt + f"  {guard_str}"

        # Line 1: dir | vault·guard | model
        line1 = _3col(f"{_T}{d}{_Z}", vlt_guard, f"{_T}{agent.provider.model}{_Z}", w)
        # Line 2: mode | stats | flags
        line2 = _3col(mode, stats, flags, w)

        return line1 + "\n" + line2

    def _draw():
        with _draw_lock:
            thinking   = is_thinking
            frame      = _spin_frame[0]
            new_items  = history[_drawn_count[0]:]
            _drawn_count[0] = len(history)

        sys.stdout.write("\033[?25l\033[u\033[J")
        sys.stdout.write(_header_bar())

        for (_, rendered) in new_items:
            sys.stdout.write(rendered if rendered.endswith("\n") else rendered + "\n")

        sys.stdout.write("\033[s")

        todo_block = _todo_overlay()
        todo_lines = todo_block.count("\n") if todo_block else 0

        if thinking:
            # Render live streaming text (last N lines to avoid flood)
            live = _live_buf[0]
            if live:
                live_color = _D if _live_is_think[0] else _T
                visible = live.replace("\r", "").splitlines()[-12:]
                live_block = "".join(
                    f"  {live_color}{ln[:_cols()-4]}{_Z}\n" for ln in visible
                ) + "\n"
            else:
                live_block = ""
            sys.stdout.write(
                f"{live_block}"
                f"\n{_sep(thinking=True, frame=frame)}"
                f"{todo_block}"
                f"  {_D}❯{_Z}  {_D}{input_buffer}{_Z}\n"
                f"{_vault_bar()}"
                f"{_status()}"
            )
        else:
            sys.stdout.write(
                f"\n{_sep()}"
                f"{todo_block}"
                f"  {_A}❯{_Z}  {_A2}{input_buffer}{_Z}\n"
                f"{_vault_bar()}"
                f"{_status()}"
            )
            # Rewrite input line so cursor lands naturally after the buffer —
            # avoids guessing ❯ column width (ambiguous across terminals)
            input_row = 2 + todo_lines
            sys.stdout.write(f"\033[u\033[{input_row}B\r  {_A}❯{_Z}  {_A2}{input_buffer}")
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    # ── Resize ───────────────────────────────────────────────────────────────
    def _on_resize(signum=None, frame=None):
        rows = shutil.get_terminal_size().lines
        for i, (renderable, _) in enumerate(history):
            if renderable is not None:
                history[i] = (renderable, _render(renderable))
        sys.stdout.write(f"\033[2J\033[2;{rows}r\033[2;1H\033[s")
        sys.stdout.flush()
        _drawn_count[0] = 0
        _draw()

    signal.signal(signal.SIGWINCH, _on_resize)

    # ── Prompt review popup (native — works in any terminal) ─────────────────
    def _prompt_review_popup(text, issues):
        w = shutil.get_terminal_size().columns
        pad = max(2, (w - 66) // 2)
        ind = " " * pad

        _TYPE_COLOR = {
            "contradiction":      _R,
            "ambiguous":          _Y,
            "hallucination_risk": _R,
            "complex":            _Y,
        }
        _TYPE_ICON = {
            "contradiction":      "✕",
            "ambiguous":          "?",
            "hallucination_risk": "⚠",
            "complex":            "⋯",
        }

        def _render(edited=""):
            hr = f"{ind}{_D}{'─' * 62}{_Z}\n"
            out  = "\033[?1049h\033[2J\033[H"   # alt screen, clear
            out += f"\n{ind}{_R}{_B}⚠  Prompt Guard{_Z}\n"
            out += hr
            out += f"\n{ind}{_M}prompt{_Z}\n"
            for line in text[:500].splitlines():
                out += f"{ind}{_T}{line[:62]}{_Z}\n"
            out += f"\n{ind}{_Y}issues{_Z}\n"
            for issue in issues:
                col  = _TYPE_COLOR.get(issue.type, _Y)
                icon = _TYPE_ICON.get(issue.type, "▸")
                out += f"{ind}{col}{icon}  {issue.description}{_Z}\n"
                if issue.span:
                    out += f"{ind}   {_D}'{issue.span}'{_Z}\n"
            if edited:
                out += f"\n{hr}"
                out += f"{ind}{_A}edited{_Z}\n"
                for line in edited.splitlines():
                    out += f"{ind}{_T}{line[:62]}{_Z}\n"
            out += f"\n{hr}"
            out += (f"{ind}{_A}s{_Z}{_M}end  "
                    f"{_A}e{_Z}{_M}dit  "
                    f"{_A}x{_Z}{_M}cancel{_Z}\n\n")
            return out

        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write(_render())
        sys.stdout.flush()

        result = None
        edited = ""
        try:
            tty.setcbreak(fd)
            while True:
                ch = sys.stdin.read(1).lower()
                if ch == "s":
                    result = edited or text
                    break
                elif ch == "e":
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    sys.stdout.write(f"{ind}{_A}edit (ctrl+d done):{_Z}\n{ind}")
                    sys.stdout.flush()
                    lines = []
                    try:
                        while True:
                            lines.append(input(ind))
                    except EOFError:
                        pass
                    edited = "\n".join(lines).strip() or text
                    tty.setcbreak(fd)
                    sys.stdout.write(_render(edited))
                    sys.stdout.flush()
                elif ch in ("x", "q", "\x1b"):
                    result = None
                    break
        finally:
            sys.stdout.write("\033[?1049l")   # restore main screen
            sys.stdout.flush()
            tty.setcbreak(fd)

        return result

    # ── Vault confirm ────────────────────────────────────────────────────────
    def _on_confirm(name, a):
        nonlocal is_thinking
        cmd = str(a.get("command", ""))

        # Guard — analyze the command the agent wants to run
        if guard_mode[0]:
            from codemaid.prompt_guard import analyze_prompt
            issues = analyze_prompt(cmd)
            if issues:
                with _draw_lock: is_thinking = False
                reviewed = _prompt_review_popup(cmd, issues)
                with _draw_lock: is_thinking = True
                if reviewed is None:
                    _add(f"  {_Y}⚠ guard blocked{_Z}  {cmd[:60]}", raw=True)
                    _draw()
                    return False
                # user edited or approved — update command arg
                a["command"] = reviewed
                cmd = reviewed

        severity, msg = validate_command(cmd, allowlist=allowlist_mode[0], sudo_mode=sudo_mode[0])
        _last_vault[0] = severity

        if severity == SAFE:
            with _draw_lock: is_thinking = False
            _add(f"  {_R}■ safe{_Z}  {cmd[:72]}", raw=True)
            _add(f"  {_D}{msg}{_Z}", raw=True)
            _draw()
            return False

        if severity == CAGE:
            _add(f"  {_Y}⚠ cage{_Z}  {cmd[:72]}", raw=True)
            _draw()

        return True

    # ── Command state ────────────────────────────────────────────────────────
    _cmd_state = {
        "history": history, "agent": agent, "work_dir": work_dir,
        "vault_on": vault_on, "session_logger": session_logger,
        "provider_name": prov_name, "session_start": time.time(),
        "host_url": host_url, "api_key": api_key,
        "add_fn": _add, "draw_fn": _draw, "render_fn": _render,
        "execute_tool": execute_tool, "TOOLS": TOOLS, "THEME": THEME,
        "get_provider": get_provider,
    }

    # ── Input loop ───────────────────────────────────────────────────────────
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        rows = shutil.get_terminal_size().lines
        sys.stdout.write(f"\033[2J\033[2;{rows}r\033[2;1H\033[s")
        _draw()
        tty.setcbreak(fd)

        try:
          while True:
            if select.select([sys.stdin], [], [], 0.05) != ([sys.stdin], [], []):
                if is_thinking:
                    now = time.time()
                    if now - _last_draw_t[0] >= 0.1:
                        _last_draw_t[0] = now
                        _spin_frame[0] += 1
                        _draw()
                    continue
                # No stdin input — drain queue if pending
                if _pending_msg[0] is not None:
                    input_buffer    = _pending_msg[0]
                    _pending_msg[0] = None
                    char = "\n"
                else:
                    continue
            else:
                char = sys.stdin.read(1)

            if char == "\x1b":                           # ESC
                if is_thinking: _interrupt.set()
                else: input_buffer = ""; _draw()
                continue

            if char == "\t":                             # TAB — mode toggle
                shell_mode[0] = not shell_mode[0]; _draw(); continue

            if char == "\x13":                           # ^S — sudo
                if sudo_mode[0]:
                    sudo_mode[0] = False
                    agent.sudo_mode = False
                    _add(f"  {_D}sudo off{_Z}", raw=True)
                    _draw()
                else:
                    # Restore terminal to get password input
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    sys.stdout.write(f"\n  {_Y}sudo password:{_Z} ")
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
                        sudo_mode[0] = True
                        agent.sudo_mode = True
                        _add(f"  {_R}{_B}SUDO ON{_Z}  all vault checks bypassed", raw=True)
                    else:
                        _add(f"  {_D}sudo denied{_Z}", raw=True)
                    _draw()
                continue

            if char == "\x04":                           # ^D — dry run
                dry_run[0] = not dry_run[0]
                agent.dry_run = dry_run[0]; _draw(); continue

            if char == "\x14":                           # ^T — thinking on/off
                show_thinking[0] = not show_thinking[0]
                state = "on" if show_thinking[0] else "off"
                _add(f"  {_D}thinking display {state}{_Z}", raw=True)
                _draw(); continue

            if char == "\x07":                           # ^G — guard toggle
                guard_mode[0] = not guard_mode[0]
                state = "on" if guard_mode[0] else "off"
                _add(f"  {_D}prompt guard {state}{_Z}", raw=True)
                _draw(); continue

            if char == "\x10":                           # ^P — cycle model
                _model_idx[0] = (_model_idx[0] + 1) % len(_model_list)
                new_model = _model_list[_model_idx[0]]
                agent.provider.model = new_model
                _add(f"  {_D}⇄  {new_model}{_Z}", raw=True)
                _draw(); continue

            if char in ("\r", "\n"):
                user_input, input_buffer = input_buffer.strip(), ""
                if not user_input: _draw(); continue

                if is_thinking:
                    _msg_queue.append(user_input)
                    _add(f"  {_I}queued  {user_input[:60]}{_Z}", raw=True)
                    _draw(); continue

                r = Text.assemble((f"  ❯  ", f"bold {THEME['blue']}"), (user_input, "#aaaaaa"))
                history.append((r, _render(r)))
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
                            _todo_idx[0] = next(
                                (i for i, (_, d) in enumerate(_todos) if not d),
                                len(_todos) - 1)
                            _add(f"  {_A}+{_Z}  {txt}", raw=True)
                        elif op in ("done", "next"):
                            if _todos:
                                idx = _todo_idx[0]
                                _todos[idx] = (_todos[idx][0], True)
                                nxt = next(
                                    (i for i in range(idx+1, len(_todos)) if not _todos[i][1]),
                                    next((i for i, (_, d) in enumerate(_todos) if not d), -1))
                                _todo_idx[0] = max(0, nxt)
                                _add(f"  {_D}✓ done{_Z}", raw=True)
                        elif op == "clear":
                            _todos.clear(); _todo_idx[0] = 0
                            _add(f"  {_D}todo cleared{_Z}", raw=True)
                        elif op == "prev":
                            if _todo_idx[0] > 0:
                                _todo_idx[0] -= 1
                        else:
                            for i, (t, d) in enumerate(_todos):
                                sym = f"{_D}✓{_Z}" if d else (f"{_A}►{_Z}" if i == _todo_idx[0] else f"{_M}○{_Z}")
                                _add(f"  {sym}  {t}", raw=True)
                        _draw(); continue

                    action = handle_slash_command(cmd, arg, _cmd_state)
                    if action == "exit": break
                    continue

                # Shell execution (TAB mode or ! prefix)
                if shell_mode[0] or user_input.startswith("!"):
                    cmd = user_input[1:].strip() if user_input.startswith("!") else user_input
                    severity, msg = validate_command(cmd, allowlist=allowlist_mode[0], sudo_mode=sudo_mode[0])
                    _last_vault[0] = severity
                    if severity == VAULT:
                        _add(f"  {_R}■ blocked{_Z}  {cmd[:72]}", raw=True)
                        _draw(); continue
                    if severity == CAGE:
                        _add(f"  {_Y}⚠ cage{_Z}  {cmd[:72]}", raw=True)
                    try:
                        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                              cwd=str(work_dir), timeout=30)
                        out = (proc.stdout + proc.stderr).strip()
                        _add(out or "(no output)")
                    except Exception as e:
                        _add(f"  {e}", style=THEME["red"])
                    _draw(); continue

                # Syntax guard — catch bare shell commands before sending to AI
                if guard_mode[0]:
                    from codemaid.prompt_guard import check_looks_like_command
                    cmd_issue = check_looks_like_command(user_input)
                    if cmd_issue:
                        _add(f"  {_Y}⚠ {cmd_issue.description}{_Z}", raw=True)
                        _draw()
                        continue

                # AI mode — run in thread so animation loop stays alive
                with _draw_lock:
                    is_thinking    = True
                    _spin_frame[0] = 0
                _draw()
                _interrupt.clear()

                _result   = [None]
                _chat_err = [None]
                _done_evt = threading.Event()

                _turn_tokens[0] = 0
                _rate_t[0]      = time.time()
                _rate_tokens[0] = 0

                def _chat_worker():
                    try:
                        def _chunk(token):
                            if _interrupt.is_set(): raise KeyboardInterrupt()
                            _token_count[0] += 1
                            _turn_tokens[0] += 1
                            _rate_tokens[0] += 1
                            now = time.time()
                            dt  = now - _rate_t[0]
                            if dt >= 0.5:
                                _token_rate[0] = _rate_tokens[0] / dt
                                _rate_tokens[0] = 0
                                _rate_t[0] = now
                            # Feed live buffer — track think vs content
                            if token.startswith("<think>"):
                                _live_is_think[0] = True
                                token = token[7:]
                            if token.endswith("</think>"):
                                _live_is_think[0] = False
                                token = token[:-8]
                            _live_buf[0] += token
                        _result[0] = agent.chat(
                            user_input,
                            on_tool_call=session_logger.log_tool_call,
                            on_tool_result=session_logger.log_tool_result,
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
                        if now - _last_draw_t[0] >= 0.08:
                            _last_draw_t[0] = now
                            _spin_frame[0] += 1
                            _draw()
                        # Read keys during thinking
                        if select.select([sys.stdin], [], [], 0)[0]:
                            k = sys.stdin.read(1)
                            if k == "\x1b":
                                _interrupt.set()
                            elif k == "\x10":            # ^P — cycle model mid-stream
                                _model_idx[0] = (_model_idx[0] + 1) % len(_model_list)
                                agent.provider.model = _model_list[_model_idx[0]]
                                _add(f"  {_I}⇄  {agent.provider.model}{_Z}", raw=True)
                                _draw()
                except KeyboardInterrupt:
                    _interrupt.set()
                    _done_evt.wait(2.0)

                with _draw_lock:
                    is_thinking = False
                _token_rate[0]  = 0.0
                _live_buf[0]    = ""
                _live_is_think[0] = False
                result = f"Error: {_chat_err[0]}" if _chat_err[0] else _result[0]

                if result:
                    # Separate <think> block from response
                    import re as _re
                    think_match = _re.search(r'<think>(.*?)</think>', result, _re.DOTALL)
                    clean = _re.sub(r'<think>.*?</think>', '', result, flags=_re.DOTALL).strip()
                    if think_match and show_thinking[0]:
                        think_text = think_match.group(1).strip()
                        tr = Text(think_text, style=_D)
                        history.append((tr, _render(tr)))
                    display = clean or result
                    r = Markdown(display)
                    history.append((r, _render(r)))
                    session_logger.log_output(display)
                    if agent._turn_count % 10 == 0:
                        from codemaid.tools.session_tools import auto_save_history
                        auto_save_history(agent.history)

                _draw()

                if _msg_queue:
                    _pending_msg[0] = _msg_queue.pop(0)

                continue

            if char in ("\x7f", "\x08"):
                if input_buffer:
                    input_buffer = input_buffer[:-1]
                    _draw()
            elif ord(char) > 31:
                input_buffer += char
                _draw()

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
        session_logger.end_session()

        sys.stdout.write(f"\n{_M}{'─' * w}{_Z}\n")
        sys.stdout.write(f"  {_M}session ended{_Z}\n\n")
        sys.stdout.write(f"  {_A2}turns       {_Z}{_A}{turns}{_Z}\n")
        sys.stdout.write(f"  {_A2}tokens      {_Z}{_A}{_token_count[0]}{_Z}\n")
        sys.stdout.write(f"  {_A2}model       {_Z}{_A}{agent.provider.model}{_Z}\n")
        sys.stdout.write(f"  {_A2}provider    {_Z}{_A}{prov_name[0]}{_Z}\n")
        sys.stdout.write(f"  {_A2}time        {_Z}{_A}{mins}m {secs:02d}s{_Z}\n")
        sys.stdout.write(f"  {_A2}dir         {_Z}{_T}{work_dir}{_Z}\n")
        sys.stdout.write(f"  {_A2}thinking    {_Z}{_A}{'on' if show_thinking[0] else 'off'}{_Z}\n")
        sys.stdout.write(f"  {_A2}sudo        {_Z}{(_R + 'on' + _Z) if sudo_mode[0] else (_D + 'off' + _Z)}\n")
        if done_t or open_t:
            sys.stdout.write(f"\n  {_M}todos{_Z}\n")
            for t in done_t:
                sys.stdout.write(f"  {_D}✓  {t}{_Z}\n")
            for t in open_t:
                sys.stdout.write(f"  {_Y}○  {t}{_Z}\n")
        sys.stdout.write(f"\n{_M}{'─' * w}{_Z}\n\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
