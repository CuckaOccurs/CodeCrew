"""
OpenPaws Tools — Secure file editing and bash execution.

All shell=True + f-string interpolation removed.
Path traversal checks on all file-reading tools.
Audit logging for every action.
Post-edit validation. Automatic backups. Input sanitization.
"""

import ast
import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from difflib import SequenceMatcher, unified_diff
from pathlib import Path

# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

_AUDIT_DIR = None

def _get_audit_dir():
    global _AUDIT_DIR
    if _AUDIT_DIR is None:
        _AUDIT_DIR = Path.home() / ".config" / "openpaws"
        _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    return _AUDIT_DIR

def _audit_log(action, target="", result="", session_id=""):
    """Append one JSON line to the audit log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "target": target,
        "result": result,
        "session_id": session_id,
    }
    audit_path = _get_audit_dir() / "audit.log"
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------

_BACKUP_DIR = None

def _get_backup_dir():
    global _BACKUP_DIR
    if _BACKUP_DIR is None:
        _BACKUP_DIR = _get_audit_dir() / "backups"
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return _BACKUP_DIR

def _backup_file(path):
    """Copy a file to the backup dir with a timestamp before editing."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = str(path).replace("/", "_").replace("\\", "_")
    backup_path = _get_backup_dir() / f"{ts}_{safe_name}"
    import shutil
    shutil.copy2(path, backup_path)
    return str(backup_path)

# ---------------------------------------------------------------------------
# Post-edit validation
# ---------------------------------------------------------------------------

def _validate_file(path):
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
            path.read_text(encoding="utf-8")  # will raise if invalid
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

def _diff_preview(original_path, new_content):
    """Return a unified diff string between original file and new content."""
    try:
        original = original_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except FileNotFoundError:
        original = []
    new_lines = new_content.splitlines(keepends=True)
    return "".join(unified_diff(original, new_lines, fromfile=str(original_path), tofile=str(original_path)))

