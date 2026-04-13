"""OpenPaws — Beautiful terminal AI coding assistant that actually edits files.

Combines Aider's edit system with a clean UI and local LLM support.
Now includes a Gateway for messaging and Persistent Memory.

Usage:
    openpaws .                          # Start in current directory
    openpaws gateway start              # Start the messaging gateway
    openpaws gateway setup              # Configure messaging bridges
    openpaws --model gemma4:latest      # Specific model
    openpaws -p "Create utils.py"       # Non-interactive mode
    openpaws --provider openai          # Use an API model
"""

import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

# Rich for the UI
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.layout import Layout
    from rich.text import Text
    from rich.markdown import Markdown
    from rich.prompt import Prompt
    from rich.theme import Theme
except ImportError:
    print("Error: 'rich' is required. Install with: pip install rich")
    sys.exit(1)

# Import core components
from openpaws.cat import BANNER, random_cat_joke
from openpaws.agent import Agent
from openpaws.tools import execute_tool
from openpaws.provider import get_provider
from openpaws.skills_loader import build_system_prompt
from openpaws.memory import Memory
from openpaws.gateway import Gateway
from openpaws.onboarder import Onboarder

# Register a custom "blinking paw" spinner
from rich.spinner import SPINNERS
if "paw_blink" not in SPINNERS:
    SPINNERS["paw_blink"] = {"frames": ["🐾", "  "], "interval": 150}

console = Console(theme=Theme({
    "panel.border": "#3584e4",
    "panel.title": "#78aeed bold",
    "border": "#5e5c64",
    "title": "#ffffff bold",
    "dim": "#9a9996",
    "white": "#ffffff",
    "bold white": "#ffffff bold",
    "cyan": "#3584e4",
    "bold cyan": "#78aeed bold",
    "bold green": "#26a269 bold",
    "bold yellow": "#f5c211 bold",
    "red": "#e01b24",
    "dim white": "#9a9996",
}))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_banner(work_dir, model, provider_name):
    """Print Qwen Code-style splash screen with cat logo."""
    console.print()
    # Print the banner in plain text to match terminal font
    console.print(BANNER, style="bold white")
    console.print()
    # Info panel
    info_text = (
        f"  [#9a9996]dir[/#9a9996]      [bold #ffffff]{work_dir}[/bold #ffffff]\n"
        f"  [#9a9996]provider[/#9a9996]  [bold #ffffff]{provider_name}[/bold #ffffff]\n"
        f"  [#9a9996]model[/#9a9996]     [bold #ffffff]{model}[/bold #ffffff]\n"
        f"  [#9a9996]tools[/#9a9996]     [bold #ffffff]read, write, edit, grep, run[/bold #ffffff]"
    )
    console.print(Panel(
        info_text,
        border_style="#3584e4",
        padding=(0, 2),
    ))
    console.print()
    console.print("  [#9a9996]type /help or start a conversation[/#9a9996]")
    console.print()


def print_help():
    table = Table(title="Commands", show_header=False)
    table.add_column("Command", style="cyan")
    table.add_column("Description", style="dim")
    table.add_row("/help", "Show this help")
    table.add_row("/cat", "Cat joke 🐱")
    table.add_row("/model", "Show current model")
    table.add_row("/model <name>", "Switch model (e.g., /model qwen3:14b)")
    table.add_row("/provider <name>", "Switch provider (ollama, openai, anthropic)")
    table.add_row("/models", "List available models (Ollama only)")
    table.add_row("/files", "Show files in working directory")
    table.add_row("/clear", "Clear conversation history")
    table.add_row("/exit", "Quit")
    table.add_row("any text", "Ask the AI to write/edit code")
    console.print(table)


def load_config():
    """Auto-load saved config from ~/.config/openpaws/config.json"""
    config_path = Path.home() / ".config" / "openpaws" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}

