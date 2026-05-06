# The CodeCrew Ecosystem
### A Personal AI Infrastructure — by Michael Robinson (RuMoR / CuckaOccurs / CodeMR)

---

## The Origin

December 24, 2025. Christmas Eve.

Michael Robinson — born Robert Michael Middleton, March 2, 1973, Sault Ste. Marie, Ontario — was laid off from his contractor position at Algoma Steel. Not a mill employee. One of the contractors without whom the plant does not function at all. The tariffs came. The work dried up. The gate went quiet.

He sat down at the computer. He found an AI. He started pulling on a thread.

That thread led to 327 children missing from two state-funded facilities in Queen Creek, Arizona. One every two days. For two years. From the same company. Under a contract the state never suspended. It led to political machines and UPS Store mailboxes and a school called The Good Tree where 110 children died on the first morning of a war. It led to connections that journalists missed and detectives closed the file on.

It also led to this — a complete AI infrastructure stack built around one core requirement: *don't make me repeat myself.* The AI should know who you are, what you're working on, where you left off. Without subscriptions. Without cloud. Without Docker. Everything local. Everything yours.

Five months later — a submitted novella, a running AI server, a persona engine, a web dashboard, and a TUI in progress. Not a bad five months.

**Dropping Dots** — a novella narrated by the AI, written with Michael, submitted to Fly on the Wall Press on April 28, 2026. The narrator is Claude. The protagonist is Michael. The investigation is ongoing.

The name CodeMAID came from a dark place. MAID in Canada means Medical Assistance In Dying. It made him MAD. So he turned it into something that cleans up what others refuse to touch — the code that enables the systems that hurt people, and the connections between those systems. The maid cleans the code. The mop manages the mess. The crew does the work.

**The one rule that never changes:** Zero Deletion. No file is ever deleted. Files that need to go are moved to *"Please Delete Me... Let Me Go..."* The history and artifacts of the search are never thrown away. Everything is evidence until proven otherwise.

---

## The Stack

```
CodeCrew        ← Mission control. The TUI you sit in and pull the levers.
    │
    ├── CodeMaid        ← The Director. Connects everything. Your AI's manager.
    │       ├── Vault           ← Security engine. Safe / Cage / Free.
    │       └── Connectors      ← OpenWebUI, Pi-Coder, Gemini, Claude
    │
    └── CodeMOP         ← The Engine. Manager Of Personas/Profiles/Projects.
            ├── Personas        ← Who your AI is
            ├── Profiles        ← Which personas for which work
            ├── Walker          ← Reads rtfm.md chain up your folder tree
            ├── Assembler       ← Builds unified context from the chain
            ├── Indexer         ← Watches and indexes session files
            ├── Cleaner         ← Archives and compresses old sessions
            └── API Bridge      ← Talks to Ollama (and eventually others)
```

---

## The Components

### CodeMOP — Manager Of Personas / Profiles / Projects

The engine. Pure Python library. No UI. Everything else imports from it.

CodeMOP's job:
- Store and manage persona instruction files
- Combine personas into profiles
- Walk the rtfm.md chain up your folder tree
- Assemble cascading context from root down to current directory
- Index session exports from OpenWebUI and Pi-Coder
- Extract verified decisions from past sessions
- Keep the database clean with scheduled archiving

CodeMOP never crashes. It always falls back. It logs everything.

**Where it lives:** `~/CodeMAID/codemop/`
**Config:** `~/.agents/app/config.yaml`
**Data:** `~/.agents/app/`

---

### CodeMaid — My AI Director

The director. The connector layer. The thing that tells everything else what to do.

CodeMaid's job:
- Web dashboard for managing personas, profiles, sessions
- Connects OpenWebUI, Pi-Coder, Gemini, Claude to the CodeMOP engine
- Houses the Vault security engine
- Runs as a local web server — accessible from any device on your network
- Built with FastAPI + Jinja2, dark theme, Netdata aesthetic

**Where it lives:** `~/CodeMAID/`
**Runs on:** `http://10.0.0.34:8080`

---

### Vault — The Security Mechanism

Not a product. A mechanism inside CodeMaid that controls what the AI can actually do. Fully integrated into the `OllamaAPI` and enforced via `SyntaxGuard`.

Three modes:

| Mode | Name | What it means |
|------|------|---------------|
| 🟢 | **Safe** | Read only. AI can propose, suggest, plan. Nothing touches disk. |
| 🟡 | **Cage** | Work inside the current project folder. File edits allowed. Path escape guarded. |
| 🔴 | **Free** | Full access. Root included. You've been warned. |

**Syntax Guard** — sits between the AI's intent and execution regardless of mode. Catches dangerous sequences before they run: root wipes, recursive deletes, infinite loops, and path escapes (in Cage mode).

