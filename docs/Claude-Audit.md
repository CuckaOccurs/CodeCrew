# Claude Audit — NewYou Directory
**Date:** 2026-04-19
**Auditor:** Claude (claude-sonnet-4-6)

---

## What This Directory Is

A cross-AI comparison project. The same prompt was sent to 7 AI systems (ChatGPT, Claude, DeepSeek, Gemini, Grok, Perplexity, Qwen), each responding to a request to help design a local-first session manager TUI backed by a `~/.agents/` system. The directory also contains early architecture planning docs and a TODO list.

**The project goal:** A hidden `~/.agents/` runtime that gives any AI persistent memory, personas, tool access, and saved conversations — all local, no cloud, no fine-tuning.

---

## File Inventory

| File | Type | Summary |
|------|------|---------|
| `000-quick-reference.md` | Planning | Quick-start guide; most implementation steps still unchecked |
| `01-architecture-audit.md` | Architecture | Multi-agent analysis concluding on a bash-wrapper pattern |
| `ChatGPT.md` | AI Response | Structural breakdown + MVP roadmap; suggested git-style session branching |
| `Claude.md` | AI Response | Asked 6 clarifying questions before building anything |
| `DeepSeek.md` | AI Response | Full Python TUI code (Textual + SQLite + Ollama), ready to run |
| `document_inventory.md` | Reference | Catalog of personal files across `/home/cuckaoccurs/Projects/` |
| `Gemini.md` | AI Response | Go/Rust stack recommendation (Bubble Tea / Ratatui), clean architecture |
| `Grok.md` | AI Response | Complete Python TUI code (Textual), similar to DeepSeek but with dark CSS theme |
| `Perplexity.md` | AI Response | Cleanest framing; flagged the "sidestepping" language as a liability |
| `personality_summary.md` | Reference | Profile of the CuckaOccurs persona and Michael's philosophy |
| `Qwen.md` | AI Response | Tech stack comparison table, constraints/workarounds table, async-aware |
| `todo_edits.md` | TODO | Audit cleanup list; all items unchecked |

---

## AI Response Comparison

### Who gave runnable code
- **DeepSeek** — Most complete Python implementation. Includes DB schema, TUI layout, Ollama integration, memory injection logic. Closest to a working MVP.
- **Grok** — Full Python TUI code with dark CSS theme. Slightly less complete but more aggressively styled.
- **Qwen** — Provided skeletons/stubs; noted async concerns (aiosqlite, asyncio queues) that DeepSeek/Grok glossed over.

### Who gave the best architecture
- **Perplexity** — Clearest separation of concerns. Only one to flag that "sidestepping training" framing is risky positioning. Recommended clean MVP scope.
- **Gemini** — Best stack recommendation if you want performance (Go + Bubble Tea). Explicitly covers the "thoughts" Chain-of-Thought staging pattern.
- **ChatGPT** — Strongest on product thinking. The git-style session branching idea (`session A → branch: experiment-1`) is worth stealing.

### Who asked questions first
- **Claude (web)** — Only AI that asked 6 targeted clarifying questions before generating anything. Slower start, but would have produced more targeted output.

### What everyone agreed on
1. SQLite is the right storage layer for sessions/messages/memory.
2. YAML or JSON for persona profiles.
3. Textual (Python) or Bubble Tea (Go) for the TUI.
4. Memory = short-term (last N turns) + episodic (summaries) + semantic (optional embeddings).
5. Tools/skills as local Python functions called via structured AI output.

---

## State of Work

**Designed:** The architecture is well-covered across multiple documents. No gaps in the conceptual layer.

**Not built yet (based on `000-quick-reference.md` checklist):**
- Basic wrapper script
- Config manifest
- TUI command hooks
- Persona switching UI
- Session persistence

**Directory conflicts to resolve (`todo_edits.md`):**
- `.agent/` vs `.agents/` — two directories exist, one needs to win
- Multiple resume files across the system
- CodeMAID consolidated copy not yet done

---

## Observations

**The bash wrapper idea (`01-architecture-audit.md`) is the wrong starting point.** A bash wrapper around CodeMAID is a dead end — it limits the TUI to CodeMAID's I/O shape. The Python Textual approach from DeepSeek/Grok is the right foundation because it owns the session loop directly.

**DeepSeek's code is the closest to runnable.** It has the DB schema, persona loading, session creation, message history, and Ollama integration in one file. It's the natural starting point. The Grok version is nearly identical but adds a nicer CSS theme — merge the two.

**The async issue is real.** Qwen is the only AI that flagged it: mixing synchronous SQLite calls inside a reactive Textual app will cause UI freezes. Use `aiosqlite` from the start, not sqlite3. This is a day-one architectural decision.

**Perplexity's caution is worth heeding.** Framing this as "sidestepping Unsloth and agent training" sounds like you're bypassing safety guardrails. The real pitch is cleaner: *local-first orchestration, user-owned memory, zero cloud dependency*. That framing is also more accurate — you're doing prompt engineering + retrieval, not actually retraining anything.

**The git-style session branching idea (ChatGPT) is the killer feature.** None of the other AIs mentioned it. A research session that branches like a git repo turns this from a chat wrapper into an actual thinking tool.

---

## Recommended Next Step

Start from DeepSeek's `session_manager.py`, make two immediate changes:
1. Replace `sqlite3` with `aiosqlite` throughout.
2. Add the session branching schema (parent_session_id column on the sessions table).

Then wire in the persona YAML loader from Gemini's spec and the CSS theme from Grok. That gets you a working MVP in one file before touching the TUI layout or tool system.

The `~/.agents/` directory structure from DeepSeek/Qwen is solid:

```
~/.agents/
├── config.yaml
├── agents.db
├── personas/
│   └── default.yaml
├── sessions/
├── skills/
└── memory/
```

Resolve the `.agent/` vs `.agents/` conflict first — pick `.agents/`, move everything there, delete the other.
