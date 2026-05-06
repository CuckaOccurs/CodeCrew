"""
CODEMAID CLI — Slash command handlers.

handle_slash_command() receives a `state` dict containing all the shared TUI
state so these handlers are testable and isolated from the main input loop.

Required keys in state:
  history       list[str]      — rendered ANSI lines
  agent         Agent          — the agent instance
  work_dir      Path           — current working directory
  ui            UIState        — mutable UI state (vault_on, prov_name, etc.)
  session_start float          — time.time() at session start
  host_url      str
  api_key       str|None
  add_fn        callable(text, style=None)  — append a text line to history
  draw_fn       callable()                  — redraw the terminal
  render_fn     callable(renderable) -> str — Rich → ANSI
  execute_tool  callable
  TOOLS         list
  THEME         dict
  get_provider  callable

Returns:
  "exit"     — caller should break the input loop
  "continue" — caller should continue the input loop (already handled)
  None       — no special action needed (caller calls _draw() as normal)
"""

import subprocess
import time
from typing import Any

import requests

from .config import _G, _R, _Y, _A, _T, _I, _D, _Z

def _on(state: bool) -> str:
    return f"{_G}on{_Z}" if state else f"{_R}off{_Z}"


def handle_slash_command(cmd: str, arg: str, state: dict[str, Any]) -> str | None:
    """Dispatch a slash command. Returns 'exit', 'continue', or None."""

    history      = state["history"]
    agent        = state["agent"]
    work_dir     = state["work_dir"]
    add          = state["add_fn"]
    draw         = state["draw_fn"]
    render       = state["render_fn"]
    THEME        = state["THEME"]
    TOOLS        = state["TOOLS"]
    execute_tool = state["execute_tool"]
    get_provider = state["get_provider"]
    host_url     = state["host_url"]
    api_key      = state["api_key"]

    st = state["ui"]

    # ── navigation ──────────────────────────────────────────────────────────
    if cmd in ("/exit", "/quit", "/q"):
        return "exit"

    elif cmd == "/config":
        from .config import load_config, save_config, update_config_path
        parts = arg.split(None, 2)
        if not parts:
            c = load_config()
            add("  [bold]Current Config:[/bold]")
            import json
            add(json.dumps(c, indent=2))
        elif parts[0] == "set" and len(parts) >= 3:
            key, val = parts[1], parts[2]
            if update_config_path(key, val):
                add(f"  ✓ set {key} → {val}")
        elif parts[0] == "get" and len(parts) >= 2:
            key = parts[1]
            c = load_config()
            # simple traversal
            target = c
            for p in key.split("."):
                target = target.get(p, {}) if isinstance(target, dict) else {}
            add(f"  {key} = {target}")
        else:
            add("  usage: /config [set|get] [key] [value]", style=THEME["red"])
        draw(); return "continue"

    elif cmd == "/help":
        from .config import _build_help_table
        history.append((None, render(_build_help_table())))

    elif cmd == "/cat":
        from .cat import random_cat_joke
        add(f"  🐾 {random_cat_joke()}")

    elif cmd == "/clear":
        history.clear()
        agent.history.clear()

    # ── trace / mode toggles ────────────────────────────────────────────────
    elif cmd == "/trace":
        agent.trace = not getattr(agent, "trace", False)
        add(f"  trace: {_on(agent.trace)}", raw=True)

    elif cmd == "/lean":
        from .config import load_config, save_config
        from .skills_loader import build_system_prompt
        cfg = load_config()
        if "load" not in cfg: cfg["load"] = {}
        
        current = cfg["load"].get("lean", False)
        cfg["load"]["lean"] = not current
        save_config(cfg)
        
        persona = getattr(agent, "_current_persona", cfg.get("default_profile", "default"))
        agent.system_prompt = build_system_prompt(profile_name=persona, load_cfg=cfg["load"])
        
        status = "ON (Context pruned)" if cfg["load"]["lean"] else "OFF (Full context)"
        add(f"  lean mode: {status}")

    elif cmd == "/plan":
        agent.plan_mode = not getattr(agent, "plan_mode", False)
        add(f"  plan mode: {_on(agent.plan_mode)}", raw=True)

    elif cmd == "/autocommit":
        agent.auto_commit = not getattr(agent, "auto_commit", False)
        add(f"  auto-commit: {_on(agent.auto_commit)}", raw=True)

    elif cmd == "/vault":
        st.vault_on = not st.vault_on
        add(f"  vault: {_on(st.vault_on)}", raw=True)

    elif cmd == "/allowlist":
        agent.vault_allowlist = not agent.vault_allowlist
        mode = "allowlist" if agent.vault_allowlist else "denylist"
        add(f"  vault mode: {mode}")

    # ── model / provider ────────────────────────────────────────────────────
    elif cmd == "/model":
        if arg:
            agent.provider.model = arg
            add(f"  model → {arg}")
        else:
            add(f"  model: {agent.provider.model}")

    elif cmd == "/provider":
        if arg:
            try:
                agent.provider = get_provider(
                    name=arg, model=agent.provider.model,
                    host=host_url, api_key=api_key)
                st.prov_name = arg
                add(f"  provider → {arg}")
            except ValueError as e:
                add(f"  error: {e}", style=THEME["red"])
        else:
            add(f"  provider: {st.prov_name}")

    elif cmd == "/models":
        try:
            data  = requests.get(f"{host_url}/api/tags", timeout=5).json()
            names = [m["name"] for m in data.get("models", [])]
            add("\n".join(f"  {n}" for n in names) or "  (none)")
        except Exception as e:
            add(f"  {e}", style=THEME["red"])

    # ── workspace ───────────────────────────────────────────────────────────
    elif cmd == "/files":
        try:
            files = sorted(p.relative_to(work_dir)
                           for p in work_dir.rglob("*") if p.is_file())
            add("\n".join(f"  {f}" for f in files[:30]))
        except Exception as e:
            add(f"  {e}", style=THEME["red"])

    # ── session info ────────────────────────────────────────────────────────
    elif cmd == "/stats":
        elapsed = time.time() - state["session_start"]
        turns   = sum(1 for m in agent.history if m["role"] == "user")
        tools   = sum(1 for m in agent.history if "tool_calls" in m)
        add(f"  {elapsed/60:.1f}m  •  {turns} turns  •  {tools} tool calls")

    elif cmd == "/about":
        add(f"  codemaid 3.0.0  •  {st.prov_name}  •  {agent.provider.model}")

    elif cmd == "/loaded":
        from .skills_loader import get_load_status
        from .config import load_config
        cfg = load_config()
        lc  = cfg.get("load", {})
        s   = get_load_status(lc)
        add("  ── What's loaded ──────────────────────────")
        add(f"  {'●' if lc.get('lean')        else '○'}  L  lean mode         (prunes backbone/skills)")
        add(f"  {'●' if s.get('instructions') else '○'}  I  instructions     ~/.agents/instructions.md")
        add(f"  {'●' if s.get('rules')        else '○'}  R  rules            ~/.agents/rules/  ({s.get('rule_count', 0)} files)")
        add(f"  {'●' if s.get('skills')       else '○'}  S  skills           ~/.agents/skills/ ({s.get('skill_count', 0)} loaded)")
        dicts = ", ".join(s.get("dicts", [])) or "none"
        add(f"  {'●' if s.get('dicts')        else '○'}  D  dicts            {dicts}")
        add(f"  ◆  persona: {cfg.get('default_profile', 'default')}")
        add(f"  ─  context: {agent.context_token_limit} token limit  •  keep {agent._summary_keep_turns} turns fresh")

    elif cmd == "/session":
        mop    = state.get("mop")
        logger = state.get("session_logger")
        sub    = arg.strip().lower()

        if sub == "pause":
            if mop:
                mop.pause()
                add("  ⏸  session logging paused")
            else:
                add("  MOP not available", style=THEME["red"])

        elif sub == "resume":
            if mop:
                mop.resume()
                add("  ▶  session logging resumed")
            else:
                add("  MOP not available", style=THEME["red"])

        elif sub == "context":
            ctx = mop.injected_context if mop else ""
            if ctx:
                add(f"  [bold]Injected context[/bold] ({len(ctx.encode())} bytes):")
                for line in ctx.splitlines()[:20]:
                    add(f"  {line}")
                if ctx.count("\n") > 20:
                    add("  … (truncated)")
            else:
                add("  no prior context injected this session")

        elif sub.startswith("save"):
            label = arg[4:].strip() or "codemaid"
            from .tools.session_tools import auto_save_history
            agent = state.get("agent")
            if agent and agent.history:
                auto_save_history(list(agent.history), label=label)
                add(f"  ✓ session saved  [{label}]")
            else:
                add("  nothing to save yet")

        else:
            # Default: show status report
            report = mop.report(logger.current_session_id if logger else None) if mop else {}
            add(f"  [bold]session[/bold]  {report.get('current', 'none')}")
            add(f"  paused    {report.get('paused', False)}")
            add(f"  context   {report.get('context_bytes', 0)} bytes injected")
            if report.get("tasks"):
                add(f"  tasks     {', '.join(report['tasks'])}")
            if report.get("last_date"):
                add(f"  last      {report['last_date']}  [{report.get('last_persona','?')}]")
            if report.get("last_summary"):
                add(f"  summary   {report['last_summary']}")
            add("  subcommands: pause · resume · save [label] · context")

    elif cmd == "/export":
        from .sessions.exporter import export_session
        logger = state.get("session_logger")
        if logger and logger.current_session_id:
            out_dir = work_dir / "exports"
            out_dir.mkdir(exist_ok=True)
            from datetime import datetime as _dt
            _name = (state.get("ui").session_name or "codemaid").lower()
            _stamp = _dt.now().strftime("%Y%m%d-%H%M%S")
            out_path = out_dir / f"{_name}-sessions-{_stamp}.html"
            try:
                export_session(logger.storage, logger.current_session_id, out_path)
                add(f"  ✓ Session exported to: [bold]{out_path.relative_to(work_dir)}[/bold]")
            except Exception as e:
                add(f"  error exporting session: {e}", style=THEME["red"])
        else:
            add("  no active session to export", style=THEME["red"])

    elif cmd == "/sessions":
        logger = state.get("session_logger")
        if logger:
            sessions = logger.storage.list_sessions()
            if sessions:
                add("  [bold]Recent Sessions:[/bold]")
                for s in sessions[:10]:
                    add(f"  • {s['session_id']} ({s['started_at']}) - {s['status']}")
            else:
                add("  no sessions found")
        else:
            add("  session storage not available", style=THEME["red"])

    elif cmd in ("/persona", "/profile"):  # /profile kept as alias
        from .skills_loader import build_system_prompt
        from .config import load_config, save_config

        from pathlib import Path

        cfg = load_config()
        profiles_dir = Path(__file__).parent.parent / "profiles"
        personas = [p.stem for p in profiles_dir.glob("*.md")]
        roles = cfg.get("profiles", {})

        if arg:
            # Accept either a role name (thinker) or persona name (qwen-27b)
            role_cfg = roles.get(arg, {})
            persona = role_cfg.get("persona", arg)
            if persona not in personas:
                add(f"  unknown persona '{arg}'. Personas: {', '.join(personas) or '(none)'}  Roles: {', '.join(roles) or '(none)'}", style=THEME["red"])
            else:
                agent.system_prompt = build_system_prompt(profile_name=persona, load_cfg=cfg.get("load", {}))
                agent._current_persona = arg
                cfg["default_profile"] = arg
                save_config(cfg)
                add(f"  persona → [bold]{arg}[/bold] ({persona})")
        else:
            current = getattr(agent, '_current_persona', cfg.get("default_profile", "default"))
            add(f"  persona: [bold]{current}[/bold]")
            if roles:
                add("  roles:")
                for role, rcfg in roles.items():
                    add(f"    {role} — {rcfg.get('persona','?')} via {rcfg.get('provider','?')}")
            add(f"  personas: {', '.join(personas)}")

    elif cmd == "/tools":
        add("\n".join(
            f"  {t['function']['name']} — {t['function']['description'][:55]}"
            for t in TOOLS))

    # ── clipboard ───────────────────────────────────────────────────────────
    elif cmd == "/copy":
        last = next((m["content"] for m in reversed(agent.history)
                     if m["role"] == "assistant"), None)
        if last:
            for clip in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
                try:
                    subprocess.run(clip, input=last.encode(),
                                   check=True, capture_output=True)
                    add("  copied")
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            else:
                add("  no clipboard tool (wl-copy / xclip)", style=THEME["red"])
        else:
            add("  nothing to copy yet")

    # ── history management ──────────────────────────────────────────────────
    elif cmd == "/compress":
        keep = 10
        if len(agent.history) > keep:
            agent.history = agent.history[-keep:]
            add(f"  trimmed to last {keep} messages")
        else:
            add("  history already short")

    elif cmd == "/subcompress":
        n = 0
        for m in agent.history:
            if m.get("role") == "tool" and len(m.get("content", "")) > 500:
                m["content"] = m["content"][:500] + "…[compressed]"
                n += 1
        add(f"  compressed {n} tool outputs")

    elif cmd == "/checkpoint":
        name = agent.checkpoint(arg.strip() or None)
        add(f"  checkpoint '{name}' saved  ({len(agent.list_checkpoints())} total)")

    elif cmd == "/checkpoints":
        names = agent.list_checkpoints()
        add("\n".join(f"  {i+1}. {n}" for i, n in enumerate(names)) if names else "  (none)")

    elif cmd == "/rewind":
        n = int(arg) if arg.isdigit() else 1
        add(f"  rewound {agent.rewind(n)} messages")

    elif cmd == "/restore":
        ref: str | int | None = int(arg) if arg.isdigit() else (arg.strip() or None)
        ok, msg = agent.restore_checkpoint(ref)
        add(f"  {msg}")

    # ── search passthrough ──────────────────────────────────────────────────
    elif cmd == "/focus":
        if arg:
            res = execute_tool("focus", {"pattern": arg}, str(work_dir))
            add(str(res.get("focus_results", res.get("error", res)))[:1000])
        else:
            add("  usage: /focus <pattern>", style=THEME["red"])

    elif cmd == "/grep":
        if arg:
            res = execute_tool("grep",
                {"pattern": arg, "path": str(work_dir)}, str(work_dir))
            add(str(res.get("matches", res.get("error", res)))[:1000])
        else:
            add("  usage: /grep <pattern>", style=THEME["red"])

    else:
        add(f"  unknown command: {cmd}  (try /help)", style=THEME["red"])

    draw()
    return "continue"