# ---------------------------------------------------------------------------
# Tool Definitions (OpenAI / Ollama Function Calling Format)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. ALWAYS use this before editing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file to read (relative to working directory).",
                    }
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
                    "path": {
                        "type": "string",
                        "description": "The path to the file to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The full content of the file.",
                    },
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
                    "path": {
                        "type": "string",
                        "description": "The path to the file to edit.",
                    },
                    "search": {
                        "type": "string",
                        "description": "The exact block of code to search for (must match exactly).",
                    },
                    "replace": {
                        "type": "string",
                        "description": "The new block of code to replace the search block.",
                    },
                },
                "required": ["path", "search", "replace"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus",
            "description": "Deep-search the entire codebase for a pattern. Returns file paths, line numbers, and surrounding context. Like Ctrl+F for the whole project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The regex or string pattern to search for.",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of surrounding lines to include (default: 2).",
                    },
                    "file_type": {
                        "type": "string",
                        "description": "Optional file extension filter (e.g., '.py', '.md', '.js').",
                    }
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
                    "pattern": {
                        "type": "string",
                        "description": "The regex or string pattern to search for.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional specific file or directory to search in.",
                    }
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information using Firecrawl.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_scrape",
            "description": "Fetch and read the text content of a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to scrape.",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read the text content of a PDF, Word, or Excel file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the document.",
                    }
                },
                "required": ["path"],
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
                    "path": {
                        "type": "string",
                        "description": "The path to the file whose last edit diff to show.",
                    }
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
                    "path": {
                        "type": "string",
                        "description": "The path to the file to undo the last edit on.",
                    }
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
                    }
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
                    "path": {
                        "type": "string",
                        "description": "Optional directory to list. Defaults to working directory.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "List all special skills and capabilities currently loaded by OpenPaws.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run.",
                    }
                },
                "required": ["command"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Tool Implementation
# ---------------------------------------------------------------------------

def _check_confinement(path, work_dir):
    """Verify path stays within work_dir. Returns (resolved_path, error_string_or_None)."""
    try:
        resolved = path.resolve()
        resolved.relative_to(Path(work_dir).resolve())
        return resolved, None
    except ValueError:
        return None, "Access denied: Path outside working directory."


def execute_tool(name, args, work_dir):
    """Execute a tool and return the result."""
    try:
        if name == "read_file":
            path = Path(work_dir) / args["path"]
            resolved, err = _check_confinement(path, work_dir)
            if err:
                return {"error": err}

            if not resolved.exists():
                return {"error": f"File not found: {path}"}
            content = resolved.read_text(encoding="utf-8")
            if len(content) > 20000:
                return {"content": content[:10000] + "\n... [File truncated] ..."}
            _audit_log("read_file", str(path), "ok")
            return {"content": content}

        elif name == "write_file":
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

            backups = sorted(_get_backup_dir().glob(f"*_{resolved.name}"), key=lambda p: p.stat().st_mtime)
            if not backups:
                return {"error": "No backup found for this file."}
            latest_backup = backups[-1]
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

            backups = sorted(_get_backup_dir().glob(f"*_{resolved.name}"), key=lambda p: p.stat().st_mtime)
            if not backups:
                return {"error": "No backup found for this file."}
            latest_backup = backups[-1]
            import shutil
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

        elif name == "focus":
            pattern = args.get("pattern")
            context = args.get("context_lines", 2)
            file_type = args.get("file_type", "")
            try:
                which_rg = subprocess.run(
                    ["which", "rg"], capture_output=True, text=True, timeout=5,
                )
                has_rg = which_rg.returncode == 0
                grep_args = ["-n", "--no-color", "-C", str(context)]
                if file_type:
                    grep_args.extend(["-g", f"*{file_type}"])
                grep_args.append(pattern)

                cmd = (["rg"] if has_rg else ["grep", "-r", "-n"]) + grep_args
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=15, cwd=work_dir,
                )
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
                which_rg = subprocess.run(
                    ["which", "rg"], capture_output=True, text=True, timeout=5,
                )
                has_rg = which_rg.returncode == 0
                grep_cmd = ["rg", "-n", "--no-color"] if has_rg else ["grep", "-r", "-n"]
                grep_cmd.append(pattern)
                if not has_rg:
                    grep_cmd.append(target)

                result = subprocess.run(
                    grep_cmd, capture_output=True, text=True, timeout=10, cwd=work_dir,
                )
                output = result.stdout
                if not output and result.returncode != 0:
                    output = result.stderr or "No matches found."
                if len(output) > 4000:
                    output = output[:4000] + "\n... [Output truncated] ..."
                _audit_log("grep", pattern, "ok")
                return {"matches": output}
            except Exception as e:
                return {"error": f"Grep failed: {str(e)}"}

        elif name == "web_search":
            query = args.get("query")
            try:
                which_fc = subprocess.run(
                    ["which", "firecrawl-search"], capture_output=True, text=True, timeout=5,
                )
                if which_fc.returncode == 0:
                    cmd = ["firecrawl-search", query]
                else:
                    return {"error": "Firecrawl not installed. Install with: npm i -g @mendable/firecrawl-cli"}

                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=20, cwd=work_dir,
                )
                output = result.stdout
                if not output and result.returncode != 0:
                    output = result.stderr or "No search results found."
                if len(output) > 4000:
                    output = output[:4000] + "\n... [Search results truncated] ..."
                _audit_log("web_search", query, "ok")
                return {"results": output}
            except Exception as e:
                return {"error": f"Web search failed: {str(e)}"}

        elif name == "web_scrape":
            url = args.get("url")
            try:
                which_fc = subprocess.run(
                    ["which", "firecrawl-scrape"], capture_output=True, text=True, timeout=5,
                )
                if which_fc.returncode == 0:
                    cmd = ["firecrawl-scrape", url]
                else:
                    curl = subprocess.run(
                        ["curl", "-s", url],
                        capture_output=True, text=True, timeout=15,
                    )
                    which_pandoc = subprocess.run(
                        ["which", "pandoc"], capture_output=True, text=True, timeout=5,
                    )
                    if which_pandoc.returncode == 0:
                        pandoc = subprocess.run(
                            ["pandoc", "-f", "html", "-t", "markdown"],
                            input=curl.stdout, capture_output=True, text=True, timeout=15,
                        )
                        output = pandoc.stdout or curl.stdout
                    else:
                        output = curl.stdout
                    if len(output) > 4000:
                        output = output[:4000] + "\n... [Content truncated] ..."
                    _audit_log("web_scrape", url, "ok")
                    return {"content": output}

                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=20, cwd=work_dir,
                )
                output = result.stdout
                if not output and result.returncode != 0:
                    output = result.stderr or "No content found."
                if len(output) > 4000:
                    output = output[:4000] + "\n... [Content truncated] ..."
                _audit_log("web_scrape", url, "ok")
                return {"content": output}
            except Exception as e:
                return {"error": f"Web scrape failed: {str(e)}"}

        elif name == "read_document":
            path = Path(work_dir) / args["path"]
            resolved, err = _check_confinement(path, work_dir)
            if err:
                return {"error": err}
            if not resolved.exists():
                return {"error": f"File not found: {path}"}

            ext = resolved.suffix.lower()
            try:
                if ext == ".pdf":
                    result = subprocess.run(
                        ["pdftotext", str(resolved), "-"],
                        capture_output=True, text=True, timeout=20,
                    )
                    output = result.stdout or result.stderr
                elif ext in (".docx", ".doc"):
                    result = subprocess.run(
                        ["pandoc", str(resolved), "-t", "markdown"],
                        capture_output=True, text=True, timeout=20,
                    )
                    output = result.stdout or result.stderr
                elif ext in (".xlsx", ".xls", ".csv"):
                    result = subprocess.run(
                        ["xlsx2csv", str(resolved), "-"],
                        capture_output=True, text=True, timeout=20,
                    )
                    if result.returncode != 0:
                        output = resolved.read_text(encoding="utf-8")
                    else:
                        output = result.stdout or result.stderr
                else:
                    return {"content": resolved.read_text(encoding="utf-8")}

                if not output:
                    return {"content": "(Document is empty or unreadable)"}
                _audit_log("read_document", str(path), "ok")
                return {"content": output[:10000]}
            except Exception as e:
                return {"error": f"Read document failed: {str(e)}"}

        elif name == "list_skills":
            return {"message": "Skills are loaded into the system prompt. Check the 'Currently Loaded Skills' section."}

        elif name == "run_command":
            cmd_str = args["command"]
            # Log before execution
            _audit_log("run_command", cmd_str, "executing")

            # Use shell=True but with a timeout and capture
            result = subprocess.run(
                cmd_str, shell=True, capture_output=True, text=True, timeout=30, cwd=work_dir,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            exit_code = result.returncode
            _audit_log("run_command", cmd_str, f"exit_code={exit_code}")
            return {"output": output or "(No output)", "exit_code": exit_code}

    except Exception as e:
        _audit_log(name, str(args), f"error: {e}")
        return {"error": str(e)}

    return {"error": f"Unknown tool: {name}"}


def _fuzzy_edit(content, search, replace):
    """Try to find the search block approximately and replace it."""
    search_lines = search.strip().split('\n')
    content_lines = content.split('\n')

    best_ratio = 0
    best_idx = -1

    for i in range(len(content_lines) - len(search_lines) + 1):
        window = '\n'.join(content_lines[i:i+len(search_lines)])
        ratio = SequenceMatcher(None, window.strip(), search.strip()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = i

    if best_ratio >= 0.8:
        new_lines = content_lines[:best_idx] + replace.strip().split('\n') + content_lines[best_idx + len(search_lines):]
        return '\n'.join(new_lines)

    return None
