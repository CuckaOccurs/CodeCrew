# ~/.agents/rules/rules.md

## No Hardcoded Values

| Value | Use instead |
|-------|-------------|
| Usernames | `getpass.getuser()` |
| Home paths | `Path.home()` |
| API keys | `os.environ.get("KEY_NAME")` |
| Service URLs | config → env var → fallback |

## Read Before Editing

Always read a file before modifying it.

## Shell Safety

- `shell=False` + `shlex.split()` for subprocess
- Never build shell strings from user input
