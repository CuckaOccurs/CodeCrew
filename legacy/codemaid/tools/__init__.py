"""
CODEMAID Tools — Package entry point.

Aggregates all tool definitions and provides the execute_tool() dispatcher.
Backward-compatible: `from codemaid.tools import TOOLS, execute_tool` still works.
"""

from pathlib import Path
from typing import Any

from .common import _check_confinement  # re-exported for backward compat (tests import it)
from .file_tools import TOOLS as _FILE_TOOLS, execute as _exec_file
from .search_tools import TOOLS as _SEARCH_TOOLS, execute as _exec_search
from .web_tools import TOOLS as _WEB_TOOLS, execute as _exec_web
from .git_tools import TOOLS as _GIT_TOOLS, execute as _exec_git
from .system_tools import TOOLS as _SYSTEM_TOOLS, execute as _exec_system
from .memory_tools import TOOLS as _MEMORY_TOOLS, execute as _exec_memory
from .session_tools import TOOLS as _SESSION_TOOLS, execute as _exec_session

# Aggregated tool schema list — same structure the agent passes to providers
TOOLS = (
    _FILE_TOOLS
    + _SEARCH_TOOLS
    + _WEB_TOOLS
    + _GIT_TOOLS
    + _SYSTEM_TOOLS
    + _MEMORY_TOOLS
    + _SESSION_TOOLS
)

# Ordered list of executor functions — first match wins
_EXECUTORS = [
    _exec_file,
    _exec_search,
    _exec_web,
    _exec_git,
    _exec_system,
    _exec_memory,
    _exec_session,
]


def execute_tool(
    name: str,
    args: dict[str, Any],
    work_dir: str | Path,
    vault_on: bool = True,
    vault_allowlist: bool = False,
    sudo_mode: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Dispatch a tool call to the appropriate submodule executor.

    Returns a result dict. Unknown tool names return {"error": "Unknown tool: <name>"}.
    """
    try:
        for executor in _EXECUTORS:
            result = executor(
                name, args, work_dir,
                vault_on=vault_on,
                vault_allowlist=vault_allowlist,
                sudo_mode=sudo_mode,
                dry_run=dry_run,
            )
            if result is not None:
                return result
    except Exception as e:
        from .common import _audit_log
        _audit_log(name, str(args), f"error: {e}")
        return {"error": str(e)}

    return {"error": f"Unknown tool: {name}"}
