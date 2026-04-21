# Second & Third Set of Eyes — Recommendation Guide
**Date:** 2026-04-19
**Context:** CachyOS, Ollama running, CodeMAID as primary tool

---

## The Strategy First

The point of a second/third set of eyes isn't a backup — it's a **different perspective**. Different models have genuinely different blind spots, strengths, and failure modes. A review that agrees with your primary tool is noise. One that catches something different is signal.

**Ideal stack:**
```
First eyes  →  Claude Code (you, right now) — reasoning, architecture, big picture
Second eyes →  Local model via Ollama — fast, free, private, different training data
Third eyes  →  One cloud option with different lineage — catches what both miss
```

---

## Your Current Setup Advantage

You already have everything you need for a free second set of eyes:

- **Ollama is running** — zero extra cost for local model reviews
- **CodeMAID supports multiple providers/profiles** — `codemaid . --profile <name>` switches model instantly
- **The `--provider` flag** — point CodeMAID at a completely different backend with one flag

Before installing anything new, the second set of eyes you already have:

```bash
# Primary session (Claude/Anthropic)
codemaid . --profile claude

# Second eyes — different local model, same interface
codemaid . --provider ollama --model deepseek-coder:latest

# Third eyes — yet another local model
codemaid . --provider ollama --model qwen3:14b
```

Same tool, different brain. No new software, no new cost.

---

## Free Options Ranked for Your Setup

### Tier 1 — Already Have It, Use It Now

#### CodeMAID with a Second Ollama Model
- **Cost:** Free (local compute only)
- **Setup:** Zero — already done
- **Best for:** Code review, architecture questions, catching logic errors
- **Weakness:** Same interface as primary — comfort bias, you'll frame prompts similarly
- **Command:**
  ```bash
  codemaid . --provider ollama --model deepseek-coder:latest
  ```

---

### Tier 2 — Install Once, Free Forever

#### Aider + Ollama
- **Cost:** Free (BYOK — bring your own keys, Ollama = no keys needed)
- **Install:** `pip install aider-chat` or `pipx install aider-chat`
- **Best for:** Git-native review, seeing diffs the way git sees them, auto-commit workflow
- **Weakness:** More opinionated about changing your code — sometimes you just want it to *look*, not *touch*
- **Why it's a good second eye:** Git-aware by default. Understands diffs, commit history, changed files. Different angle than a pure chat agent.
- **Commands:**
  ```bash
  # Read-only review mode (doesn't edit anything)
  aider --model ollama/deepseek-coder:latest --no-auto-commits --read file.py

  # Full session with Ollama
  aider --model ollama/qwen3:14b
  ```
- **Note:** You already have aider history in your old openpaws dev files — you've used this before.

---

#### mods (by Charm)
- **Cost:** Free/OSS
- **Install:** `yay -S mods` or download binary from charm.sh
- **Best for:** Quick pipe-based reviews — lowest friction of anything on this list
- **Weakness:** Stateless, no project context, one-shot only
- **Why it's a good second eye:** Forces you to be specific about what you want reviewed. No fluff.
- **Works with:** Ollama out of the box
- **Commands:**
  ```bash
  # Pipe a file directly
  cat agent.py | mods "what's wrong with this code"

  # Pipe a diff
  git diff | mods "review these changes for bugs"

  # Multiple files
  cat *.py | mods "find security issues"
  ```
- **Config for Ollama** (`~/.config/mods/mods.yml`):
  ```yaml
  default-model: ollama/qwen3:14b
  apis:
    ollama:
      base-url: http://localhost:11434/v1
      models:
        qwen3:14b:
          max-input-chars: 200000
  ```

---

#### Oterm
- **Cost:** Free/OSS
- **Install:** `pipx install oterm`
- **Best for:** Conversational review in a proper TUI — closest to what you're building with ChatMAID
- **Weakness:** Just a chat wrapper around Ollama, no code awareness
- **Why it's a good second eye:** Nice TUI, model switching built in, multiple conversations open at once
- **Commands:**
  ```bash
  oterm   # launches TUI, pick model, start chatting
  ```

---

#### llm (Simon Willison's CLI)
- **Cost:** Free/OSS
- **Install:** `pipx install llm && llm install llm-ollama`
- **Best for:** Quick CLI queries, logging all conversations automatically, comparing model outputs
- **Weakness:** Minimal, no project context
- **Why it's a good second eye:** Keeps a local SQLite log of every query — good for your "Ai Story" research angle
- **Commands:**
  ```bash
  llm -m ollama/qwen3:14b "review this" < agent.py
  llm logs   # see all past queries
  ```

---

### Tier 3 — Free Cloud Options (Requires Account)

