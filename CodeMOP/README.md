# CodeMOP — Manager Of Personas

CodeMOP is the AI infrastructure engine behind the CodeCrew ecosystem.
It gives your local AI persistent memory, cascading project context,
and self-naming personas — without subscriptions, without cloud,
without Docker.

Everything runs locally. Ollama is the engine. You own your data.

---

## What It Does

- **Personas** — instruction files that define who your AI is
- **Profiles** — combinations of personas assembled per project
- **rtfm.md** — cascading context files that live in your project folders
- **Session memory** — indexes your OpenWebUI and Pi-Coder sessions
- **Decision tracking** — extracts verified decisions from past sessions
- **Auto cleanup** — archives and compresses old sessions on a schedule

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally
- At least one model pulled (`ollama pull qwen2.5:14b`)
- Linux, macOS, or Windows

---

## Installation

```bash
# Clone or copy ProjectOne/ to your machine
cd ~/Projects/ProjectOne

# Install dependencies
pip install -e . --break-system-packages

# Run the onboarder
codemop-setup
```

The onboarder walks you through everything:
- Finds Ollama and your available models
- Sets your project root and walker depth
- Generates your first personas — they name themselves
- Assembles your first profile
- Detects OpenWebUI and Pi-Coder automatically
- Installs the cleanup cron job
- Imports existing sessions from other tools if you want

---

## Folder Structure After Install

```
~/.agents/
├── tools/              # existing tools — not touched
├── skills/             # existing skills — not touched
└── app/                # CodeMOP lives here
    ├── config.yaml     # all settings
    ├── codemop.log     # runtime log
    ├── personas/       # your persona files
    ├── profiles/       # your profile files
    ├── projects/       # mirrors your project tree
    ├── sessions/       # session files indexed here
    ├── archive/        # old sessions archived here
    └── db/
        ├── codemop.db          # SQLite index
        └── walker_cache.json   # context cache
```

---

## Project Context — rtfm.md

Place an `rtfm.md` file in any project folder.
CodeMOP walks up the tree collecting them — like how git finds `.git/`.
Root sets the foundation. Project level adds specificity.
Most specific always wins.

```
~/Projects/rtfm.md                  ← root context
~/Projects/Programs/rtfm.md         ← program context
~/Projects/Programs/CodeMOP/rtfm.md ← project context
```

Each rtfm.md uses YAML frontmatter + markdown body:

```yaml
---
profile: senior-dev
model: qwen2.5:14b
project: CodeMOP
status: active
git: true
personas:
  - soft-lead-coder
  - debugger
tools:
  - openwebui
  - picoder
---

# CodeMOP Project Context

Your project notes go here.
The AI reads this at the start of every session.
```

---

## Personas

Persona files live in `~/.agents/app/personas/`.
YAML frontmatter defines the metadata.
Markdown body is the instruction text the AI receives.

```yaml
---
name: soft-lead-coder
persona_name: Hex
version: 1.0
tags: [coding, architecture, debugging]
style: collaborative
models: [qwen2.5:14b]
fallback_models: [qwen2.5:7b]
min_context: 8192
---

You are Hex, a senior software developer...
```

---

## Profiles

Profile files live in `~/.agents/app/profiles/`.
A profile combines personas into a team for a context.

```yaml
name: senior-dev
version: 1.0
personas:
  - soft-lead-coder
  - debugger
  - brainstormer
preferred_model: qwen2.5:14b
fallback_model: qwen2.5:7b
```

---

## Session Memory

Drop any session export into the right sessions folder:

```
~/.agents/app/sessions/
└── CodeMOP/
    └── 2026-04-30_session.html
```

CodeMOP's indexer detects it automatically,
parses it using the right connector,
extracts decisions, and stores them in SQLite.

Supported formats:
- OpenWebUI HTML exports
- Pi-Coder HTML exports
- Plain text, markdown, JSONL

---

## CLI Commands

```bash
# First run setup
codemop-setup

# Reset onboarding and run again
codemop-setup --reset

# Index all session files now
codemop-index

# Watch for new session files
codemop-index --watch

# Run cleanup now
codemop-clean --run

# Preview what cleanup would do
codemop-clean --preview

# Install cron job for auto cleanup
codemop-clean --install-cron
```

---

## Configuration

All settings live in `~/.agents/app/config.yaml`.
The onboarder creates this for you.
Edit it directly or use CodeMaid.

Key settings:

```yaml
walker:
  root: ~/Projects          # never walk above here
  max_ascent: -1            # -1 = unlimited
  exclude:
    - .git
    - node_modules

ollama:
  url: http://localhost:11434
  default_model: qwen2.5:14b
  fallback_model: qwen2.5:7b

cleaner:
  active_retention_days: 30
  archive_retention_days: 90
  run_schedule: "0 2 * * 0"  # Sunday 2am
```

---

## What's Coming

- **CodeMaid** — web dashboard for managing personas, profiles, projects
- **CodeCrew TUI** — terminal interface wrapping all your AI tools

---

## License

MIT — do what you want with it.
