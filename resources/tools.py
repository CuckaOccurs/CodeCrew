"""
CodeMAID Tools — Aider-style file editing and bash execution.
"""

import subprocess
from pathlib import Path
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Tool Definitions (OpenAI / Ollama Function Calling Format)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Always use this before editing.",
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
            "name": "list_skills",
            "description": "List all special skills and capabilities currently loaded by CodeMAID.",
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

def execute_tool(name, args, work_dir):
    """Execute a tool and return the result."""
    try:
        if name == "read_file":
            path = Path(work_dir) / args["path"]
            # Security: confinement check
            try:
                path.resolve().relative_to(Path(work_dir).resolve())
            except ValueError:
                return {"error": "Access denied: Path outside working directory."}
            
            if not path.exists():
                return {"error": f"File not found: {path}"}
            content = path.read_text(encoding="utf-8")
            # Truncate if huge
            if len(content) > 20000:
                return {"content": content[:10000] + "\n... [File truncated] ..."}
            return {"content": content}

        elif name == "write_file":
            path = Path(work_dir) / args["path"]
            try:
                path.resolve().relative_to(Path(work_dir).resolve())
            except ValueError:
                return {"error": "Access denied: Path outside working directory."}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args["content"], encoding="utf-8")
            return {"message": f"✓ Created/Overwrote {path}"}

        elif name == "edit_file":
            path = Path(work_dir) / args["path"]
            try:
                path.resolve().relative_to(Path(work_dir).resolve())
            except ValueError:
                return {"error": "Access denied: Path outside working directory."}
            if not path.exists():
                return {"error": f"File not found: {path}"}
            
            content = path.read_text(encoding="utf-8")
            search = args["search"]
            replace = args["replace"]

            # Exact match
            if search in content:
                new_content = content.replace(search, replace, 1)
                path.write_text(new_content, encoding="utf-8")
                return {"message": f"✓ Edited {path}"}
            
            # Fuzzy match (80% similarity on lines)
            result = _fuzzy_edit(content, search, replace)
            if result:
                path.write_text(result, encoding="utf-8")
                return {"message": f"✓ Edited {path} (fuzzy match)"}
            
            return {"error": "Could not find exact search text in file."}

        elif name == "focus":
            pattern = args.get("pattern")
            context = args.get("context_lines", 2)
            file_type = args.get("file_type", "")
            try:
                # Use ripgrep with context lines for a rich search result
                grep_cmd = "rg" if subprocess.run(["which", "rg"], capture_output=True).returncode == 0 else "grep"
                if grep_cmd == "rg":
                    type_flag = f"-g '*{file_type}'" if file_type else ""
                    cmd = f"rg -n --no-color -C {context} {type_flag} '{pattern}'"
                else:
                    type_flag = f"--include='*{file_type}'" if file_type else ""
                    cmd = f"grep -r -n {type_flag} '{pattern}'"
                
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=15, cwd=work_dir
                )
                output = result.stdout
                if not output and result.returncode != 0:
                    output = result.stderr or "No matches found."
                if len(output) > 8000:
                    output = output[:8000] + "\n... [Focus results truncated. Try a more specific pattern.] ..."
                return {"focus_results": output}
            except Exception as e:
                return {"error": f"Focus search failed: {str(e)}"}

        elif name == "grep":
            pattern = args.get("pattern")
            target = args.get("path", ".")
            try:
                # Use ripgrep (rg) if available, else fallback to grep
                grep_cmd = "rg" if subprocess.run(["which", "rg"], capture_output=True).returncode == 0 else "grep -r"
                cmd = f"{grep_cmd} -n --no-color '{pattern}' {target}"
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=10, cwd=work_dir
                )
                output = result.stdout
                if not output and result.returncode != 0:
                    output = result.stderr or "No matches found."
                # Limit output length
                if len(output) > 4000:
                    output = output[:4000] + "\n... [Output truncated] ..."
                return {"matches": output}
            except Exception as e:
                return {"error": f"Grep failed: {str(e)}"}

        elif name == "web_search":
            query = args.get("query")
            try:
                # Try firecrawl-search first
                cmd = f"firecrawl-search '{query}'"
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=20, cwd=work_dir
                )
                output = result.stdout
                if not output and result.returncode != 0:
                    output = result.stderr or "No search results found."
                # Limit output length
                if len(output) > 4000:
                    output = output[:4000] + "\n... [Search results truncated] ..."
                return {"results": output}
            except Exception as e:
                return {"error": f"Web search failed: {str(e)}"}

        elif name == "web_scrape":
            url = args.get("url")
            try:
                # Use firecrawl-scrape if available, else curl
                if subprocess.run(["which", "firecrawl-scrape"], capture_output=True).returncode == 0:
                    cmd = f"firecrawl-scrape '{url}'"
                else:
                    cmd = f"curl -s '{url}' | pandoc -f html -t markdown 2>/dev/null || curl -s '{url}'"
                
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=20, cwd=work_dir
                )
                output = result.stdout
                if not output and result.returncode != 0:
                    output = result.stderr or "No content found."
                if len(output) > 4000:
                    output = output[:4000] + "\n... [Content truncated] ..."
                return {"content": output}
            except Exception as e:
                return {"error": f"Web scrape failed: {str(e)}"}

        elif name == "read_document":
            path = Path(work_dir) / args["path"]
            if not path.exists():
                return {"error": f"File not found: {path}"}
            
            ext = path.suffix.lower()
            try:
                if ext == ".pdf":
                    cmd = f"pdftotext '{path}' -"
                elif ext in [".docx", ".doc"]:
                    cmd = f"pandoc '{path}' -t markdown"
                elif ext in [".xlsx", ".xls", ".csv"]:
                    cmd = f"xlsx2csv '{path}' - 2>/dev/null || cat '{path}'"
                else:
                    return path.read_text(encoding="utf-8")
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20, cwd=work_dir)
                output = result.stdout or result.stderr
                if not output:
                    return {"content": "(Document is empty or unreadable)"}
                return {"content": output[:10000]}
            except Exception as e:
                return {"error": f"Read document failed: {str(e)}"}

        elif name == "list_skills":
            # This is handled by the Agent's context, but we return a confirmation
            return {"message": "Skills are loaded into the system prompt. Check the 'Currently Loaded Skills' section."}

        elif name == "run_command":
            cmd = args["command"]
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=work_dir
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            return output or "(No output)"

    except Exception as e:
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