#### Gemini CLI
- **Cost:** Free with Google account (60 requests/min, 1500/day)
- **Install:** `npm install -g @google/gemini-cli` then `gemini auth`
- **Best for:** Large codebase reviews — 1M context window means it can read your entire project at once
- **Weakness:** Reasoning quality on complex problems is noticeably weaker than Claude or GPT-4 class models. Good for "read everything and find inconsistencies", weak for "figure out why this architecture is wrong"
- **Why it's still worth having:** Context window. Claude Code has limits. Sometimes you need something that can hold the entire codebase in one shot.
- **Commands:**
  ```bash
  gemini   # interactive TUI
  gemini -p "review the session management in this project" < sessions/storage.py
  ```

#### GitHub Copilot CLI
- **Cost:** Free tier (2000 completions/month)
- **Install:** `gh extension install github/gh-copilot`
- **Best for:** GitHub-integrated workflows — PR reviews, explaining git history
- **Weakness:** Not a full agent, more of a suggestion tool. Free tier is limited.
- **Honest take:** Less useful as a "set of eyes" and more useful as a "autocomplete in the terminal". Not recommended as second eyes.

---

## Recommended Combinations

### Option A — Fully Local (Zero Cloud Cost)
```
First:   Claude Code (API billing as normal)
Second:  CodeMAID + deepseek-coder via Ollama
Third:   Aider + qwen3:14b via Ollama
```
**Pros:** Private, free after compute, works offline
**Cons:** Local models are weaker than frontier models on hard problems

---

### Option B — Local + One Cloud Second
```
First:   Claude Code
Second:  CodeMAID + deepseek-coder (local, fast, free)
Third:   Gemini CLI (free, cloud, huge context)
```
**Pros:** Best coverage — local speed + cloud context window
**Cons:** Gemini quality varies, requires Google account

---

### Option C — The Research Setup (for "Ai Story" work)
```
First:   Claude Code
Second:  mods (pipe-based, logs everything, forces precision)
Third:   llm CLI (auto-logs to SQLite, comparable outputs)
```
**Pros:** Every query is logged and comparable — good for documenting how different models respond
**Cons:** No persistent context, one-shot only

---

## Ollama vs llama.cpp — Which Backend to Run Under Your Tools

All the Tier 2 tools above (Aider, mods, oterm, llm) can point at either Ollama or a raw llama.cpp server. Same model, different runner. Here's the practical difference:

| Feature | Ollama | llama.cpp (raw) |
|---------|--------|-----------------|
| Setup time | ~5 minutes | 30+ minutes |
| Running a model | `ollama run deepseek-coder` | compile → convert → `./llama-cli` |
| Customization | Limited (Modelfile) | Full — context size, batch, threads, GPU layers |
| Hardware tuning | Automatic | Manual (`-ngl`, `--threads`, etc.) |
| OpenAI-compat API | Built in (`/v1`) | Built in (`--server` flag) |
| Portability | Easy | Complex path/binary management |
| Same model quality | Yes (95%+) | Yes — it's the same GGUF |

**The honest answer:** Ollama is llama.cpp under the hood. You get the same model, same quantization, same output. Ollama just wraps it with a clean API, auto-downloads models, and handles GPU detection for you.

**When to use raw llama.cpp instead:**
- You need to control exact GPU layer split (`-ngl 35` vs `-ngl 40`)
- You're running on unusual hardware (multiple GPUs, specific VRAM constraints)
- You want to test specific context window sizes or batch settings
- Benchmarking/profiling model performance

**For second/third set of eyes use:** Ollama is the right call. You already have it. The 5% performance gap from not hand-tuning llama.cpp doesn't matter for code review — model quality matters, not inference speed.

**If you later want llama.cpp for optimization:**
```bash
# Install on CachyOS
yay -S llama-cpp

# Run as OpenAI-compat server (drop-in for Ollama URL)
llama-server --model ~/.ollama/models/blobs/<model-hash>.gguf \
             --port 8080 --ctx-size 32768 --n-gpu-layers 40
```
Then just change `http://localhost:11434` → `http://localhost:8080` in any tool config.

---

## Quick Install Script

```bash
# Install everything useful from Tier 2
pipx install aider-chat
pipx install oterm
pipx install llm
llm install llm-ollama

# mods (via AUR on CachyOS)
yay -S mods

# Gemini CLI (optional, requires Node)
npm install -g @google/gemini-cli
```

---

## The Real Answer

Until ChatMAID is connected to CodeMAID, your best free second set of eyes is:

1. **CodeMAID with a different Ollama model** — zero setup, works today
2. **mods** — install in 30 seconds, pipe anything at it

Everything else is nice-to-have. The architecture you're building (ChatMAID → CodeMAID → any model) means eventually you'll have second/third eyes built into the tool itself — just point two instances at different models.