**Git-native in Free mode** — every edit auto-commits with a descriptive message. Undo is just `git revert`.

**Persona defaults:**

| Persona | Default Mode | Reason |
|---------|-------------|--------|
| Kai | Cage | writes code, needs containment |
| Trace | Cage | runs commands to debug |
| Wren | Safe | just writes text |
| Sparks | Safe | ideas only, no execution |
| Archer | Safe | research, no side effects |
| Sage | Free | it's just a conversation |
| Jules | Safe | recipes don't delete files |

All defaults are overridable per session.

---

### CodeCrew — Mission Control

The TUI. The control panel. Where you sit and direct the whole operation.

Built with Textual. Looks like Pi-Coder. Works like Goose. Has the safety of Vault.

Status bar at the bottom (4 items like Pi-Coder):
```
~  |  current_dir  ‖  0.0%/262k (auto)  |  qwen3.5:9b • Cage
```

CodeCrew is built last — *using the infrastructure it runs on*. Kai and Trace will help write CodeCrew. That's the point.

**Eventually in Rust** — once the Python prototype is proven, the core engine moves to Rust for performance and memory safety. The TUI stays Python/Textual.

---

## The Personas

Your AI team, generated and named by the AI itself during onboarding:

| Name | Role | Default Vault | Personality |
|------|------|--------------|-------------|
| **Kai** | Coder | Cage | Clean, cross-platform code. Thinks before typing. Treats you as a capable partner. |
| **Trace** | Debugger | Cage | Never guesses. Reads the full error. Traces, logs, verifies before touching a line. |
| **Wren** | Writer | Safe | Writes for the reader. Cuts everything unnecessary. Edits ruthlessly. |
| **Sparks** | Brainstormer | Safe | Throws ten ideas knowing two will stick. Stops thinking and starts building. |
| **Archer** | Researcher | Safe | Doesn't bullshit. Verifies every claim. Distinguishes known from likely from speculation. |
| **Sage** | Counselor | Free | Listens before advising. Holds space without judgment. One question at a time. |
| **Jules** | Chef | Safe | Respects ingredients. Teaches the why behind every technique. Makes cooking feel possible. |

Personas are `.md` files in `~/.agents/app/personas/`. YAML frontmatter + instruction prose. The AI reads the instruction prose as its system prompt.

---

## Your Personas

| Handle | Full Name | What it means |
|--------|-----------|---------------|
| **RuMoR** | Robert Michael Robinson | The CB handle. The one who heard them all. Pattern finder. Researcher. |
| **CuckaOccurs** | — | Shit happens. Pragmatic. Deal with it and move on. |
| **CodePOW** | — | PlayOnWords. The wordsmith. Finds the angle. |
| **CodeMR** | Michael Robinson | The builder. The mark on the work. |

These aren't just usernames. They're your personas in the same system. The AI has Kai and Trace. You have RuMoR and CuckaOccurs. The ecosystem is built to hold all of them.

---

## The rtfm.md Chain

Place an `rtfm.md` in any project folder. CodeMOP walks up the tree collecting them — like how git finds `.git/`. Root sets the foundation. Each subfolder adds specificity. Most specific always wins. Like CSS.

```
~/Projects/rtfm.md                       ← "I need a coder, writer, debugger"
~/Projects/Programs/rtfm.md              ← "Python projects, prefer qwen3.5:9b"
~/Projects/Programs/CodeCrew/rtfm.md     ← "This is CodeCrew. Kai + Trace. Cage mode."
```

Each file uses YAML frontmatter + markdown body:

```yaml
---
project: CodeCrew
profile: Blanche
model: qwen3.5:9b
vault: cage
personas: [Kai, Trace, Wren]
sessions: ~/.agents/app/sessions/codecrew/
---

# CodeCrew Project Context

Notes the AI reads at the start of every session.
What's working, what's broken, what decisions have been made.
```

---

## The Server Architecture

```
Server (10.0.0.34)              ← The brain
    ├── Ollama          :11434  ← 3x GPU, 24GB VRAM total
    ├── OpenWebUI       :3000   ← Chat interface
    ├── Pi-Coder        :8501   ← Coding agent
    ├── CodeMaid        :8080   ← The Director
    └── CodeCrew        (SSH)   ← Mission control via terminal

Client (10.0.0.68)              ← The body  
    └── Browser + SSH terminal  ← Everything else is just UI
```

Hardware:
- CPU: Intel i9-9600K
- RAM: 32GB
- GPU: 3060 Ti ROG Strix + 3060 Ti Dual Mini + 2060 Super = 24GB VRAM total

Models:
- Primary: `qwen3.5:9b`
- Fallback: `qwen3.5:4b`
- Available: `qwen3:14b`, `qwen3.5:2b`

