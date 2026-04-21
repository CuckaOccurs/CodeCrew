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

1.  **Access Netdata**: Navigate to `http://localhost:19999` in your browser.
2.  **Create a Custom Dashboard**: Go to the Netdata Cloud or Local UI, find the option to create a new dashboard.
3.  **Filter by Process**: Search for `ollama`, `python` (for the CodeMAID engine), or `nvidia-smi` (for GPU).
4.  **Group Metrics**: Arrange the available charts into logical rows:
    *   **Row 1**: GPU Memory Usage (VRAM)
    *   **Row 2**: System Memory (RAM) Usage & Commit
    *   **Row 3**: Disk Read/Write Activity (especially I/O wait)
    *   **Row 4**: CPU Usage for relevant processes (Python, Ollama)

## 📡 3. The "Network Connection" Alert
Configure a Netdata alarm for **"Ollama Downtime"**:
- If the `ollama` process stops responding or the API port (11434) becomes unreachable, Netdata should trigger a warning. This visually aligns with the **RED (●)** status in the CodeCrew TUI.

---

**Architect's Note:** Ensure the `nvidia-smi` Netdata plugin is active for detailed GPU VRAM monitoring.
