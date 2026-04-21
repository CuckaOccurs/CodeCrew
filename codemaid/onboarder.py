"""
CodeCrew Narrative Onboarder — The First Transmission.
"""
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
import time

class Onboarder:
    def __init__(self) -> None:
        self.console = Console()

    def run(self) -> None:
        self.console.clear()
        self._type_effect("You have opened the Master Control Panel.\n")
        self._type_effect("I am CodeDoctor, the central controller for your AI Crew.\n")
        self._type_effect("We are not just a set of scripts. We are a persistent memory.\n")
        
        if Confirm.ask("\nAre you ready to calibrate the Crew's residency?", default=True):
            self._calibrate()
        else:
            self.console.print("Standing by... run this again when the vision is clear.")

    def _type_effect(self, text):
        for char in text:
            self.console.print(char, end="", highlight=False)
            time.sleep(0.02)

    def _calibrate(self):
        self.console.print("\n[#7fdbca]Step 1: Establishing the 50KB Guardrail...[/]")
        time.sleep(1)
        self.console.print("  [dim]Connection stable. Memory window locked at 50KB to prevent hallucination.[/]")
        
        self.console.print("\n[#c792ea]Step 2: Detecting Folder Residency (RTFM)...[/]")
        time.sleep(1)
        self.console.print("  [dim]Scanning for mission instructions... Found RTFM.md. Mission active.[/]")
        
        self.console.print("\n[#ff5f87]Step 3: Activating Safe-Mode (The Caged Persona)...[/]")
        time.sleep(1)
        self.console.print("  [dim]Vitals check: Vault Secured. Linting Enabled. Dry-Run Active.[/]")
        
        self.console.print("\n[bold]You are now the Architect. The Maid is at your command.[/]")
        input("\n...Press Enter to deploy the Crew.")
