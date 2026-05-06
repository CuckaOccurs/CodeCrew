# CodeCrew: Sovereign AI Infrastructure

<p align="center">
  <img src="assets/banner.jpg" alt="CodeCrew Banner" width="100%">
</p>

## The Manifesto: End the AI "Black Box"
You don't need a containerized bubble. You don't need a subscription. You don't need to guess if your AI is phoning home or why it "forgot" your project requirements. 

**CodeCrew** is a paradigm shift. We have moved away from the "App as a Container" model and toward a **"System-as-Filesystem"** architecture. Your AI isn't an application; it is a permanent, transparent, and hackable layer of your operating system.

---

## 🔱 The Three Pillars

*   **[CodeCREW](./CodeCREW) — The Cockpit (TUI)**
    A lightweight, high-performance interface for real-time interaction. Built to stay out of your way and focused on the work.

*   **[CodeMAID](./CodeMAID) — The Director (Dashboard)**
    Your management plane. FastAPI-backed, HTMX-powered. It doesn't just manage settings—it governs the integrity of the agent ecosystem.

*   **[CodeMOP](./CodeMOP) — The Engine (Manager Of Personas)**
    The heart of the beast. It provides **Long-Term Memory** (SQL-backed decisions), **Short-Term Context** (KV-Buffer), and **Directory-Aware Persona Injection** (rtfm.md).

---

## 🧠 Why CodeCrew is Different

### 1. Filesystem-as-API
We don't hide your AI’s "brain" inside an opaque Docker container. 
- **Skills are scripts:** Want a new AI skill? Drop a script in `~/.agents/tools/`.
- **Memory is persistent:** Decisions are markdown files. You can `grep` your AI’s history. You can edit its memory. You can physically prune its decision-tree.
- **Context is structural:** We don't "prompt" the AI; we provide `rtfm.md` files that define your project's *reality*.

### 2. Radical Transparency
The AI is under your supervision. 
- **Thought Monitoring:** A real-time `thought.log` gives you a window into the agent's intent *before* it touches your disk.
- **Action Guard:** No process is executed without an audit trail. You are the architect; the AI is the apprentice.

### 3. Hardware Sovereignty
Designed specifically for local dual-GPU rigs. It budgets your VRAM as a smart, self-managed resource—dynamically shifting between "Lean" and "Fat" models based on project complexity, not just hardware limits.

---

## 🚀 The Local-First Workflow
1. **Initialize:** `codemop-setup` audits your hardware and optimizes your agent environment.
2. **Work:** Move into any project folder. The AI "discovers" the agent it needs based on the `rtfm.md` symlink.
3. **Govern:** Use the Dashboard to review decisions, prune memory, and audit the agent's research activity.

---

<p align="center">
  <img src="assets/mascot.png" alt="CodeCrew Mascot" width="150">
</p>

<p align="center">
  <em>The AI is not a service. It is a local intelligence, rooted in your filesystem, governed by your truth.</em>
</p>

---
## 📜 License
MIT — Michael Robinson (RuMoR / CuckaOccurs)
