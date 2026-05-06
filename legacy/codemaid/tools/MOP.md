# codemaid/tools/ — Tool Definitions

**Path:** `codemaid/tools/`
**Total Tools:** 23

---

## Tool Inventory

### file_tools.py — File I/O

| Tool | Description |
|------|------------|
| `edit_plan` | Propose a multi-file edit plan before executing (plan mode) |
| `read_file` | Read a file's contents — always required before editing |
| `write_file` | Create or overwrite a file with full content |
| `edit_file` | Apply a SEARCH/REPLACE block to a file |
| `diff_preview` | Show unified diff of the last edit |
| `undo_edit` | Restore file from its last backup |
| `read_multiple` | Read multiple files in one call (parallel) |
| `list_dir` | List files and directories with types and sizes |

Internals: `_backup_file()`, `_fuzzy_edit()`, `_validate_file()`, `_check_confinement()`, `_audit_log()`, `_find_latest_backup()` — all from `common.py`

---

### search_tools.py — Code Search

| Tool | Description |
|------|------------|
| `focus` | Deep-search codebase with regex — returns file:line + context. Supports file type filter |
| `grep` | Search for pattern in files (fast, simple) |

---

### web_tools.py — Web Access

| Tool | Description |
|------|------------|
| `web_search` | Search the web |
| `web_scrape` | Fetch and read text content from a URL |
| `read_document` | Read PDF, Word, or Excel file contents |

Security: SSRF guard blocks cloud metadata IPs (`169.254.169.254`, `100.100.100.200`).

---

### git_tools.py — Version Control

| Tool | Description |
|------|------------|
| `git_status` | Show modified, staged, and untracked files |
| `git_diff` | Show unstaged or staged diffs |
| `git_add` | Stage files for commit |
| `git_commit` | Commit staged changes with a message |
| `git_log` | Show recent commit history |

---

### system_tools.py — Shell Execution

| Tool | Description |
|------|------------|
| `run_command` | Run a shell command in the working directory |

All commands pass through `vault.py` validation. Supports denylist (default) and allowlist modes. Optional Firejail sandbox.

---

### memory_tools.py — Persistent Memory

| Tool | Description |
|------|------------|
| `remember_fact` | Save a fact to persistent JSON memory |
| `update_memory_summary` | Update the high-level project summary |
| `list_skills` | List available skills from `~/.agents/skills/` |
| `save_session` | Save session data |

Memory stored at `.agents/codemaid_memory.json` in the working directory.

---

## common.py — Shared Utilities

| Function | Purpose |
|----------|---------|
| `_audit_log()` | Log tool calls to audit trail |
| `_backup_file()` | Create `.bak` backup before editing |
| `_check_confinement()` | Verify path stays within working directory |
| `_find_latest_backup()` | Find most recent backup for undo |
| `_fuzzy_edit()` | Apply SEARCH/REPLACE with fuzzy matching |
| `_validate_file()` | Validate file exists and is readable |

---

## Execution Flow

```
execute_tool(name, args, work_dir, vault_on, vault_allowlist, sudo_mode, dry_run)
  │
  ├── file_tools
  ├── search_tools
  ├── web_tools
  ├── git_tools
  ├── system_tools  ← passes through vault.py
  └── memory_tools
      └── returns {"error": "Unknown tool: <name>"} if none match
```

Each executor returns `None` if the tool name doesn't belong to it — clean fallthrough.
