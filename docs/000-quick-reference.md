# CodeMAID Integration - Quick Reference Guide

## Project Location
- **Audit/Design Documents:** `/home/cuckaoccurs/Desktop/NewYou/`
- **Prompt Templates/Persona Examples:** `/home/cuckaoccurs/Desktop/Prompts/`

## Key Files Created

### 1. Architecture Audit
- `01-architecture-audit.md` - Multi-agent architectural analysis and final recommendation

### 2. Prompt Repository Structure
- `Prompts/personas.md` - Sample persona templates (senior dev, debugging expert, etc.)
- `Prompts/system-overrides.md` - System prompt patterns
- `Prompts/context-samples.md` - Context file templates

## Quick Start

### Basic Wrapper Setup
```bash
# 1. Create config directory
mkdir -p ~/.agents/{personas,memory,sessions}

# 2. Create config.json
cat > ~/.agents/config.json << 'EOF'
{
  "system_file": "/home/cuckaoccurs/.agents/system.md",
  "current_persona": "default",
  "memory_dir": "/home/cuckaoccurs/.agents/memory",
  "session_dir": "/home/cuckaoccurs/.agents/sessions"
}
EOF

# 3. Create codemaid-wrap script (see 02-implementation.md)
chmod +x codemaid-wrap
```

### Running CodeMAID with Configs
```bash
codemaid-wrap  # Loads your configured persona and context
```

### Switch Personas in TUI
- Command: `P` (toggle between personas)
- View current persona in status bar

## Implementation Status

- [x] Architecture analysis complete
- [ ] Basic wrapper script implementation
- [ ] Config manifest creation
- [ ] TUI command hooks
- [ ] Persona switching UI
- [ ] Session persistence

## Next Immediate Action
Start with `02-implementation.md` for the minimal working solution