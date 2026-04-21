Local AI Session Manager TUI Design
DeepSeek terminal option comparison
Local AI Agent Setup Guide
NewsFeed Tool for Investigative Journalism
Local AI Session Manager TUI Design
I am trying to write a session mananger tool that allows one to use a tui to connect to an APP * built. That is a hidden /home/user/.agents system that turns all your ai's tools and skills local, and also a built in session manager turn your cli into a memory rich, instructions personas profiles that live on your device that allows your ai to have a memory, thoughts , full on convrsations saved locally in a funtional DB for research or personal projects that make your AI have a peronality that you taylor think of it as a way to side step unlsoth and agent training...

We need to understand the request: user wants to build a session manager tool with TUI to connect to an "APP" they built. That APP is a hidden system at /home/user/.agents that turns all AI's tools and skills local. Also built-in session manager turns CLI into memory-rich, instruction personas profiles that live on device, allowing AI to have memory, thoughts, full conversations saved locally in functional DB for research/personal projects, giving AI a personality tailored by user. They mention "side step unlsoth and agent training" – likely "Unsloth" (fine-tuning library) and agent training. So they want a local, persistent, persona-based AI interaction system with TUI, bypassing need for fine-tuning or external agent training.

The user is asking for help in writing such a tool. They might want architecture advice, code structure, or implementation details.

We need to provide a helpful response: explain how to design this system, components, TUI library choices (e.g., textual, rich, curses), database (sqlite), local LLM integration (Ollama, llama.cpp), session management, persona/prompt templates, memory storage (vector DB? or simple conversation history). Also note hidden directory .agents, tool/skill management.

Provide step-by-step guidance, code examples (Python likely), and considerations for privacy, local control.

Let's craft response.

I'll help you design and implement a local session manager with TUI that turns your CLI into a memory-rich, persona-driven AI companion — all stored in ~/.agents without relying on cloud or fine-tuning (bypassing Unsloth/agent training).

We'll build it in Python using:

    Textual for the TUI (rich, reactive)

    SQLite for conversation DB + metadata

    Ollama or llama.cpp for local LLM inference

    Prompt templating for personas and memory injection

1. Core Architecture
text

~/.agents/
├── config.yaml          # global settings, default persona
├── personas/            # YAML files defining agent personalities
│   └── mentor.yaml
├── skills/              # Python functions the AI can call (local tools)
│   └── calculator.py
├── sessions.db          # SQLite: conversations, memory vectors, thoughts
└── logs/                # raw conversation exports

Components:

    Session Manager – loads persona, manages conversation turns, compiles context.

    Memory Store – stores short‑term (last N messages) + long‑term (embeddings + SQLite FTS5 for search).

    Tool Executor – allows AI to invoke local functions (safe subset).

    TUI – chat interface with persona switcher, memory search, thought logs.

2. Database Schema (sessions.db)
sql

-- one row per conversation session
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    persona_name TEXT,
    created_at DATETIME,
    title TEXT
);

-- every message in a session
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    role TEXT,          -- 'user', 'assistant', 'thought'
    content TEXT,
    timestamp DATETIME,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

-- long-term memory key-value store
CREATE TABLE memory (
    key TEXT PRIMARY KEY,
    value TEXT,
    embedding BLOB,     -- optional for semantic search
    updated_at DATETIME
);

3. Persona & Memory Injection

Each persona YAML defines system prompt, memory style, and tool access.

Example ~/.agents/personas/mentor.yaml:
yaml

name: mentor
system_prompt: |
  You are a patient, wise mentor. Speak in short, reflective sentences.
  You remember past user challenges and gently refer to them.
memory:
  use_long_term: true
  recall_count: 5          # number of memory entries to inject
tools:
  - calculator

Memory injection logic (before each LLM call):

    Fetch last 6 conversation turns from DB.

    Perform keyword search on memory table (or semantic if embeddings exist).

    Build final prompt:

text

[System: {persona.system_prompt}]

[Long‑term memory you recalled]:
{memory_entries}

[Recent conversation]:
{last_turns}

User: {current_input}
Assistant:

4. Local Tool Calling

Allow the AI to output structured commands like [[tool:calculator|2+2]].
You parse, run in a sandboxed Python environment, and insert result as a system message.

