"""
CodeMAID Onboarder — Clean, local-first setup wizard.
No telemetry, no cloud phoning, no paywalls. Just your machine, your data, your rules.
"""
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from pathlib import Path
import json
import os

class Onboarder:
    def __init__(self):
        self.console = Console()
        self.config = {}

    def run(self):
        self.console.print()
        self.console.print("[bold #3584e4]  ___   ____ ______ ___   _      /\\_/\\")
        self.console.print("[bold #3584e4] / _ \\ |  _ \\| ___| |\\ \\ | |    ( o.o )")
        self.console.print("[bold #3584e4]| | | || |_) |  _|  | \\ \\| |    (> ^ <)")
        self.console.print("[bold #3584e4]| |_| ||  __/| |___ | |\\   |    /|   |\\")
        self.console.print("[bold #3584e4] \\___/ |_|   |_____|| | \\__|   (_|   |_)")
        self.console.print()
        
        self.console.print(Panel(
            "[bold #ffffff]Welcome to CodeMAID[/bold #ffffff]\n\n"
            "[dim #9a9996]CodeMAID is 100% free, open-source, and runs entirely on your machine. "
            "No telemetry, no tracking, no paywalls. Just a powerful local AI assistant that respects your privacy.\n\n"
            "We're building this to prove you don't need a big studio—just the right tools and the right mindset.[/dim #9a9996]",
            border_style="#3584e4",
            padding=(1, 2)
        ))

        if not Confirm.ask("\n[yellow]Shall we set things up?[/yellow]", default=True):
            self.console.print("[dim]No problem. You can run `codemaid onboard` anytime.[/dim]")
            return

        self.step_provider()
        self.step_gateway()
        self.step_skills()
        self.step_finish()

    def step_provider(self):
        self.console.print("\n[bold #3584e4]Step 1: Choose your AI Provider[/bold #3584e4]")
        choice = Prompt.ask(
            "How would you like to run models?",
            choices=["ollama (local)", "openai (api)", "anthropic (api)"],
            default="ollama (local)"
        )
        provider = choice.split(" ")[0]
        self.config["provider"] = provider
        
        if provider == "ollama":
            self.config["model"] = Prompt.ask("Default local model", default="qwen3:14b")
            self.console.print(f"✅ Provider set to [cyan]{provider}[/cyan] (Model: [bold]{self.config['model']}[/bold])")
        else:
            api_key = Prompt.ask(f"Enter {provider.title()} API key", password=True)
            self.config["api_key"] = api_key
            default_model = "gpt-4o" if provider == "openai" else "claude-sonnet-4-20250514"
            self.config["model"] = Prompt.ask("Default API model", default=default_model)
            self.console.print(f"✅ Provider set to [cyan]{provider}[/cyan] (Model: [bold]{self.config['model']}[/bold])")

    def step_gateway(self):
        self.console.print("\n[bold #3584e4]Step 2: Messaging Gateway (Optional)[/bold #3584e4]")
        self.console.print("[dim]Connect CodeMAID to Telegram, Discord, or Slack so you can chat with your AI from anywhere.[/dim]")
        if Confirm.ask("Enable messaging gateway?", default=False):
            platform = Prompt.ask("Which platform?", choices=["telegram", "discord", "slack"], default="telegram")
            token = Prompt.ask(f"Enter your {platform} bot token", password=True)
            self.config["gateway"] = {"platform": platform, "token": token, "enabled": True}
            self.console.print(f"✅ [cyan]{platform.title()}[/cyan] gateway configured.")
        else:
            self.config["gateway"] = None
            self.console.print("[dim]Skipped. You can always configure this later.[/dim]")

    def step_skills(self):
        self.console.print("\n[bold #3584e4]Step 3: Skills & Memory[/bold #3584e4]")
        skills_dir = Path.home() / ".agents" / "skills"
        if skills_dir.exists():
            count = len([d for d in skills_dir.iterdir() if d.is_dir()])
            self.console.print(f"✅ Found [bold]{count}[/bold] existing skills in your library.")
        
        if Confirm.ask("Enable persistent memory across sessions?", default=True):
            self.config["memory"] = True
            self.console.print("✅ Persistent memory enabled.")
        else:
            self.config["memory"] = False
            self.console.print("[dim]Skipped. Agent will run statelessly.[/dim]")

    def step_finish(self):
        self.console.print("\n[bold #3584e4]Step 4: Save Configuration[/bold #3584e4]")
        config_dir = Path.home() / ".config" / "codemaid"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.json"
        
        with open(config_path, "w") as f:
            json.dump(self.config, f, indent=2)

        self.console.print(f"✅ Configuration saved to [cyan]{config_path}[/cyan]")
        self.console.print(Panel(
            "[dim #9a9996]💖 CodeMAID is free forever. If you ever want to support the project, "
            "donations are welcome but never required. We build this because it needs to exist.[/dim #9a9996]",
            border_style="#26a269"
        ))
        self.console.print("\n[bold #26a269]🐱 All set! Run `codemaid .` to start.[/bold #26a269]\n")
