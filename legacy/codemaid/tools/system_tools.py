"""
CODEMAID System Tools — run_command (stateful shell session).
"""

import os
import queue
import shlex
import subprocess
import threading
from pathlib import Path
from typing import Any

from codemaid.vault import validate_command, BLOCKED, CAGE, firejail_run
from .common import _audit_log

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command in the working directory. "
                "State persists between calls — cd, export, and variable assignments carry over."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run."},
                    "timeout": {"type": "integer", "description": "Max seconds to wait (default 30)."},
                },
                "required": ["command"],
            },
        },
    },
]

# Per-working-directory persistent shell sessions.
# Key: str(work_dir) → _ShellSession instance
_sessions: dict[str, "_ShellSession"] = {}
_sessions_lock = threading.Lock()


class _ShellSession:
    """A persistent bash subprocess whose state (cwd, env, vars) survives between calls."""

    _SENTINEL = "__CODEMAID_DONE__"

    def __init__(self, work_dir: str) -> None:
        self._proc = subprocess.Popen(
            ["/bin/bash", "--norc", "--noprofile"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=work_dir, env=os.environ.copy(), text=True, bufsize=1,
        )
        self._lock = threading.Lock()
        self._out_queue: queue.Queue[str] = queue.Queue()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        assert self._proc.stdout
        for line in self._proc.stdout:
            self._out_queue.put(line)

    def run(self, cmd: str, timeout: int = 30) -> tuple[str, int]:
        """Run cmd, return (output, exit_code). Thread-safe."""
        with self._lock:
            assert self._proc.stdin
            # Write command + sentinel echo
            self._proc.stdin.write(
                f"{cmd}\n"
                f"echo \"{self._SENTINEL}:$?\"\n"
            )
            self._proc.stdin.flush()

            lines: list[str] = []
            exit_code = 0
            import time
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return "".join(lines) + "\n[timed out]", 1
                try:
                    line = self._out_queue.get(timeout=min(remaining, 0.5))
                except queue.Empty:
                    continue
                if line.startswith(self._SENTINEL + ":"):
                    try:
                        exit_code = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        exit_code = 0
                    break
                lines.append(line)
            return "".join(lines), exit_code

    def is_alive(self) -> bool:
        return self._proc.poll() is None


def _get_session(work_dir: str) -> _ShellSession:
    with _sessions_lock:
        sess = _sessions.get(work_dir)
        if sess is None or not sess.is_alive():
            sess = _ShellSession(work_dir)
            _sessions[work_dir] = sess
        return sess


def execute(
    name: str,
    args: dict[str, Any],
    work_dir: str | Path,
    vault_on: bool = True,
    vault_allowlist: bool = False,
    sudo_mode: bool = False,
    dry_run: bool = False,
    **kwargs: Any,
) -> dict[str, Any] | None:
    if name != "run_command":
        return None

    cmd_str = args["command"]
    timeout = int(args.get("timeout", 30))
    work_dir_str = str(work_dir)

    if dry_run:
        _audit_log("run_command", cmd_str, "DRY RUN (Simulation)")
        return {"output": f"(DRY RUN) Simulated execution of: {cmd_str}", "exit_code": 0}

    if vault_on:
        severity, message = validate_command(cmd_str, allowlist=vault_allowlist, sudo_mode=sudo_mode)
        if severity == BLOCKED:
            _audit_log("run_command", cmd_str, f"BLOCKED: {message}")
            return {"error": message}
        if severity == CAGE:
            _audit_log("run_command", cmd_str, f"CAGE: {message}")

    _audit_log("run_command", cmd_str, "executing")

    try:
        # Use stateful session for all commands (no firejail in stateful mode — stateful shell
        # and firejail are mutually exclusive; firejail wraps a fresh process each time).
        sess = _get_session(work_dir_str)
        output, exit_code = sess.run(cmd_str, timeout=timeout)
    except Exception as e:
        return {"error": f"Execution failed: {e}"}

    _audit_log("run_command", cmd_str, f"exit_code={exit_code}")
    return {"output": output.strip() or "(No output)", "exit_code": exit_code}
