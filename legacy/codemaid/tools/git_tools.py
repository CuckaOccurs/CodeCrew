"""
CODEMAID Git Tools — git_status, git_diff, git_add, git_commit, git_log.
"""

import subprocess
from pathlib import Path
from typing import Any

from .common import _audit_log

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show git status: modified, staged, and untracked files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "short": {"type": "boolean", "description": "Use short format (true/false). Default: false."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show git diff of unstaged changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional specific file to diff."},
                    "staged": {"type": "boolean", "description": "Show staged (vs unstaged) changes. Default: false."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_add",
            "description": "Stage files for commit. Use 'all' for git add -A, or specify a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or directory to stage. Use '.' for all files."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commit staged changes with a message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The commit message."},
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Show recent git log entries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of log entries to show. Default: 10."},
                },
            },
        },
    },
]


def execute(name: str, args: dict[str, Any], work_dir: str | Path, **kwargs: Any) -> dict[str, Any] | None:
    """Execute a git tool. Returns result dict or None if name not handled."""

    if name == "git_status":
        short = args.get("short", False)
        git_cmd = ["git", "status", "--short"] if short else ["git", "status"]
        result = subprocess.run(git_cmd, capture_output=True, text=True, timeout=10, cwd=work_dir)
        output = (result.stdout + result.stderr).strip()
        _audit_log("git_status", "", "ok")
        return {"status": output or "(Clean working tree)"}

    elif name == "git_diff":
        path = args.get("path", "")
        staged = args.get("staged", False)
        git_cmd = ["git", "diff"]
        if staged:
            git_cmd.append("--staged")
        if path:
            git_cmd.extend(["--", path])
        result = subprocess.run(git_cmd, capture_output=True, text=True, timeout=10, cwd=work_dir)
        output = result.stdout or "(No changes)"
        if len(output) > 12000:
            output = output[:12000] + "\n... [Diff truncated] ..."
        _audit_log("git_diff", path or "all", "ok")
        return {"diff": output}

    elif name == "git_add":
        path = args.get("path", ".")
        result = subprocess.run(
            ["git", "add", path], capture_output=True, text=True, timeout=10, cwd=work_dir,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip()}
        _audit_log("git_add", path, "ok")
        return {"message": f"✓ Staged: {path}"}

    elif name == "git_commit":
        message = args.get("message", "")
        if not message:
            return {"error": "Commit message is required."}
        result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True, text=True, timeout=10, cwd=work_dir,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            return {"error": output or "Commit failed (nothing staged?)"}
        _audit_log("git_commit", message[:80], "ok")
        return {"message": f"✓ Committed: {message[:80]}"}

    elif name == "git_log":
        count = args.get("count", 10)
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{count}"],
            capture_output=True, text=True, timeout=10, cwd=work_dir,
        )
        output = result.stdout.strip()
        _audit_log("git_log", f"count={count}", "ok")
        return {"log": output or "(No commits)"}

    return None
