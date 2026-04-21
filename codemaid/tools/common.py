"""
CODEMAID Tools — Shared utilities.
Path confinement, audit logging, backups, validation, fuzzy matching.
"""

import ast
import json
import logging
import logging.handlers
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Audit Log (Python logging module)
# ---------------------------------------------------------------------------

_AUDIT_DIR = None
_audit_logger = None


def _get_audit_dir() -> Path:
    global _AUDIT_DIR
    if _AUDIT_DIR is None:
        _AUDIT_DIR = Path.home() / ".config" / "codemaid"
        _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    return _AUDIT_DIR


def _get_audit_logger() -> logging.Logger:
    """Return the shared audit logger, initializing it on first call."""
    global _audit_logger
    if _audit_logger is not None:
        return _audit_logger

    _audit_logger = logging.getLogger("codemaid.audit")
    _audit_logger.setLevel(logging.INFO)
    _audit_logger.propagate = False  # don't bleed into the root logger

    if not _audit_logger.handlers:
        audit_path = _get_audit_dir() / "audit.log"
        handler = logging.handlers.RotatingFileHandler(
            audit_path,
            maxBytes=5 * 1024 * 1024,   # 5 MB per file
            backupCount=3,               # keep audit.log + 3 rotated copies
            encoding="utf-8",
        )

        class _JsonFormatter(logging.Formatter):
            def format(self, record):
                return json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action":    record.action,
                    "target":    record.target,
                    "result":    record.result,
                    "session_id": record.session_id,
                })

        handler.setFormatter(_JsonFormatter())
        _audit_logger.addHandler(handler)

    return _audit_logger


def _audit_log(action: str, target: str = "", result: str = "", session_id: str = "") -> None:
    """Write one JSON audit entry via the standard logging module."""
    _get_audit_logger().info(
        "",
        extra={
            "action":     action,
            "target":     target,
            "result":     result,
            "session_id": session_id,
        },
    )


# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------

_BACKUP_DIR = None


def _get_backup_dir() -> Path:
    global _BACKUP_DIR
    if _BACKUP_DIR is None:
        _BACKUP_DIR = _get_audit_dir() / "backups"
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return _BACKUP_DIR


def _backup_file(path: Path) -> str:
    """Copy a file to the backup dir with a timestamp before editing."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = str(path).replace("/", "_").replace("\\", "_")
    backup_path = _get_backup_dir() / f"{ts}_{safe_name}"
    shutil.copy2(path, backup_path)

    # Rotation: keep at most 500 backups; prune oldest 50 if exceeded
    backups = sorted(_get_backup_dir().glob("*"), key=lambda p: p.stat().st_mtime)
    if len(backups) > 500:
        for old in backups[:50]:
            try:
                old.unlink()
            except OSError:
                pass

    return str(backup_path)


def _find_latest_backup(resolved_path: Path) -> Path | None:
    """Find the most recent backup for a given resolved path."""
    safe_name = str(resolved_path).replace("/", "_").replace("\\", "_")
    backups = sorted(_get_backup_dir().glob(f"*_{safe_name}"), key=lambda p: p.stat().st_mtime)
    return backups[-1] if backups else None


# ---------------------------------------------------------------------------
# Post-edit validation
# ---------------------------------------------------------------------------

def _validate_file(path: Path) -> tuple[bool, str]:
    """Run a language-appropriate syntax check after an edit. Returns (ok, message)."""
    ext = path.suffix.lower()
    try:
        if ext == ".py":
            source = path.read_text(encoding="utf-8")
            ast.parse(source)
            return True, "Python syntax OK"
        elif ext in (".js", ".ts"):
            result = subprocess.run(
                ["node", "--check", str(path)],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return True, "JS/TS syntax OK"
            return False, result.stderr.strip()
        elif ext in (".json",):
            json.loads(path.read_text(encoding="utf-8"))
            return True, "JSON syntax OK"
        else:
            return True, f"No validator for {ext}"
    except SyntaxError as e:
        return False, str(e)
    except Exception:
        return True, f"No validator for {ext}"


# ---------------------------------------------------------------------------
# Diff preview
# ---------------------------------------------------------------------------

def _diff_preview(original_path: Path, new_content: str) -> str:
    """Return a unified diff string between original file and new content."""
    try:
        original = original_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except FileNotFoundError:
        original = []
    new_lines = new_content.splitlines(keepends=True)
    return "".join(unified_diff(original, new_lines, fromfile=str(original_path), tofile=str(original_path)))


# ---------------------------------------------------------------------------
# Path confinement
# ---------------------------------------------------------------------------

def _check_confinement(path: str | Path, work_dir: str | Path) -> tuple[Path | None, str | None]:
    """Verify path stays within work_dir. Returns (resolved_path, error_string_or_None).

    Uses is_relative_to() (Python 3.9+) to prevent the startswith suffix-attack
    where /project-evil passes a startswith('/project') check.
    """
    try:
        real_work = Path(work_dir).resolve()
        resolved = Path(path).resolve()

        if not resolved.is_relative_to(real_work):
            return None, f"Access denied: Path {path} resolves to {resolved}, which is outside {real_work}."

        return resolved, None
    except Exception as e:
        return None, f"Access denied: Path validation failed ({e})."


# ---------------------------------------------------------------------------
# Fuzzy edit
# ---------------------------------------------------------------------------

def _fuzzy_edit(content: str, search: str, replace: str) -> str | None:
    """Try to find the search block approximately and replace it."""
    search_lines = search.strip().split('\n')
    content_lines = content.split('\n')

    best_ratio = 0
    best_idx = -1

    for i in range(len(content_lines) - len(search_lines) + 1):
        window = '\n'.join(content_lines[i:i + len(search_lines)])
        ratio = SequenceMatcher(None, window.strip(), search.strip()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = i

    if best_ratio >= 0.8:
        new_lines = (
            content_lines[:best_idx]
            + replace.strip().split('\n')
            + content_lines[best_idx + len(search_lines):]
        )
        return '\n'.join(new_lines)

    return None