Simple tool registry (skills/calculator.py):
python

def run(expr: str) -> str:
    try:
        return str(eval(expr, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error: {e}"

Execution safety:

    Use restricted mode (no file/network access) or run in a separate process with timeout.

5. TUI with Textual

Create a chat window, input box, and a side panel for memory search/persona switching.

Minimal app.py:
python

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Log, ListView, ListItem
from textual.containers import Horizontal, Vertical
from textual import events
from session_manager import SessionManager

class AgentTUI(App):
    CSS = """
    Horizontal { height: 1fr; }
    Log { border: solid $accent; }
    #sidebar { width: 30%; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield ListView(*[ListItem(label) for label in ["Mentor", "Sage", "Techie"]])
                yield Input(placeholder="Search memory...", id="mem_search")
            with Vertical():
                yield Log(id="chat_log")
                yield Input(placeholder="Your message...", id="msg_input")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "msg_input":
            user_msg = event.value
            log = self.query_one("#chat_log")
            log.write(f"[bold]You:[/bold] {user_msg}")
            event.input.clear()
            # Get AI response from SessionManager
            response = self.session_manager.chat(user_msg)
            log.write(f"[italic]AI:[/italic] {response}")

SessionManager (backend):
python

import sqlite3, yaml, subprocess
from datetime import datetime

class SessionManager:
    def __init__(self, db_path, persona_name):
        self.db = sqlite3.connect(db_path)
        self.persona = self._load_persona(persona_name)
        self.session_id = self._new_session()

    def _load_persona(self, name):
        with open(f"{os.environ['HOME']}/.agents/personas/{name}.yaml") as f:
            return yaml.safe_load(f)

    def chat(self, user_input):
        # 1. save user message
        self._save_message("user", user_input)
        # 2. fetch recent context + memory
        context = self._build_context()
        # 3. call local LLM (Ollama example)
        prompt = f"{context}\nUser: {user_input}\nAssistant:"
        result = subprocess.run(
            ["ollama", "run", "llama3.2", prompt],
            capture_output=True, text=True
        ).stdout.strip()
        # 4. parse any tool calls
        result = self._handle_tools(result)
        # 5. save assistant response
        self._save_message("assistant", result)
        return result

6. Long‑Term Memory & Thoughts

"Thoughts" are just messages with role='thought' inserted by the AI when you want to record a reflection.
Add a keybinding in TUI (e.g., Ctrl+T) that asks the AI: "Based on this conversation, write a short thought for your internal memory." Then save it as a thought.

Memory retrieval (semantic + keyword):

    For small projects, use SQLite FTS5 virtual table over memory.value.

    For vector search, store embeddings from sentence-transformers (all‑MiniLM‑L6‑v2) and compute cosine similarity.

Example memory insertion (after a meaningful exchange):
python

def remember(self, key, content):
    embedding = self._get_embedding(content)  # optional
    self.db.execute(
        "INSERT OR REPLACE INTO memory (key, value, embedding, updated_at) VALUES (?,?,?,?)",
        (key, content, embedding, datetime.now())
    )

7. Bypassing Unsloth / Agent Training

You don't need fine‑tuning because:

    Personas are pure prompt engineering (system + few‑shot examples).

    Memory is retrieved from a local DB at inference time (RAG).

    Tools are hardcoded Python functions, not learned.

This keeps your AI behaviour fully controllable, transparent, and adaptable without retraining.
8. Putting It All Together

File structure for your project:
text

my_agent_tui/
├── main.py               # runs the Textual app
├── session_manager.py    # logic above
├── tools.py              # tool registry
├── memory_store.py       # embedding & search
└── requirements.txt

Run:
bash

pip install textual ollama sentence-transformers pyyaml
python main.py

First launch creates ~/.agents with default persona and DB.
9. Next Steps / Customisation

    Add a /persona <name> command in TUI to switch personas mid‑session.

    Implement /memory search <query> to display past memories.

    Export conversations to Markdown or JSON for research.

    Add a /thought command that logs a thought without disrupting conversation.

Would you like me to elaborate on any specific part — e.g., tool sandboxing, embedding search performance, or TUI styling?

