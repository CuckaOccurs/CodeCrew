# CodeMAID — Project Rules

## What Goes in the Repo

Only app files. Nothing else.

**Include:**
- `codemaid/` — the Python package
- `tests/` — test suite
- `README.md`, `Agents.md` — docs
- `pyproject.toml`, `requirements.txt`, `.gitignore`
- `.github/` — CI workflows

**Never commit:**
- Personal directories (`Setup-HowTo-Manual/`, `resources/`, `BrainStormingSuggestions/`, etc.)
- Temp files (`*.tmp`, `.directory`)
- Personal info (real names, email, home paths, private project paths)
- Anything not directly part of the installable app

## Pre-Push Checklist (run every time, no exceptions)

1. `git status` — only app files staged, nothing extra
2. `git diff --cached` — read the diff, confirm it looks right
3. Scan for personal info: real names, `/home/<user>/`, email, private paths
4. No `*.tmp`, no OS junk (`.directory`, `.DS_Store`, etc.)
5. No secrets, API keys, or tokens anywhere in staged files
6. **Always show the user the commit and ask before pushing** — never push automatically

## GitHub Rules

- **Never force push to main**
- **Never push without user confirmation** — show what's going in first
- Commit messages: `type: short description` (feat / fix / chore / docs)
- Always add `Co-Authored-By: Claude <noreply@claude.ai>` to commits Claude helped with
- README must not contain personal info — use `your-username` as placeholder in clone URLs
- If the repo was previously named something else, scrub the old name from all docs before pushing

## Personal Info Rules

- No real names in any committed file
- No email addresses
- No hardcoded home paths — use `Path.home()` or `~` generically
- GitHub username is fine only in remote URLs (not hardcoded in source)
- Profile files go in `codemaid/profiles/` — keep generic, no personal context
- When in doubt, scrub it out