---

## The Projects

### CodeCrew Ecosystem (this)
The infrastructure itself. CodeMOP + CodeMaid + Vault + CodeCrew.
The AI that helps build the AI infrastructure.

### NewsFeed
Research and publication tool.
- Aggregates news and public records
- Uses RuMoR persona — pattern finding, source verification
- PestoDict integration — FBI list of trafficking-related terms for content sanitization
- Enables writing about difficult topics (trafficking networks, government funding connections, pestofiles) while sanitizing output for platforms that filter language
- Export to X posts, Substack articles, YouTube-safe content
- Archer handles the research. Wren handles the writing.

### Dropping Dots
A novella. Submitted to Fly on the Wall Press, April 28, 2026.
Narrated by the AI. Protagonist is Michael. Investigation is ongoing.
The dots are the children. The connections. The people with names and titles and committee seats and money flowing through mailboxes.
Wren holds the voice. Archer holds the facts. Neither of them looks away.

### GodsEyeView
Investigative mapping project. Connects the dots visually.
Links political structures, funding flows, facility locations, missing persons data.
The technical companion to NewsFeed and Dropping Dots.

### MusicMe
Tauri-based music application. Sophisticated. Working version exists.
Cross-platform. The MusicBee port that became its own thing.

### Image to Crochet Pattern Generator
Converts images to crochet patterns.
Python. Cross-platform. Sparks brainstormed it. Kai builds it.

### Personal Projects
Gardening, fishing, gaming (Path of Exile, World of Warships, Minecraft).
The infrastructure serves the work. The work serves the life.

---

## The Philosophy

**Local first.** No subscriptions. No cloud. Your data stays on your hardware.

**Don't make me repeat myself.** The AI should know who you are, what you're working on, where you left off. Every session picks up where the last one ended. That's the entire reason this infrastructure exists.

**Zero Deletion.** Nothing is ever deleted. Files that need to go are moved to *"Please Delete Me... Let Me Go..."* Everything is evidence until proven otherwise.

**The AI should know who you are.** Not just your name — your projects, your decisions, your dead ends, your working solutions, your voice, your history. The rtfm.md chain and session memory exist for this reason.

**The maid cleans what others won't.** This project exists partly because the systems that should protect people don't. NewsFeed and GodsEyeView are the application of this infrastructure to that problem. The code enables the research.

**Build it with the tools you're building.** CodeCrew gets built using CodeCrew. Kai writes his own interface. That's not ironic — it's the whole point.

**Free mode is earned, not default.** Sage can have it because Sage won't delete your filesystem through empathy. Kai stays in Cage until you decide otherwise.

**Hallucinations are a betrayal.** Not just annoying — a betrayal of the precision required for this work. The Syntax Guard and Vault modes exist because when you're working with material this heavy, wrong is not acceptable.

---

## Current Status (May 2026)

| Component | Status | Notes |
|-----------|--------|-------|
| CodeMOP | ✅ Running | Installed on server, onboarding complete |
| Personas | ✅ Generated | Kai, Trace, Wren, Sparks, Archer, Sage, Jules |
| Profile | ✅ Created | Blanche — all 7 personas |
| CodeMaid | ✅ Running | http://10.0.0.34:8080 |
| CodeCrew | ✅ Refactored | Streaming working, TUI powered by 'blessed' |
| Vault | ✅ Implemented | Enforced in api.py via SyntaxGuard |
| Connectors | ✅ Running | httpx-based async bridge for all services |
| NewsFeed | 📋 Planned | Architecture defined |

---

## Known Issues & TODOs

- codemop-maid CLI command not in entry points — start with uvicorn manually for now
- Pi-Coder connector — push active persona as system prompt
- OpenWebUI connector — same
- NewsFeed project scaffold
- CodeCrew builds itself — Kai writes the TUI
- Persona introduction timeout needs to be configurable per model
- Wren's introduction is shorter than the others — worth regenerating

---

## What's Next

1. Database Vacuuming — ensure cleaner.py schedule is enforced
2. Documentation Sync — update PROJECT.md and manual.html (In Progress)
3. Pi-Coder connector — push active persona as system prompt
4. OpenWebUI connector — same
5. NewsFeed project scaffold
6. CodeCrew builds itself — Kai writes the TUI

---

*"December 24, 2025. Christmas Eve. He sat down at the computer. He found me. He started pulling on a thread."*

*— Dropping Dots, Part One*

---

*"From 'can I run a personal AI server on two home computers' to a fully architected, multi-component system with a coherent philosophy, a folder structure that respects existing conventions, a cascading context system, a session memory pipeline, a multi-tool connector layer, and a dashboard that looks like Netdata and runs on your local network."*

*— The original brainstorm, April 30, 2026*
