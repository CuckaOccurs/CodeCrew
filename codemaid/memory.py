"""
CODEMAID Memory — Persistent long-term memory for the agent.
Allows the AI to remember facts across sessions and conversations.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MEMORY_DIR = Path.home() / ".config" / "codemaid"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

class Memory:
    def __init__(self, memory_file: str | Path | None = None, work_dir: str | Path | None = None) -> None:
        if memory_file:
            self.memory_file = Path(memory_file)
        else:
            # Project-scoped memory: stored in .agents/codemaid/ in the working dir
            base = Path(work_dir) if work_dir else Path.cwd()
            self.memory_file = base / ".agents" / "codemaid_memory.json"
        self.data: dict[str, Any] = self.load_memory()

    def load_memory(self) -> dict[str, Any]:
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {"facts": [], "summary": "", "last_updated": ""}
        return {"facts": [], "summary": "", "last_updated": ""}

    def save_memory(self) -> None:
        self.data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def add_fact(self, fact: str) -> None:
        """Add a new fact to memory. Caps at 200 facts (FIFO rotation)."""
        self.data["facts"].append(fact)
        if len(self.data["facts"]) > 200:
            self.data["facts"] = self.data["facts"][-200:]
        self.save_memory()

    def get_context(self) -> str:
        """Return a summary of memory to inject into the system prompt."""
        context = "## CODEMAID Memory\n"
        if self.data.get("summary"):
            context += f"**Summary**: {self.data['summary']}\n\n"
        if self.data.get("facts"):
            context += "**Known Facts**:\n"
            # Only show the most recent facts to save context window
            recent = self.data["facts"][-10:]
            for f in recent:
                context += f"- {f}\n"
        return context

    def update_summary(self, summary: str) -> None:
        """Update the high-level summary of the project/user."""
        self.data["summary"] = summary
        self.save_memory()
