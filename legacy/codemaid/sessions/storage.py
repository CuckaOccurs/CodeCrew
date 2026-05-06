import sqlite3
import json
from pathlib import Path
from datetime import datetime

DEFAULT_DB = Path.home() / ".agents" / "sessions" / "codemaid.db"

class SQLiteStorage:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id   TEXT PRIMARY KEY,
                    agent_id     TEXT,
                    profile      TEXT,
                    summary      TEXT,
                    started_at   TEXT,
                    completed_at TEXT,
                    status       TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id   TEXT,
                    timestamp    TEXT,
                    event_type   TEXT,
                    content      TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                )
            """)
            # Add columns if upgrading from old schema
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN profile TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN summary TEXT")
            except sqlite3.OperationalError:
                pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id   TEXT NOT NULL,
                    text       TEXT NOT NULL,
                    done       INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_todos_agent ON todos(agent_id)")

    def save_session(self, session_id, agent_id, profile=None, status="active"):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, agent_id, profile, started_at, status) VALUES (?, ?, ?, ?, ?)",
                (session_id, agent_id, profile, datetime.now().isoformat(), status)
            )

    def save_event(self, session_id, event_type, content):
        if isinstance(content, (dict, list)):
            content = json.dumps(content)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO events (session_id, timestamp, event_type, content) VALUES (?, ?, ?, ?)",
                (session_id, datetime.now().isoformat(), event_type, content)
            )

    def save_summary(self, session_id, summary):
        if isinstance(summary, dict):
            summary = summary.get("content") or json.dumps(summary)
        elif not isinstance(summary, str):
            summary = str(summary)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sessions SET summary = ? WHERE session_id = ?",
                (summary, session_id)
            )

    def end_session(self, session_id, status="completed"):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sessions SET completed_at = ?, status = ? WHERE session_id = ?",
                (datetime.now().isoformat(), status, session_id)
            )

    def list_sessions(self, limit=20):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()]

    def load_session(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def last_session(self, agent_id=None):
        """Return the most recent completed session, optionally filtered by agent_id."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if agent_id:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE agent_id = ? AND status = 'completed' ORDER BY completed_at DESC LIMIT 1",
                    (agent_id,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE status = 'completed' ORDER BY completed_at DESC LIMIT 1"
                ).fetchone()
            return dict(row) if row else None

    def load_events(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp ASC", (session_id,)
            ).fetchall()
            events = []
            for row in rows:
                d = dict(row)
                try:
                    d["content"] = json.loads(d["content"])
                except (json.JSONDecodeError, TypeError):
                    pass
                events.append(d)
            return events

    def save_todos(self, agent_id: str, todos: list) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM todos WHERE agent_id = ?", (agent_id,))
            conn.executemany(
                "INSERT INTO todos (agent_id, text, done, created_at) VALUES (?, ?, ?, ?)",
                [(agent_id, text, int(done), now) for text, done in todos]
            )

    def load_todos(self, agent_id: str) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT text, done FROM todos WHERE agent_id = ? ORDER BY id ASC",
                (agent_id,)
            ).fetchall()
        return [(row[0], bool(row[1])) for row in rows]

    def reconstruct_history(self, session_id):
        """Rebuild conversation turns from events for context injection."""
        events = self.load_events(session_id)
        messages = []
        for e in events:
            c = e.get("content", {})
            if e["event_type"] == "input":
                messages.append({"role": "user", "content": c.get("text", "")})
            elif e["event_type"] == "output":
                messages.append({"role": "assistant", "content": c.get("text", "")})
        return messages
