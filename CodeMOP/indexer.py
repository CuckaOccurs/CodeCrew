# CodeMOP — Indexer
# Watches session directories.
# Parses new files using connectors.
# Stores results in SQLite.
# Bridge between raw session files
# and structured memory.

from pathlib import Path
import sqlite3
import json
import logging
import hashlib
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from codemop import (
    APP_ROOT,
    SESSIONS_DIR,
    DB_PATH,
    load_config,
)
from codemop.connectors import ConnectorRegistry

log = logging.getLogger("codemop.indexer")

# ── Schema ────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    path TEXT UNIQUE NOT NULL,
    profile TEXT,
    model TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id),
    filename TEXT NOT NULL,
    filepath TEXT UNIQUE NOT NULL,
    file_hash TEXT,
    tool TEXT,
    model TEXT,
    profile TEXT,
    outcome TEXT,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parsed_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id),
    session_id INTEGER REFERENCES sessions(id),
    decision TEXT NOT NULL,
    context TEXT,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS dead_ends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id),
    session_id INTEGER REFERENCES sessions(id),
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_project
    ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_decisions_project
    ON decisions(project_id);
CREATE INDEX IF NOT EXISTS idx_decisions_verified
    ON decisions(verified);
"""


class Database:
    """
    Thin SQLite wrapper.
    Handles connection, schema, operations.
    """

    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(SCHEMA)
        log.debug("Database initialized")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ── Projects ──────────────────────────────────────
    def get_or_create_project(self,
                               name: str,
                               path: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM projects "
                "WHERE path = ?",
                (path,)).fetchone()

            if row:
                conn.execute(
                    "UPDATE projects SET "
                    "last_accessed = ? "
                    "WHERE id = ?",
                    (datetime.now(), row["id"]))
                return row["id"]

            cursor = conn.execute(
                "INSERT INTO projects "
                "(name, path) VALUES (?, ?)",
                (name, path))
            log.info(
                f"Registered project: {name}")
            return cursor.lastrowid

    def list_projects(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects "
                "ORDER BY last_accessed DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Sessions ──────────────────────────────────────
    def session_exists(self,
                       filepath: str,
                       file_hash: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT file_hash FROM sessions "
                "WHERE filepath = ?",
                (filepath,)).fetchone()

            if not row:
                return False
            return row["file_hash"] == file_hash

    def register_session(self,
                         project_id: int,
                         parsed: dict,
                         file_hash: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sessions
                (project_id, filename, filepath,
                 file_hash, tool, model, profile,
                 outcome, parsed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    tool = excluded.tool,
                    model = excluded.model,
                    outcome = excluded.outcome,
                    parsed_at = excluded.parsed_at
                """,
                (
                    project_id,
                    Path(parsed["filepath"]).name,
                    parsed["filepath"],
                    file_hash,
                    parsed.get("tool", "unknown"),
                    parsed.get("model", "unknown"),
                    parsed.get("profile", ""),
                    parsed.get(
                        "outcome", "unknown"),
                    datetime.now()
                ))
            return cursor.lastrowid

    def list_sessions(self,
                      project_id: int = None,
                      verified_only: bool = False
                      ) -> list:
        with self._connect() as conn:
            query = "SELECT * FROM sessions"
            params = []
            conditions = []

            if project_id:
                conditions.append(
                    "project_id = ?")
                params.append(project_id)

            if verified_only:
                conditions.append(
                    "verified = TRUE")

            if conditions:
                query += (" WHERE " +
                          " AND ".join(conditions))

            query += " ORDER BY created_at DESC"

            rows = conn.execute(
                query, params).fetchall()
            return [dict(r) for r in rows]

    # ── Decisions ─────────────────────────────────────
    def store_decisions(self,
                        project_id: int,
                        session_id: int,
                        decisions: list):
        if not decisions:
            return

        with self._connect() as conn:
            for d in decisions:
                existing = conn.execute(
                    "SELECT id FROM decisions "
                    "WHERE project_id = ? "
                    "AND decision = ?",
                    (project_id,
                     d.get("decision", ""))
                ).fetchone()

                if existing:
                    continue

                conn.execute(
                    """
                    INSERT INTO decisions
                    (project_id, session_id,
                     decision, context, verified)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        session_id,
                        d.get("decision", ""),
                        d.get("context", ""),
                        d.get("verified", False)
                    ))

        log.info(
            f"Stored {len(decisions)} decisions")

    def store_dead_ends(self,
                        project_id: int,
                        session_id: int,
                        dead_ends: list):
        if not dead_ends:
            return

        with self._connect() as conn:
            for d in dead_ends:
                conn.execute(
                    """
                    INSERT INTO dead_ends
                    (project_id, session_id,
                     description)
                    VALUES (?, ?, ?)
                    """,
                    (project_id,
                     session_id, d))

    def get_decisions(self,
                      project_id: int,
                      verified_only: bool = True
                      ) -> list:
        with self._connect() as conn:
            query = (
                "SELECT * FROM decisions "
                "WHERE project_id = ?")
            params = [project_id]

            if verified_only:
                query += " AND verified = TRUE"

            query += " ORDER BY created_at DESC"

            rows = conn.execute(
                query, params).fetchall()
            return [dict(r) for r in rows]

    def vacuum(self):
        with self._connect() as conn:
            conn.execute("VACUUM")
            conn.execute("REINDEX")
        log.info("Database vacuumed")


# ── File watcher ──────────────────────────────────────
class SessionHandler(FileSystemEventHandler):

    def __init__(self, indexer):
        self.indexer = indexer
        super().__init__()

    def on_created(self, event):
        if not event.is_directory:
            self.indexer.process_file(
                Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            self.indexer.process_file(
                Path(event.src_path))


# ── Main indexer ──────────────────────────────────────
class Indexer:

    SUPPORTED_EXTENSIONS = {
        ".html", ".jsonl",
        ".md", ".txt", ".log"
    }

    def __init__(self):
        self.config = load_config()
        self.db = Database()
        self.registry = ConnectorRegistry()
        self.observer = None

    # ── File processing ───────────────────────────────
    def process_file(self, filepath: Path):
        if not self._should_process(filepath):
            return

        log.info(f"Processing: {filepath.name}")

        file_hash = self._hash_file(filepath)

        if self.db.session_exists(
                str(filepath), file_hash):
            log.debug(
                f"Already indexed: "
                f"{filepath.name}")
            return

        project_name = filepath.parent.name
        project_path = str(filepath.parent)
        project_id = (
            self.db.get_or_create_project(
                project_name, project_path))

        parsed = self.registry.parse(filepath)
        parsed["project"] = project_name

        self._write_sidecar(filepath, parsed)

        session_id = self.db.register_session(
            project_id, parsed, file_hash)

        self.db.store_decisions(
            project_id,
            session_id,
            parsed.get("decisions", []))

        self.db.store_dead_ends(
            project_id,
            session_id,
            parsed.get("dead_ends", []))

        log.info(
            f"Indexed: {filepath.name} — "
            f"{len(parsed.get('decisions', []))}"
            f" decisions")

    def process_directory(self,
                          directory: Path = None):
        directory = directory or SESSIONS_DIR

        if not directory.exists():
            log.warning(
                f"Directory not found: "
                f"{directory}")
            return

        count = 0
        for filepath in directory.rglob("*"):
            if filepath.is_file():
                self.process_file(filepath)
                count += 1

        log.info(
            f"Batch processed {count} files")

    def process_project(self,
                        project_name: str):
        project_dir = (SESSIONS_DIR /
                       project_name)
        if project_dir.exists():
            self.process_directory(project_dir)
        else:
            log.warning(
                f"No sessions: {project_name}")

    # ── Watching ──────────────────────────────────────
    def start_watching(self):
        SESSIONS_DIR.mkdir(
            parents=True, exist_ok=True)

        # Resolve symlinks to ensure watchdog watches the actual target
        watch_path = SESSIONS_DIR.resolve()

        handler = SessionHandler(self)
        self.observer = Observer()
        self.observer.schedule(
            handler,
            str(watch_path),
            recursive=True)
        self.observer.start()
        log.info(f"Watching: {watch_path}")

    def stop_watching(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            log.info("Watcher stopped")

    # ── Decision retrieval ────────────────────────────
    def get_decisions_for_context(
            self,
            project_name: str,
            verified_only: bool = True
    ) -> list:
        projects = self.db.list_projects()
        project_id = None

        for p in projects:
            if p["name"] == project_name:
                project_id = p["id"]
                break

        if not project_id:
            return []

        return self.db.get_decisions(
            project_id, verified_only)

    def verify_session(self,
                       filepath: str):
        with self.db._connect() as conn:
            row = conn.execute(
                "SELECT id, project_id "
                "FROM sessions "
                "WHERE filepath = ?",
                (filepath,)).fetchone()

            if not row:
                log.warning(
                    f"Session not found: "
                    f"{filepath}")
                return

            session_id = row["id"]

            conn.execute(
                "UPDATE sessions SET "
                "verified = TRUE "
                "WHERE id = ?",
                (session_id,))

            conn.execute(
                "UPDATE decisions SET "
                "verified = TRUE "
                "WHERE session_id = ?",
                (session_id,))

        log.info(
            f"Verified: "
            f"{Path(filepath).name}")

    # ── Stats for CodeMaid ────────────────────────────
    def stats(self) -> dict:
        projects = self.db.list_projects()
        all_sessions = []
        all_decisions = []

        for p in projects:
            sessions = self.db.list_sessions(
                p["id"])
            decisions = self.db.get_decisions(
                p["id"],
                verified_only=False)
            all_sessions.extend(sessions)
            all_decisions.extend(decisions)

        return {
            "total_projects": len(projects),
            "total_sessions": len(all_sessions),
            "verified_sessions": len([
                s for s in all_sessions
                if s.get("verified")]),
            "total_decisions": len(all_decisions),
            "verified_decisions": len([
                d for d in all_decisions
                if d.get("verified")]),
            "sessions_dir": str(SESSIONS_DIR),
            "db_size_mb": round(
                DB_PATH.stat().st_size /
                1024 / 1024, 2)
            if DB_PATH.exists() else 0
        }

    # ── Utilities ─────────────────────────────────────
    def _should_process(self,
                        filepath: Path) -> bool:
        if filepath.stem.endswith("_parsed"):
            return False
        if filepath.name.startswith("."):
            return False
        if filepath.suffix.lower() not in \
                self.SUPPORTED_EXTENSIONS:
            return False
        if not filepath.exists():
            return False
        return True

    def _hash_file(self,
                   filepath: Path) -> str:
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()

    def _write_sidecar(self,
                       filepath: Path,
                       parsed: dict):
        sidecar = (filepath.parent /
                   f"{filepath.stem}_parsed.json")
        try:
            with open(sidecar, 'w') as f:
                json.dump(parsed, f,
                          indent=2,
                          default=str)
        except Exception as e:
            log.warning(
                f"Could not write sidecar: {e}")


# ── CLI entry point ───────────────────────────────────
def main():
    import sys
    indexer = Indexer()

    if "--watch" in sys.argv:
        indexer.start_watching()
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            indexer.stop_watching()
    else:
        indexer.process_directory()


if __name__ == "__main__":
    main()
