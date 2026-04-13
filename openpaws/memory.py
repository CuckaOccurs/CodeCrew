"""
OpenPaws Memory — Persistent long-term memory for the agent.
Allows the AI to remember facts across sessions and conversations.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path.home() / ".config" / "openpaws"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

class Memory:
    def __init__(self, memory_file=None):
        self.memory_file = Path(memory_file) if memory_file else MEMORY_DIR / "openpaws_memory.json"
        self.data = self.load_memory()

    def load_memory(self):
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {"facts": [], "summary": "", "last_updated": ""}
        return {"facts": [], "summary": "", "last_updated": ""}

    def save_memory(self):
        self.data["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(self.memory_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def add_fact(self, fact):
        """Add a new fact to memory."""
        self.data["facts"].append(fact)
        self.save_memory()

    def get_context(self):
        """Return a summary of memory to inject into the system prompt."""
        context = "## OpenPaws Memory\n"
        if self.data.get("summary"):
            context += f"**Summary**: {self.data['summary']}\n\n"
        if self.data.get("facts"):
            context += "**Known Facts**:\n"
            # Only show the most recent facts to save context window
            recent = self.data["facts"][-10:]
            for f in recent:
                context += f"- {f}\n"
        return context

    def update_summary(self, summary):
        """Update the high-level summary of the project/user."""
        self.data["summary"] = summary
        self.save_memory()
