"""
CODEMAID Search Tools — focus, grep.
"""

import subprocess
from pathlib import Path
from typing import Any

from .common import _audit_log

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "focus",
            "description": "Deep-search the entire codebase for a pattern. Returns file paths, line numbers, and surrounding context. Like Ctrl+F for the whole project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "The regex or string pattern to search for."},
                    "context_lines": {"type": "integer", "description": "Number of surrounding lines to include (default: 2)."},
                    "file_type": {"type": "string", "description": "Optional file extension filter (e.g., '.py', '.md', '.js')."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for a pattern in files within the working directory (Ctrl+F for the codebase).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "The regex or string pattern to search for."},
                    "path": {"type": "string", "description": "Optional specific file or directory to search in."},
                },
                "required": ["pattern"],
            },
        },
    },
]


def execute(name: str, args: dict[str, Any], work_dir: str | Path, **kwargs: Any) -> dict[str, Any] | None:
    """Execute a search tool. Returns result dict or None if name not handled."""

    if name == "focus":
        pattern = args.get("pattern")
        context = args.get("context_lines", 2)
        file_type = args.get("file_type", "")
        try:
            which_rg = subprocess.run(["which", "rg"], capture_output=True, text=True, timeout=5)
            has_rg = which_rg.returncode == 0
            grep_args = ["-n", "-C", str(context)]
            if file_type:
                grep_args.extend(["-g", f"*{file_type}"])
            grep_args.append(pattern)
            cmd = (["rg"] if has_rg else ["grep", "-r", "-n"]) + grep_args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, cwd=work_dir)
            output = result.stdout
            if not output and result.returncode != 0:
                output = result.stderr or "No matches found."
            if len(output) > 8000:
                output = output[:8000] + "\n... [Focus results truncated. Try a more specific pattern.] ..."
            _audit_log("focus", pattern, "ok")
            return {"focus_results": output}
        except Exception as e:
            return {"error": f"Focus search failed: {str(e)}"}

    elif name == "grep":
        pattern = args.get("pattern")
        target = args.get("path", ".")
        try:
            which_rg = subprocess.run(["which", "rg"], capture_output=True, text=True, timeout=5)
            has_rg = which_rg.returncode == 0
            grep_cmd = ["rg", "-n", pattern, target] if has_rg else ["grep", "-r", "-n", pattern, target]
            result = subprocess.run(grep_cmd, capture_output=True, text=True, timeout=10, cwd=work_dir)
            output = result.stdout
            if not output and result.returncode != 0:
                output = result.stderr or "No matches found."
            if len(output) > 4000:
                output = output[:4000] + "\n... [Output truncated] ..."
            _audit_log("grep", pattern, "ok")
            return {"matches": output}
        except Exception as e:
            return {"error": f"Grep failed: {str(e)}"}

    return None
