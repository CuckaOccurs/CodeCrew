# Architecture Audit: CodeMAID + Agents Integration
**Date:** $(date)
**Status:** Analysis Complete

## Problem Statement
How to hook CodeMAID TUI to load `~/.agents/` configuration without modifying CoreMAID source code.

## Multi-Agent Analysis Summary

### Agent 1: Architectural Approach
**Core Insight:** Use a config-driven bridge between systems.

**Recommendation:**
- Create `~/.agents/config.json` as central manifest
- `codemaid-wrapper.sh` reads manifest and loads configs
- Environment-based connection: `codemaid-wrap` wrapper script

**File Structure:**
```
~/.agents/
  config.json       # Master manifest
  system.md         # System prompt
  personas/
    default.md      # Default persona
    developer.md    # Developer persona
  context.md        # User context
  memory/           # Long-term memory
```

**Example config.json:**
```json
{
  "system_file_path": "/home/user/.agents/system.md",
  "persona_file_path": "/home/user/.agents/personas/default.md",
  "context_file_path": "/home/user/.agents/context.md",
  "memory_dir": "/home/user/.agents/memory",
  "session_dir": "/home/user/.agents/sessions"
}
```

### Agent 2: User Experience
**Core Insight:** Make persona switching seamless in TUI.

**Recommendation:**
- TUI command: `P` to switch personas
- Context display in status bar
- Save chat history to `~/.agents/sessions/`

**Key Features:**
- Quick persona switching from TUI
- View current persona in UI
- Persist context across sessions
- Clean separation between personas

### Agent 3: Security
**Core Insight:** Explicit opt-in for config loading, no auto-assumption of dangerous parameters.

**Recommendation:**
- Only load configs explicitly listed in `config.json`
- No execution of code from configs
- Secrets separated from system prompts
- File permissions on `~/.agents/`

**Safety Checklist:**
- [ ] Config files are read-only
- [ ] No system prompt injection
- [ ] Context files are human-editable
- [ ] Secrets never auto-loaded

## Final Architecture: Hybrid Approach

**Winner:** A bash wrapper script (`codemaid-wrap`) that:
1. Reads `~/.agents/config.json`
2. Concatenates system + persona + context into prompt
3. Calls `codemaid` as subprocess
4. Captures stdout/stderr and forwards to TUI
5. Saves conversation state to `sessions/`

**Why:** Simple, no external dependencies, directly usable with existing CodeMAID.

---

**Architectural Decision:** Proceed with Bash Wrapper Pattern
**Complexity:** Low (shell scripting)
**Extensibility:** High (config-driven)
**Maintainability:** Easy to understand and modify

## Files Modified
- N/A (Design phase)

## Next Steps
1. Implement wrapper script
2. Create config manifest
3. Add TUI commands for persona switching
4. Test with multiple personas
5. Document usage