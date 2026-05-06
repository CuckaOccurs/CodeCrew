# CODEMAID — CodeCrew IDE Engine

A terminal AI coding assistant that interfaces with CodeCrew.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CodeCrew WebUI                            │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                  WebUI Bridge (bridge.py)                        │
│  - /execute, /status endpoints                                   │
│  - Forwards requests to CodeCrew IDE                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│          CodeMAID Engine (pipx/installable)                      │
│  - CLI tool: codemaid/maid                                        │
│  - Provides: audit, execute, status subcommands                   │
│  - Uses: Ollama API, task definitions                             │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

1. **Install CodeMAID:**

```bash
pipx install /home/cuckaoccurs/Projects/apps/CodeMAID
# OR
pip install -e /home/cuckaoccurs/Projects/apps/CodeMAID
```

2. **Configure WebUI:**

Add to `/home/cuckaoccurs/Projects/web-ui/requirements.txt`:
```
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
requests>=2.28.0
pydantic>=2.0.0
```

3. **Restart WebUI:**
```bash
cd /home/cuckaoccurs/Projects/web-ui
uvicorn codemaid_ui:app --reload --host 0.0.0.0 --port 3030
```

## Manual Commands

```bash
# Start from terminal
codemaid list           # List available models
codemaid audit <task>   # Audit a task
codemaid execute <task> # Execute a task
codemaid status         # Check status
```

## Environment Variables

```bash
export OLLAMA_BASE_URL="http://localhost:11434"
export MODEL="codellama:7b-codebase"
```

## File Structure

```
/home/cuckaoccurs/Projects/apps/CodeMAID/
├── codemaid/
│   ├── __init__.py
│   └── main.py          # Entry point for CLI
├── bridge.py            # WebUI integration
├── pyproject.toml      # Package config
├── INSTALL.md          # Installation guide (see above)
└── README.md           # This file
```

## Testing

```bash
# Test the engine
python3 -m codemaid --help

# Test audit
python3 -m codemaid audit test-task
```

## Troubleshooting

### termios Error
```
termios.error: Inappropriate ioctl for device
```
**Solution:** Run from an actual terminal session.

### Import Issues
```bash
# Add to your Python environment
sys.path.insert(0, '/home/cuckaoccurs/Projects/apps/CodeMAID')
```

### Ollama Not Running
```bash
# Start Ollama
ollama serve
```

## Support

- Repository: `/home/cuckaoccurs/Projects/apps/CodeMAID`
- Documentation: Check INSTALL.md
