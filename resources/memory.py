"""
CodeMAID Memory — Persistent long-term memory for the agent.
Allows the AI to remember facts across sessions and conversations.
"""
import json
import os
from datetime import datetime
from pathlib import Path

class Memory:
    def __init__(self, memory_file="codemaid_memory.json"):
        self.memory_file = memory_file
        self.data = self.load_memory()

    def load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except:
                return {"facts": [], "summary": "", "last_updated": ""}
        return {"facts": [], "summary": "", "last_updated": ""}

    def save_memory(self):
        self.data["last_updated"] = datetime.now().isoformat()
        with open(self.memory_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def add_fact(self, fact):
        """Add a new fact to memory."""
        self.data["facts"].append(fact)
        self.save_memory()

    def get_context(self):
        """Return a summary of memory to inject into the system prompt."""
        context = "## CodeMAID Memory\n"
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
