"""
CodeCrew Command Center — Interactive Settings & Setup.
Manages the Maid-Mop Network: Personas, Skills, Tools, and Context Rules.
"""
import json
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.text import Text

from codemaid.config import THEME

class Onboarder:
    def __init__(self) -> None:
        self.console = Console()
        self.config_dir = Path.home() / ".config" / "codemaid"
        self.config_path = self.config_dir / "config.json"
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text())
            except: pass
        return {}

    def run(self) -> None:
        self.console.clear()
        self.console.print(Panel(
            Text.assemble(
                ("CODECREW COMMAND CENTER", "bold #7fdbca"),
                "\nManage your AI Crew, MOP settings, and Context Rules.",
            ),
            border_style="#c792ea",
            padding=(1, 3),
        ))

        steps = [
            ("Core MOP Settings (50KB Rule)", self.step_mop),
            ("Crew Management (Personas)",   self.step_personas),
            ("Skill & Tool Access",          self.step_skills),
            ("Network Status & Services",    self.step_network),
            ("Save & Deploy",                self.step_finish),
        ]

        current = 0
        while current < len(steps):
            self._print_menu(steps, current)
            choice = IntPrompt.ask("Select setting to modify (0 to finish)", default=current + 1)
            if choice == 0: break
            if 1 <= choice <= len(steps):
                current = choice - 1
                label, fn = steps[current]
                self.console.rule(f"[bold]{label}[/bold]")
                fn()
                current += 1

    def _print_menu(self, steps, current):
        table = Table(show_header=False, border_style="dim")
        for i, (label, _) in enumerate(steps):
            status = "[green]✓[/green]" if i < current else "[yellow]○[/yellow]"
            table.add_row(f"{i+1}", label, status)
        self.console.print(table)

    def step_mop(self):
        self.console.print("[dim]Configure the Manager of Personas (MOP) context rules.[/dim]")
        # 50KB Rule
        limit = IntPrompt.ask("Context Hard-Cap (bytes)", default=self.config.get("agent", {}).get("context_limit", 50000))
        self.config.setdefault("agent", {})["context_limit"] = limit
        
        # Session Pruning
        prune_days = IntPrompt.ask("Auto-delete sessions older than (days, 0 to disable)", default=30)
        self.config.setdefault("mop", {})["session_prune_days"] = prune_days
        
        self.console.print(f"[green]✓[/green] MOP rules updated: {limit} bytes cap.")

    def step_personas(self):
        persona_dir = Path.home() / ".agents" / "personas"
        personas = list(persona_dir.glob("*.md")) if persona_dir.exists() else []
        
        self.console.print(f"Available Personas in {persona_dir}:")
        for p in personas:
            self.console.print(f"  - {p.stem}")
        
        if Confirm.ask("Create new persona manual?", default=False):
            name = Prompt.ask("New Persona Name")
            role = Prompt.ask("Role/Rank")
            (persona_dir / f"{name}.md").write_text(f"# {name}\nRole: {role}\n\n[Add memories and instructions here]")
            self.console.print(f"[green]✓[/green] Persona {name} created.")

    def step_skills(self):
        # List installed tools and skills
        from codemaid.tools import TOOLS
        table = Table(title="Agent Toolbelt")
        table.add_column("Tool Name", style="cyan")
        table.add_column("Description", style="dim")
        for t in TOOLS:
            name = t.get("function", {}).get("name", "unknown")
            desc = t.get("function", {}).get("description", "")[:50] + "..."
            table.add_row(name, desc)
        self.console.print(table)

    def step_network(self):
        self.console.print("Service Configuration:")
        ollama_host = Prompt.ask("Ollama Host", default=self.config.get("providers", {}).get("ollama", {}).get("host", "http://localhost:11434"))
        self.config.setdefault("providers", {}).setdefault("ollama", {})["host"] = ollama_host
        self.console.print(f"[green]✓[/green] Network target set to {ollama_host}")

    def step_finish(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self.config, indent=2))
        os.chmod(self.config_path, 0o600)
        self.console.print("\n[bold green]Settings Saved to Crew Command Center.[/bold green]")
        self.console.print("Run `codemaid` to deploy the Crew.")

if __name__ == "__main__":
    Onboarder().run()
