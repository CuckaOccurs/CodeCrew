"""
CodeCrew Network Heartbeat — Status Monitor.
Scans skill/tool folders for 'status.json' and aggregates network health.
"""
import json
import threading
import time
from pathlib import Path

class NetworkHeartbeat:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.network_status = {}
        self._lock = threading.Lock()
        self.running = True

    def start(self):
        threading.Thread(target=self._scan_loop, daemon=True).start()

    def _scan_loop(self):
        while self.running:
            new_status = {}
            # Scan all skill directories for status.json
            for skill_dir in self.skills_dir.glob("**/status.json"):
                try:
                    data = json.loads(skill_dir.read_text())
                    new_status[skill_dir.parent.name] = data
                except:
                    continue
            
            with self._lock:
                self.network_status = new_status
            time.sleep(2) # Poll every 2 seconds

    def get_status(self):
        with self._lock:
            return self.network_status
