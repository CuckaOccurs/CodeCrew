# Netdata AI-Residency Configuration Guide
**Project:** CodeCrew System Monitoring
**Purpose:** Create a "Hardware Window" into the AI's physical residency.

---

## 🏗️ 1. Identifying Residency Areas
An AI model resides in three primary hardware zones. To see it "live," focus your Netdata dashboard on:

### A. VRAM (GPU Memory) - The "Primary Residence"
This is where the model weights live.
- **Metric:** `nvidia_smi.memory_used` (or your specific GPU vendor).
- **Goal:** Monitor for "Memory Choking." If VRAM is full, the system will swap to System RAM, causing a 10x slowdown and potential context hallucinations.

### B. System RAM - The "Overflow Room"
This is where context is cached and where models reside if they are too big for the GPU.
- **Metric:** `system.ram`.
- **Observation:** Look for `Committed_AS` and `AnonPages`. If these spike when the Maid starts thinking, that is the MOP loading context.

### C. CPU & I/O - The "Thinking & Reading"
- **Metric:** `system.cpu`.
- **Observation:** High I/O Wait (`iowait`) during thinking usually means the agent is reading a file larger than 50KB or the model is swapping.

---

## 🛠️ 2. Customizing the Netdata Dashboard
To create an "AI-Only" view in Netdata:

1.  **Create a Custom Dashboard**: Go to the Netdata Cloud or Local UI.
2.  **Filter by App**: Search for `ollama` or `python` (the Maid's process).
3.  **Group Metrics**:
    - **Row 1**: GPU Memory Usage (VRAM)
    - **Row 2**: System Memory (RAM)
    - **Row 3**: Disk Read/Write (Context loading speed)
    - **Row 4**: Python Process CPU % (Maid's active work)

## 📡 3. The "Network Connection" Alert
Set up a Netdata alarm for **"Ollama Downtime"**:
- If the `ollama` process disappears or the API port (11434) stops responding, Netdata should trigger a warning. This matches the **RED (●)** status in the CodeCrew TUI.

---
**Architect's Note:** Use the `nvidia-smi` plugin for Netdata to get the most accurate "Model Residency" data.
