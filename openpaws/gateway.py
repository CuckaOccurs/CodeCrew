"""
OpenPaws Gateway — The bridge between OpenPaws and the world.
Connects your local AI to Telegram, Discord, Slack, and Signal.
"""
import json
import signal
import time
import threading
from pathlib import Path

GATEWAY_DIR = Path.home() / ".config" / "openpaws"
GATEWAY_DIR.mkdir(parents=True, exist_ok=True)

class Gateway:
    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else GATEWAY_DIR / "gateway_config.json"
        self.config = self.load_config()
        self.active_bridges = {}
        self._pid_file = GATEWAY_DIR / "gateway.pid"

    def load_config(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"bridges": {}, "model": "qwen3:14b", "provider": "ollama"}

    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def add_bridge(self, platform, token, **kwargs):
        """Add a messaging bridge configuration."""
        self.config["bridges"][platform] = {
            "token": token,
            "enabled": True,
            "kwargs": kwargs
        }
        self.save_config()
        print(f"✅ Added {platform} bridge configuration.")

    def start_all(self):
        """Start all configured bridges."""
        # Write PID file for stop command
        self._pid_file.write_text(str(threading.get_ident()))

        print("🐱 OpenPaws Gateway starting...")
        print(f"🧠 Model: {self.config['model']} | Provider: {self.config['provider']}")

        for platform, cfg in self.config["bridges"].items():
            if cfg.get("enabled"):
                t = threading.Thread(target=self.run_bridge, args=(platform, cfg), daemon=True)
                t.start()
                self.active_bridges[platform] = t
                print(f"🔗 Connected to {platform}")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Gateway shutting down...")
        finally:
            self._pid_file.unlink(missing_ok=True)

    def stop(self):
        """Stop a running gateway by reading PID file and sending SIGTERM."""
        if self._pid_file.exists():
            try:
                import os as _os
                pid = int(self._pid_file.read_text().strip())
                _os.kill(pid, signal.SIGTERM)
                print("🛑 Gateway stopped.")
                self._pid_file.unlink(missing_ok=True)
            except (ValueError, ProcessLookupError):
                print("🛑 Gateway process not found. Removing stale PID file.")
                self._pid_file.unlink(missing_ok=True)
        else:
            print("🛑 No running gateway found.")

    def run_bridge(self, platform, config):
        """Run a specific bridge adapter."""
        print(f"[{platform.upper()}] Bridge active. Waiting for messages...")
        # Hook in real adapters here (Telegram, Discord, etc.)
        # TODO: Implement actual API polling or webhook logic

    def setup_wizard(self):
        """Interactive wizard to configure the gateway."""
        print("🐾 OpenPaws Gateway Setup Wizard")
        print("Select a platform to configure:")
        platforms = ["Telegram", "Discord", "Slack", "Signal", "Done"]

        for i, p in enumerate(platforms):
            print(f"{i+1}. {p}")

        try:
            choice = int(input("Choice: "))
            platform = platforms[choice-1].lower()

            if platform == "done":
                return

            token = input(f"Enter {platform} Bot Token: ")
            self.add_bridge(platform, token)

        except (ValueError, IndexError):
            print("Invalid choice.")
