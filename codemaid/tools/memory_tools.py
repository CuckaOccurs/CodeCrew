"""
CODEMAID Memory Tools — remember_fact, update_memory_summary, list_skills.
"""

from pathlib import Path
from typing import Any

from .common import _audit_log

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Save a fact to persistent memory. Use this when the user tells you something important to remember.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to remember."},
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_memory_summary",
            "description": "Update the high-level project summary in persistent memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "The new project summary."},
                },
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "List all special skills and capabilities currently loaded by CODEMAID.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def execute(name: str, args: dict[str, Any], work_dir: str | Path, **kwargs: Any) -> dict[str, Any] | None:
    """Execute a memory tool. Returns result dict or None if name not handled."""

    if name == "remember_fact":
        from codemaid.memory import Memory
        mem = Memory(work_dir=work_dir)
        mem.add_fact(args.get("fact", ""))
        _audit_log("remember_fact", args.get("fact", "")[:80], "ok")
        return {"message": f"✓ Fact remembered. {len(mem.data['facts'])} facts stored."}

    elif name == "update_memory_summary":
        from codemaid.memory import Memory
        mem = Memory(work_dir=work_dir)
        mem.update_summary(args.get("summary", ""))
        _audit_log("update_memory_summary", args.get("summary", "")[:80], "ok")
        return {"message": "✓ Memory summary updated."}

    elif name == "list_skills":
        return {"message": "Skills are loaded into the system prompt. Check the 'Currently Loaded Skills' section."}

    return None
