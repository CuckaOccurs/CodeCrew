"""
CODEMAID CLI — Theme constants, console, config loader, and static helpers.
"""

import io
import json
from pathlib import Path
from typing import Any

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich.theme import Theme
except ImportError:
    import sys
    print("Error: 'rich' is required. Install with: pip install rich")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

THEME = {
    "blue":      "#c792ea",   # lavender purple
    "dark_blue": "#7e57c2",   # deeper purple
    "purple":    "#82aaff",   # periwinkle
    "teal":      "#7fdbca",   # muted mint
    "red":       "#ff5874",   # soft pink-red
    "pink":      "#ff869a",   # dusty pink
    "white":     "#d6deeb",   # Night Owl foreground
    "dim":       "#4b6479",   # blue-grey dim
    "green":     "#addb67",   # muted yellow-green
    "brown":     "#ecc48d",   # warm sand
}

console = Console(theme=Theme({
    "panel.border": THEME["teal"],
    "cyan":         THEME["teal"],
    "bold cyan":    THEME["teal"] + " bold",
    "red":          THEME["red"],
    "green":        THEME["green"],
    "yellow":       THEME["brown"],
    "dim":          THEME["dim"],
    "info":         THEME["purple"],
}))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render(renderable: Any, width: int | None = None, end: str = "\n",
            style: str | None = None) -> str:
    """Render any Rich renderable to an ANSI string via a throw-away console."""
    buf = io.StringIO()
    c = Console(file=buf, force_terminal=True,
                width=width or console.width,
                highlight=False, soft_wrap=True)
    c.print(renderable, end=end, style=style or "default")
    return buf.getvalue()


def _tool_label(name: str, args: dict) -> str:
    lm = {
        "read_file":     lambda a: f"reading   {a.get('path','?')}",
        "write_file":    lambda a: f"writing   {a.get('path','?')}",
        "edit_file":     lambda a: f"editing   {a.get('path','?')}",
        "run_command":   lambda a: f"running   {str(a.get('command','?'))[:48]}",
        "grep":          lambda a: f"grep      {a.get('pattern','?')}",
        "focus":         lambda a: f"focus     {a.get('pattern','?')}",
        "web_search":    lambda a: f"search    {a.get('query','?')[:38]}",
        "web_scrape":    lambda a: f"scrape    {a.get('url','?')[:38]}",
        "git_status":    lambda _: "git status",
        "git_diff":      lambda _: "git diff",
        "git_add":       lambda a: f"git add   {a.get('files','?')}",
        "git_commit":    lambda a: f"git commit {a.get('message','?')[:28]}",
        "git_log":       lambda _: "git log",
        "list_dir":      lambda a: f"ls        {a.get('path','.')}",
        "read_multiple": lambda _: "reading multiple files",
        "edit_plan":     lambda a: f"planning  {len(a.get('edits', []))} files",
    }
    fn = lm.get(name)
    try:
        return fn(args) if fn else name
    except Exception:
        return name


def _build_help_table() -> "Table":
    t = Table(show_header=False, border_style=THEME["dim"], padding=(0, 2))
    t.add_column(style=f"bold {THEME['blue']}", no_wrap=True)
    t.add_column(style=THEME["dim"])
    for cmd, desc in [
        ("/help",            "This list"),
        ("/config",          "View or set configuration"),
        ("/lean",            "Toggle Lean Mode (prune context)"),
        ("/cat",             "Cat joke"),
        ("/model [name]",    "Show or switch model"),
        ("/provider [name]", "Show or switch provider"),
        ("/models",          "List Ollama models"),
        ("/files",           "List working directory"),
        ("/clear",           "Clear conversation"),
        ("/trace",           "Toggle trace mode"),
        ("/copy",            "Copy last response to clipboard"),
        ("/compress",        "Trim conversation history"),
        ("/subcompress",     "Compress large tool outputs"),
        ("/stats",           "Session statistics"),
        ("/tools",           "List available tools"),
        ("/about",           "Version and config"),
        ("/loaded",          "Show loaded context: instructions, rules, skills, dicts"),
        ("/persona [name]",   "Show or switch MOP persona"),
        ("/plan",            "Toggle plan mode"),
        ("/autocommit",      "Toggle auto-commit on edits"),
        ("/vault",           "Toggle command vault"),
        ("/allowlist",       "Toggle vault allowlist/denylist mode"),
        ("/rewind [n]",      "Step back N turns (default 1)"),
        ("/checkpoint",      "Save a checkpoint"),
        ("/restore [n]",     "Restore from checkpoint"),
        ("/focus <pat>",     "Deep-search codebase"),
        ("/grep <pat>",      "Grep files for pattern"),
        ("!cmd",             "Run shell command"),
        ("@file [text]",     "Inject file into prompt"),
        ("/exit",            "Quit"),
    ]:
        t.add_row(cmd, desc)
    return t


# ---------------------------------------------------------------------------
# ANSI color shortcuts (raw escape codes for non-Rich rendering)
# ---------------------------------------------------------------------------
_A = "\033[38;2;199;146;234m"  # lavender purple
_T = "\033[38;2;127;219;202m"  # muted mint teal
_I = "\033[38;2;130;170;255m"  # soft periwinkle
_G = "\033[38;2;173;219;103m"  # muted yellow-green  — ON
_R = "\033[38;2;255;88;116m"   # soft pink-red        — OFF / blocked
_Y = "\033[38;2;255;188;66m"   # warm amber           — warning
_P = "\033[38;2;255;134;154m"  # dusty pink
_D = "\033[38;2;75;100;121m"   # blue-grey            — dim
_Z = "\033[0m"

# ---------------------------------------------------------------------------

_CONFIG_PATH = Path.home() / ".config" / "codemaid" / "config.json"

def load_config() -> dict[str, Any]:
    if _CONFIG_PATH.exists():
        try:
            return json.loads(_CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}

def save_config(cfg: dict[str, Any]) -> None:
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    except OSError:
        pass

def update_config_path(key_path: str, value: Any) -> bool:
    """Update a nested config key using dot notation (e.g. 'provider_defaults.ollama')."""
    cfg = load_config()
    parts = key_path.split(".")
    target = cfg
    for part in parts[:-1]:
        if part not in target or not isinstance(target[part], dict):
            target[part] = {}
        target = target[part]
    
    # Try to parse value as JSON if it looks like a dict/list
    if isinstance(value, str):
        if (value.startswith("{") and value.endswith("}")) or (value.startswith("[") and value.endswith("]")):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
    
    target[parts[-1]] = value
    save_config(cfg)
    return True