def main():
    import argparse
    parser = argparse.ArgumentParser(description="OpenPaws — Beautiful AI coding assistant")
    parser.add_argument("dir", nargs="?", default=".", help="Working directory")
    parser.add_argument("--provider", default=None, help="Provider (ollama, openai, anthropic)")
    parser.add_argument("--model", default=None, help="Model name")
    parser.add_argument("--api-key", default=None, help="API Key for cloud providers")
    parser.add_argument("-p", "--prompt", help="Non-interactive prompt")
    parser.add_argument("--host", default=None, help="Ollama host URL")
    
    subparsers = parser.add_subparsers(dest="command")

    # Onboard command
    subparsers.add_parser("onboard", help="Run the first-time setup wizard")

    # Terminal command
    term_parser = subparsers.add_parser("terminal", help="Start the interactive terminal")
    term_parser.add_argument("dir", nargs="?", default=".", help="Working directory")
    term_parser.add_argument("--provider", default=None, help="Provider (ollama, openai, anthropic)")
    term_parser.add_argument("--model", default=None, help="Model name")
    term_parser.add_argument("--api-key", default=None, help="API Key for cloud providers")
    term_parser.add_argument("-p", "--prompt", help="Non-interactive prompt")
    term_parser.add_argument("--host", default=None, help="Ollama host URL")

    # Gateway command
    gw_parser = subparsers.add_parser("gateway", help="Manage the messaging gateway")
    gw_parser.add_argument("action", choices=["start", "setup", "stop"], help="Gateway action")

    args = parser.parse_args()

    # Handle Onboarder
    if args.command == "onboard":
        Onboarder().run()
        return

    # Handle Gateway
    if args.command == "gateway":
        gw = Gateway()
        if args.action == "start":
            gw.start_all()
        elif args.action == "setup":
            gw.setup_wizard()
        elif args.action == "stop":
            print("🛑 Gateway stopped.")
        return

    # Handle Terminal (Default)
    work_dir = Path(getattr(args, 'dir', '.')).resolve() if hasattr(args, 'dir') else Path.cwd()
    
    # Load config, but let CLI flags override it
    saved_config = load_config()
    
    provider_name = args.provider or saved_config.get("provider", "ollama")
    model_name = args.model or saved_config.get("model", "qwen3:14b")
    api_key = args.api_key or saved_config.get("api_key")
    host_url = args.host or "http://localhost:11434"
    prompt_mode = getattr(args, 'prompt', None)

    # Create Provider instance
    try:
        provider = get_provider(
            name=provider_name, 
            model=model_name, 
            host=host_url,
            api_key=api_key
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    # Load Memory and Skills
    memory = Memory()
    system_prompt = build_system_prompt() + "\n\n" + memory.get_context()

    print_banner(str(work_dir), model_name, provider_name)

    # Use the new Agent with the Provider and System Prompt
    agent = Agent(provider, str(work_dir))
    agent.history.append({"role": "system", "content": system_prompt})

    # Non-interactive mode
    if prompt_mode:
        response = agent.chat(prompt_mode)
        console.print()
        console.print(Markdown(response))
        console.print()
        return

    # Interactive mode
    while True:
        try:
            user_input = Prompt.ask("[#3584e4]❯[/#3584e4]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # Commands
        if user_input.startswith("/"):
            cmd = user_input.lower()
            if cmd in ("/exit", "/quit", "/q"):
                console.print("[dim]Goodbye![/dim]")
                break
            elif cmd == "/cat":
                console.print(f"🐾{random_cat_joke()}")
            elif cmd == "/help":
                print_help()
            elif cmd.startswith("/model "):
                # Switch model command
                new_model = user_input.split(" ", 1)[1].strip()
                agent.provider.model = new_model
                agent.history = []  # Clear history to avoid model mismatch
                console.print(f"[green]Switched to model:[/green] [bold]{new_model}[/bold]")
            elif cmd.startswith("/provider "):
                new_provider = user_input.split(" ", 1)[1].strip()
                try:
                    agent.provider = get_provider(name=new_provider, model=agent.provider.model, api_key=agent.provider.api_key)
                    agent.history = []
                    console.print(f"[green]Switched to provider:[/green] [bold]{new_provider}[/bold]")
                except Exception as e:
                    console.print(f"[red]Error switching provider: {e}[/red]")
            elif cmd == "/model":
                console.print(f"Current model: [bold]{agent.provider.model}[/bold]")
            elif cmd == "/provider":
                console.print(f"Current provider: [bold]{agent.provider.__class__.__name__}[/bold]")
            elif cmd == "/models":
                if agent.provider.__class__.__name__ == "OllamaProvider":
                    try:
                        resp = subprocess.run(
                            ["curl", "-s", f"{agent.provider.host}/api/tags"],
                            capture_output=True, text=True, timeout=5
                        )
                        data = json.loads(resp.stdout)
                        models = [m["name"] for m in data.get("models", [])]
                        console.print("Available models:", ", ".join(models) if models else "[dim]none found[/dim]")
                    except (json.JSONDecodeError, OSError) as e:
                        console.print(f"[red]Error listing models: {e}[/red]")
                else:
                    console.print("[dim]Model listing only available for Ollama provider[/dim]")
            elif cmd == "/files":
                files = sorted([f.name for f in work_dir.iterdir() if not f.name.startswith(".")])
                console.print("Files:", ", ".join(files) if files else "[dim]empty[/dim]")
            elif cmd == "/clear":
                agent.history = []
                console.print("[dim]Conversation cleared.[/dim]")
            elif cmd == "/trace":
                agent.trace = not getattr(agent, "trace", False)
                state = "[bold green]ON[/bold green]" if agent.trace else "[dim]OFF[/dim]"
                console.print(f"Trace mode: {state}")
            else:
                console.print(f"[red]Unknown command: {user_input}[/red]")
            continue

        # Chat loop
        with console.status("🐾thinking", spinner="dots", spinner_style="bold red"):
            final_text = agent.chat(user_input)

        console.print()
        console.print(Markdown(final_text))
        console.print()

        if random.randint(1, 20) == 1:
            console.print(f"\n[dim]🐾 {random_cat_joke()}[/dim]")


if __name__ == "__main__":
    main()
