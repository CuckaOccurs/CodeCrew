"""
CODEMAID Session Tools — save_session tool + auto_save_history() background function.

auto_save_history() is called by agent.py every AUTO_SAVE_INTERVAL turns.
save_session is an AI-callable tool for on-demand saves.

Saved files land in ~/.agents/sessions/conversations/ as chunked Markdown.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import _audit_log

SAVE_DIR = Path.home() / ".agents" / "sessions" / "conversations"
CHUNK_SIZE = 600  # lines — matches Konsole scrollback limit and agent 600-line rule

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_session",
            "description": (
                "Save the current conversation to the conversations-db archive. "
                "Automatically chunks at 600 lines. Use when a session grows large "
                "or when you want to preserve important context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Short label for the filename, e.g. 'codemaid-audit'. Defaults to 'codemaid'.",
                    },
                },
                "required": [],
            },
        },
    },
]


def _history_to_lines(history: list[dict]) -> list[str]:
    """Render agent message history as readable text lines."""
    lines = []
    for msg in history:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")

        if isinstance(content, list):
            parts = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    args = block.get("input", {})
                    parts.append(f"[tool: {block.get('name')} {args}]")
                elif btype == "tool_result":
                    snippet = str(block.get("content", ""))[:200]
                    parts.append(f"[result: {snippet}]")
            content = "\n".join(parts)

        lines.append(f"### {role}")
        lines.extend(content.splitlines() if content else ["(empty)"])
        lines.append("")
    return lines


def _save_chunks(lines: list[str], label: str) -> list[Path]:
    """Write lines to CHUNK_SIZE-line files. Returns list of saved paths."""
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_label = "".join(c if c.isalnum() or c in "-_" else "-" for c in label).lower()
    saved = []
    total_chunks = max(1, -(-len(lines) // CHUNK_SIZE))  # ceiling division
    for i, start in enumerate(range(0, max(len(lines), 1), CHUNK_SIZE), start=1):
        chunk = lines[start : start + CHUNK_SIZE]
        suffix = f"-chunk{i:02d}of{total_chunks:02d}" if total_chunks > 1 else ""
        path = SAVE_DIR / f"{safe_label}-sessions-{stamp}{suffix}.md"
        path.write_text("\n".join(chunk), encoding="utf-8")
        saved.append(path)
    return saved


def auto_save_history(history: list[dict], label: str = "codemaid") -> None:
    """Background auto-save called by agent.py. Silent — never raises."""
    try:
        if not history:
            return
        lines = _history_to_lines(history)
        saved = _save_chunks(lines, label)
        _audit_log("auto_save_history", label, f"saved {len(saved)} chunk(s)")
    except Exception:
        pass  # Never interrupt the agent for a save failure


def execute(
    name: str,
    args: dict[str, Any],
    work_dir: str | Path,
    **kwargs: Any,
) -> dict[str, Any] | None:
    if name != "save_session":
        return None

    label = args.get("label", "codemaid").strip() or "codemaid"
    label = "".join(c if c.isalnum() or c in "-_" else "-" for c in label)

    # history is injected by agent.py via kwargs when it dispatches this tool
    history = kwargs.get("_history", [])
    lines = _history_to_lines(history) if history else ["(no history available)"]

    try:
        saved = _save_chunks(lines, label)
        _audit_log("save_session", label, f"saved {len(saved)} chunk(s)")
        names = ", ".join(p.name for p in saved)
        return {
            "message": f"✓ Session saved: {len(saved)} chunk(s) → {names}",
            "chunks": len(saved),
            "files": [str(p) for p in saved],
        }
    except Exception as e:
        return {"error": f"save_session failed: {e}"}
