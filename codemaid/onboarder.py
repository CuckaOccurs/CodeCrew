"""
CODEMAID Onboarder — Full menu-based setup wizard with intro animation.
No telemetry, no cloud phoning, no paywalls. Just your machine, your data, your rules.
"""
import json
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.text import Text

from codemaid.cat import print_maid


# ─── Provider default models ────────────────────────────────────────────────
_PROVIDER_DEFAULTS = {
    "ollama":    ("qwen3:14b",                    None),
    "openai":    ("gpt-4o",                       "OPENAI_API_KEY"),
    "anthropic": ("claude-sonnet-4-6",            "ANTHROPIC_API_KEY"),
    "groq":      ("llama-3.3-70b-versatile",      "GROQ_API_KEY"),
    "gemini":    ("gemini-2.0-flash",             "GEMINI_API_KEY"),
    "openwebui": ("llama3.2",                     None),
}


class Onboarder:
    def __init__(self) -> None:
        self.console = Console()
        self.config: dict = {}

    def run(self) -> None:
        # 1. Intro animation
        print_maid()
        input("  press enter to begin setup...")

        self.console.clear()
        self._print_welcome()

        if not Confirm.ask("\n[yellow]Ready to set things up?[/yellow]", default=True):
            self.console.print("[dim]No worries. Run `maid onboard` any time.[/dim]")
            return

        # 2. Main menu loop
        steps = [
            ("AI Provider",        self.step_provider),
            ("Model Settings",     self.step_model),
            ("Profiles",           self.step_profiles),
            ("Messaging Gateway",  self.step_gateway),
            ("Skills & Memory",    self.step_skills),
            ("Vault Security",     self.step_vault),
            ("Finish & Save",      self.step_finish),
        ]

        current = 0
        while current < len(steps):
            self.console.print()
            self._print_menu(steps, current)
            choice = IntPrompt.ask(
                "Choose a step (or 0 to skip to finish)",
                default=current + 1
            )
            if choice == 0:
                current = len(steps) - 1
            elif 1 <= choice <= len(steps):
                current = choice - 1
            else:
                continue

            label, fn = steps[current]
            self.console.rule(f"[bold #3584e4]{label}[/bold #3584e4]")
            fn()
            current += 1

    # ─── Welcome screen ───────────────────────────────────────────────────────

    def _print_welcome(self) -> None:
        self.console.print()
        self.console.print(Panel(
            Text.assemble(
                ("CODEMAID", "bold #3584e4"),
                "  —  local-first AI assistant\n\n",
                ("100% free · open source · zero telemetry · runs on your machine\n", "dim"),
                ("Your data stays here. Always.", "bold #26a269"),
            ),
            border_style="#9141ac",
            padding=(1, 3),
        ))

    def _print_menu(self, steps: list, current: int) -> None:
        table = Table(show_header=False, border_style="dim", padding=(0, 2))
        table.add_column("#", style="dim", width=3)
        table.add_column("Step")
        table.add_column("Status", justify="right")
        for i, (label, _) in enumerate(steps):
            num   = str(i + 1)
            done  = i < current
            arrow = "→" if i == current else " "
            style = "bold #3584e4" if i == current else ("dim" if done else "")
            status = "[green]✓[/green]" if done else ("[yellow]…[/yellow]" if i == current else "")
            table.add_row(f"{arrow}{num}", f"[{style}]{label}[/{style}]" if style else label, status)
        self.console.print(table)

    # ─── Steps ───────────────────────────────────────────────────────────────

    def step_provider(self) -> None:
        self.console.print("[dim]Choose how CODEMAID talks to an AI model.[/dim]\n")
        providers = list(_PROVIDER_DEFAULTS.keys())
        for i, p in enumerate(providers, 1):
            model, env = _PROVIDER_DEFAULTS[p]
            local_tag = "[green]local[/green]" if env is None else "[yellow]api key[/yellow]"
            self.console.print(f"  [cyan]{i}.[/cyan] {p:<12} {local_tag}  default model: {model}")

        idx = IntPrompt.ask("\nChoice", default=1)
        provider = providers[max(0, min(idx - 1, len(providers) - 1))]
        self.config["provider"] = provider
        _, env_var = _PROVIDER_DEFAULTS[provider]

        if provider == "openwebui":
            host = Prompt.ask("OpenWebUI host", default="http://localhost:3000")
            self.config["host"] = host

        if env_var:
            existing = os.environ.get(env_var, "")
            if existing:
                self.console.print(f"[green]✓[/green] Found {env_var} in environment.")
                self.config["api_key"] = existing
            else:
                key = Prompt.ask(f"Enter {env_var}", password=True)
                self.config["api_key"] = key

        self.console.print(f"[green]✓[/green] Provider: [cyan]{provider}[/cyan]")

    def step_model(self) -> None:
        provider  = self.config.get("provider", "ollama")
        default_m = _PROVIDER_DEFAULTS.get(provider, ("",))[0]

        if provider == "ollama":
            # Try to list available models
            try:
                import requests
                host = self.config.get("host", "http://localhost:11434")
                resp = requests.get(f"{host}/api/tags", timeout=3).json()
                models = [m["name"] for m in resp.get("models", [])]
                if models:
                    self.console.print("Available Ollama models:")
                    for i, m in enumerate(models, 1):
                        self.console.print(f"  [cyan]{i}.[/cyan] {m}")
            except Exception:
                models = []

        model = Prompt.ask("Default model", default=default_m)
        self.config["model"] = model
        self.console.print(f"[green]✓[/green] Model: [cyan]{model}[/cyan]")

    def step_profiles(self) -> None:
        self.console.print(
            "[dim]Profiles let you switch between different provider/model combos instantly.\n"
            "Example: --profile claude, --profile groq-fast, --profile local-big[/dim]\n"
        )
        profiles: dict = self.config.get("profiles", {})
        adding = True
        while adding:
            if not Confirm.ask("Add a profile?", default=len(profiles) == 0):
                break
            name     = Prompt.ask("Profile name (e.g. 'claude', 'groq-fast')")
            provider = Prompt.ask("Provider", default=self.config.get("provider", "ollama"))
            model    = Prompt.ask("Model",    default=self.config.get("model", ""))
            api_key  = ""
            _, env_var = _PROVIDER_DEFAULTS.get(provider, (None, None))
            if env_var:
                api_key = Prompt.ask(f"API key for {provider} (leave blank to use env var)", default="", password=True)
            profiles[name] = {"provider": provider, "model": model}
            if api_key:
                profiles[name]["api_key"] = api_key
            self.console.print(f"[green]✓[/green] Profile '[cyan]{name}[/cyan]' added.")

        if profiles:
            self.config["profiles"] = profiles
            self.console.print(f"[green]✓[/green] {len(profiles)} profile(s) saved.")

    def step_gateway(self) -> None:
        self.console.print("[dim]Connect CODEMAID to Telegram, Discord, Slack, or Signal.[/dim]\n")
        if not Confirm.ask("Configure a messaging gateway?", default=False):
            self.console.print("[dim]Skipped. Run `maid gateway setup` later.[/dim]")
            return
        platform = Prompt.ask("Platform", choices=["telegram", "discord", "slack", "signal"], default="telegram")
        token    = Prompt.ask(f"{platform.title()} bot token", password=True)
        self.config["gateway"] = {"platform": platform, "enabled": True}
        # Save token separately to gateway_config.json (not main config)
        gw_dir  = Path.home() / ".config" / "codemaid"
        gw_dir.mkdir(parents=True, exist_ok=True)
        gw_path = gw_dir / "gateway_config.json"
        gw_cfg  = json.loads(gw_path.read_text()) if gw_path.exists() else {"bridges": {}}
        gw_cfg["bridges"][platform] = {"token": token, "enabled": True}
        gw_path.write_text(json.dumps(gw_cfg, indent=2))
        os.chmod(gw_path, 0o600)
        self.console.print(f"[green]✓[/green] [cyan]{platform.title()}[/cyan] gateway configured.")

    def step_skills(self) -> None:
        skills_dir = Path.home() / ".agents" / "skills"
        count = len([d for d in skills_dir.iterdir() if d.is_dir()]) if skills_dir.exists() else 0
        self.console.print(f"[dim]Skills extend what CODEMAID can do. Currently: {count} installed.[/dim]\n")
        self.config["memory"] = Confirm.ask("Enable persistent memory across sessions?", default=True)
        status = "[green]enabled[/green]" if self.config["memory"] else "[dim]disabled[/dim]"
        self.console.print(f"[green]✓[/green] Memory: {status}")

    def step_vault(self) -> None:
        self.console.print("[dim]Vault is CODEMAID's command safety system.[/dim]\n")
        self.console.print("  [cyan]denylist[/cyan]  — blocks known-dangerous commands, allows everything else (default)")
        self.console.print("  [cyan]allowlist[/cyan] — only allows explicitly safe commands (stricter)\n")
        mode = Prompt.ask("Default safety mode", choices=["denylist", "allowlist"], default="denylist")
        self.config["vault_mode"] = mode
        self.console.print(f"[green]✓[/green] Vault: [cyan]{mode}[/cyan]")

    def step_finish(self) -> None:
        config_dir = Path.home() / ".config" / "codemaid"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.json"

        # Preserve any existing keys not set in this session
        existing: dict = {}
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text())
            except Exception:
                pass
        existing.update(self.config)

        config_path.write_text(json.dumps(existing, indent=2))
        os.chmod(config_path, 0o600)

        self.console.print(f"\n[green]✓[/green] Config saved → [cyan]{config_path}[/cyan]")

        # Summary table
        table = Table(title="Your CODEMAID Config", border_style="#3584e4")
        table.add_column("Setting", style="dim")
        table.add_column("Value",   style="cyan")
        for k, v in existing.items():
            if k == "api_key":
                v = f"{str(v)[:4]}****"
            elif k == "profiles" and isinstance(v, dict):
                v = ", ".join(v.keys())
            table.add_row(k, str(v))
        self.console.print(table)

        self.console.print(Panel(
            "[dim]CODEMAID is free forever. Built because it needs to exist.\n"
            "Donations welcome, never required.[/dim]",
            border_style="#26a269",
        ))
        self.console.print("\n[bold #26a269]All set. Run `maid .` to start.[/bold #26a269]\n")
