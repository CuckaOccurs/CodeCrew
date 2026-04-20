"""
CodeMAID Gateway — The bridge between CodeMAID and the world.
Connects your local AI to Telegram, Discord, Slack, and Signal.
"""
import json
import os
import time
import threading
import subprocess
from pathlib import Path

class Gateway:
    def __init__(self, config_path="gateway_config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.active_bridges = {}

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
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
        print("🐱 CodeMAID Gateway starting...")
        print(f"🧠 Model: {self.config['model']} | Provider: {self.config['provider']}")
        
        for platform, cfg in self.config["bridges"].items():
            if cfg.get("enabled"):
                t = threading.Thread(target=self.run_bridge, args=(platform, cfg))
                t.daemon = True
                t.start()
                self.active_bridges[platform] = t
                print(f"🔗 Connected to {platform}")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Gateway shutting down...")

    def run_bridge(self, platform, config):
        """Run a specific bridge adapter."""
        # This is where we hook in the adapters (Telegram, Discord, etc.)
        # For now, we simulate the connection loop.
        print(f"[{platform.upper()}] Bridge active. Waiting for messages...")
        
        # Placeholder for actual API polling or webhook logic
        # while True:
        #    message = check_for_new_messages(platform, config)
        #    if message:
        #        response = agent.process_message(message)
        #        send_reply(platform, message.chat_id, response)
        pass

    def setup_wizard(self):
        """Interactive wizard to configure the gateway."""
        print("🐾 CodeMAID Gateway Setup Wizard")
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
