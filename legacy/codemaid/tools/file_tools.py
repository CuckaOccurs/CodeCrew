"""
CODEMAID File Tools — read, write, edit, diff, undo, list.
Tools: edit_plan, read_file, write_file, edit_file, diff_preview, undo_edit, read_multiple, list_dir
"""

import shutil
from difflib import unified_diff
from pathlib import Path
from typing import Any

from .common import (
    _audit_log, _backup_file, _check_confinement,
    _find_latest_backup, _fuzzy_edit, _validate_file,
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "edit_plan",
            "description": "Propose a plan for multi-file edits before executing them. This allows the user to review the scope of changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Explanation of the overall strategy.",
                    },
                    "edits": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "The file path to be modified."},
                                "description": {"type": "string", "description": "What will be changed in this file."},
                            },
                            "required": ["path", "description"],
                        },
                    },
                },
                "required": ["reasoning", "edits"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. ALWAYS use this before editing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the file to read (relative to working directory)."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or completely overwrite an existing file with new content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the file to write."},
                    "content": {"type": "string", "description": "The full content of the file."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Apply a SEARCH/REPLACE block to a file. Use for small edits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the file to edit."},
                    "search": {"type": "string", "description": "The exact block of code to search for (must match exactly)."},
                    "replace": {"type": "string", "description": "The new block of code to replace the search block."},
                },
                "required": ["path", "search", "replace"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diff_preview",
            "description": "Show a unified diff of the last edit made to a file. Requires a backup to exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the file whose last edit diff to show."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "undo_edit",
            "description": "Undo the last edit made to a file by restoring from backup.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the file to undo the last edit on."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_multiple",
            "description": "Read multiple files in one call. More efficient than calling read_file repeatedly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths to read (relative to working directory).",
                    },
                },
                "required": ["paths"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories with types and sizes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional directory to list. Defaults to working directory."},
                },
            },
        },
    },
]


def execute(name: str, args: dict[str, Any], work_dir: str | Path, **kwargs: Any) -> dict[str, Any] | None:
    """Execute a file tool. Returns result dict or None if name not handled."""
    dry_run = kwargs.get("dry_run", False)

    if name == "edit_plan":
        reasoning = args.get("reasoning", "No reason provided.")
        edits = args.get("edits", [])
        plan_str = f"PROPOSED EDIT PLAN:\n\nStrategy: {reasoning}\n\nFiles to modify:\n"
        for edit in edits:
            plan_str += f"- {edit.get('path', 'unknown')}: {edit.get('description', 'No description')}\n"
        _audit_log("edit_plan", str(len(edits)) + " files", "ok")
        return {"plan": plan_str}

    elif name == "read_file":
        path = Path(work_dir) / args["path"]
        resolved, err = _check_confinement(path, work_dir)
        if err:
            return {"error": err}
        if not resolved.exists():
            return {"error": f"File not found: {path}"}
        content = resolved.read_text(encoding="utf-8")
        if len(content) > 20000:
            _audit_log("read_file", str(path), "truncated")
            return {"content": content[:10000] + "\n... [File truncated] ..."}
        _audit_log("read_file", str(path), "ok")
        return {"content": content}

    elif name == "write_file":
        if dry_run:
            return {"message": f"(DRY RUN) Would have written file: {args.get('path')}"}
        path = Path(work_dir) / args["path"]
        resolved, err = _check_confinement(path, work_dir)
        if err:
            return {"error": err}
        if resolved.exists():
            _backup_file(resolved)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(args["content"], encoding="utf-8")
        ok, msg = _validate_file(resolved)
        result = f"✓ Created/Overwrote {path}"
        if not ok:
            result += f" (⚠ validation warning: {msg})"
        _audit_log("write_file", str(path), "ok" if ok else f"warning: {msg}")
        return {"message": result}

    elif name == "edit_file":
        if dry_run:
            return {"message": f"(DRY RUN) Would have edited file: {args.get('path')}"}
        path = Path(work_dir) / args["path"]
        resolved, err = _check_confinement(path, work_dir)
        if err:
            return {"error": err}
        if not resolved.exists():
            return {"error": f"File not found: {path}"}
        search = args.get("search", "")
        replace = args.get("replace", "")
        if not search or not search.strip():
            return {"error": "Search text is empty."}
        content = resolved.read_text(encoding="utf-8")
        _backup_file(resolved)
        new_content = None
        match_type = "exact"
        if search in content:
            new_content = content.replace(search, replace, 1)
        else:
            result = _fuzzy_edit(content, search, replace)
            if result:
                new_content = result
                match_type = "fuzzy"
        if new_content is None:
            return {"error": "Could not find search text in file."}
        resolved.write_text(new_content, encoding="utf-8")
        ok, msg = _validate_file(resolved)
        result = f"✓ Edited {path} ({match_type} match)"
        if not ok:
            result += f" (⚠ validation warning: {msg})"
        _audit_log("edit_file", str(path), match_type if ok else f"warning: {msg}")
        return {"message": result}

    elif name == "diff_preview":
        path = Path(work_dir) / args["path"]
        resolved, err = _check_confinement(path, work_dir)
        if err:
            return {"error": err}
        if not resolved.exists():
            return {"error": f"File not found: {path}"}
        latest_backup = _find_latest_backup(resolved)
        if not latest_backup:
            return {"error": "No backup found for this file."}
        original = latest_backup.read_text(encoding="utf-8")
        current = resolved.read_text(encoding="utf-8")
        diff = "".join(unified_diff(
            original.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile=f"{latest_backup.name}",
            tofile=str(resolved),
        ))
        return {"diff": diff or "(No differences)"}

    elif name == "undo_edit":
        path = Path(work_dir) / args["path"]
        resolved, err = _check_confinement(path, work_dir)
        if err:
            return {"error": err}
        if not resolved.exists():
            return {"error": f"File not found: {path}"}
        latest_backup = _find_latest_backup(resolved)
        if not latest_backup:
            return {"error": "No backup found for this file."}
        shutil.copy2(latest_backup, resolved)
        _audit_log("undo_edit", str(path), "ok")
        return {"message": f"✓ Restored {path} from backup"}

    elif name == "read_multiple":
        paths = args.get("paths", [])
        results = {}
        for p in paths:
            full = Path(work_dir) / p
            resolved, err = _check_confinement(full, work_dir)
            if err:
                results[p] = {"error": err}
                continue
            if not resolved.exists():
                results[p] = {"error": f"File not found: {p}"}
                continue
            content = resolved.read_text(encoding="utf-8")
            if len(content) > 10000:
                content = content[:5000] + "\n... [truncated] ..."
            results[p] = {"content": content}
        _audit_log("read_multiple", str(len(paths)) + " files", "ok")
        return results

    elif name == "list_dir":
        target = Path(work_dir) / args.get("path", ".")
        resolved, err = _check_confinement(target, work_dir)
        if err:
            return {"error": err}
        if not resolved.is_dir():
            return {"error": f"Not a directory: {target}"}
        entries = []
        for entry in sorted(resolved.iterdir()):
            size = entry.stat().st_size if entry.is_file() else "-"
            kind = "D" if entry.is_dir() else "F"
            entries.append(f"{kind} {size:>8} {entry.name}")
        return {"listing": "\n".join(entries) or "(empty)"}

    return None
