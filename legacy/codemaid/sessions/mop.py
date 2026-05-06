"""
MOP — Manager of Personas
CPU-side session controller. No VRAM required.

Responsibilities:
  - Hydrate context from DB before MAID starts inference
  - Run scheduled tasks (auto-save, cleanup) on a turn-count cadence
  - Track and restore persona state across sessions
  - Pause/resume logging without killing the session
"""

import threading
from typing import Callable

from .storage import SQLiteStorage

CHUNK_BYTES = 50 * 1024   # 50 KB hard cap on injected context
MAX_HYDRATE_TURNS = 20    # how many prior turns to consider for context


class MOPController:
    def __init__(self, agent_id: str, storage: SQLiteStorage | None = None):
        self.agent_id = agent_id
        self.storage = storage or SQLiteStorage()
        self._tasks: list[dict] = []
        self._lock = threading.Lock()
        self._paused = False
        self._context_injected: str = ""
        self._last_session_cache: dict | None = None
        self._cache_loaded = False

    # ── Last session cache ───────────────────────────────────────────────────

    def _get_last_session(self) -> dict | None:
        if not self._cache_loaded:
            self._last_session_cache = self.storage.last_session(self.agent_id)
            self._cache_loaded = True
        return self._last_session_cache

    # ── Context hydration ────────────────────────────────────────────────────

    def hydrate(self) -> str:
        """
        Pull last session's summary + recent turns from DB.
        Returns a string ready to append to the system prompt.
        Respects 50 KB hard cap so small models never overflow.
        Never raises.
        """
        try:
            last = self._get_last_session()
            if not last:
                return ""

            date = last.get("started_at", "")[:10]
            parts = [f"## Previous session ({date})"]

            summary = (last.get("summary") or "").strip()
            if summary:
                parts.append(summary)

            history = self.storage.reconstruct_history(last["session_id"])
            byte_budget = CHUNK_BYTES - sum(len(p.encode()) for p in parts)
            recent: list[str] = []
            for msg in reversed(history[-MAX_HYDRATE_TURNS:]):
                line = f"**{msg['role'].upper()}:** {msg['content']}"
                cost = len(line.encode()) + 1
                if cost > byte_budget:
                    break
                byte_budget -= cost
                recent.append(line)
            recent.reverse()

            if recent:
                parts.append("\n### Recent turns")
                parts.extend(recent)

            self._context_injected = "\n".join(parts)
            return self._context_injected
        except Exception:
            return ""

    def last_persona(self) -> str | None:
        """Return persona name used in the last session."""
        try:
            return (self._get_last_session() or {}).get("profile")
        except Exception:
            return None

    @property
    def injected_context(self) -> str:
        """The hydrated context string injected into the system prompt this session."""
        return self._context_injected

    # ── Scheduled tasks ──────────────────────────────────────────────────────

    def schedule(self, name: str, every_n_turns: int, fn: Callable) -> None:
        """Register a CPU-side task to run every N turns."""
        with self._lock:
            self._tasks.append({"name": name, "interval": every_n_turns, "fn": fn, "last": 0})

    def tick(self, turn: int) -> None:
        """Call once per agent turn. Fires any due tasks. Skips if paused."""
        if self._paused or turn == 0:
            return
        with self._lock:
            tasks = list(self._tasks)

        executed = []
        for t in tasks:
            if turn % t["interval"] == 0:
                try:
                    t["fn"]()
                    executed.append(t)
                except Exception:
                    pass

        if executed:
            with self._lock:
                for t in executed:
                    t["last"] = turn

    # ── Pause / resume ───────────────────────────────────────────────────────

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ── Persistent todos ─────────────────────────────────────────────────────

    def load_todos(self) -> list[tuple[str, bool]]:
        """Return todo list from DB, carried forward from last session."""
        try:
            return self.storage.load_todos(self.agent_id)
        except Exception:
            return []

    def save_todos(self, todos: list[tuple[str, bool]]) -> None:
        """Persist current todo list so next session picks it up."""
        try:
            self.storage.save_todos(self.agent_id, todos)
        except Exception:
            pass

    # ── Status ───────────────────────────────────────────────────────────────

    def report(self, current_session_id: str | None = None) -> dict:
        """Return a status dict for /session display."""
        out: dict = {
            "current": current_session_id,
            "paused": self._paused,
            "tasks": [f"{t['name']} every {t['interval']} turns" for t in self._tasks],
            "context_bytes": len(self._context_injected.encode()),
        }
        try:
            last = self._get_last_session()
            if last:
                out["last_id"] = last["session_id"]
                out["last_date"] = last.get("started_at", "")[:16].replace("T", " ")
                out["last_persona"] = last.get("profile") or "default"
                snippet = (last.get("summary") or "").strip()
                out["last_summary"] = snippet[:120] + ("…" if len(snippet) > 120 else "")
        except Exception:
            pass
        return out
