# CodeMAID System Audit — Full System Sweep
**Date:** 2026-04-19
**Drives scanned:** /home/cuckaoccurs (nvme), /mnt/Data (sda1)

---

## Active Files (What CodeMAID Is Actually Running)

```
/home/cuckaoccurs/Projects/CodeMAID/codemaid/   ← CANONICAL SOURCE
~/.config/codemaid/                              ← Active config (audit.log, backups)
~/.agents/sessions/codemaid.db                  ← Session database
~/.agents/codemaid_memory.json                  ← Persistent memory
~/.agents/skills/                               ← Skills directory
~/.local/share/pipx/venvs/codemaid/            ← Installed binary
```

---

## All CodeMAID/OpenPaws Locations Found

| Location | Drive | What it is | Version | Action |
|----------|-------|-----------|---------|--------|
| `Projects/CodeMAID/codemaid/` | home | **ACTIVE SOURCE** | v3 current | Keep |
| `Projects/CodeMAID/resources/` | home | Dead flat copy inside active project | v1 (Apr 15) | **DELETE** |
| `Projects/LinuxSystemDiagnostics/THE-TODO/CodeMAID/CodeM.A.I.D/openpaws/` | home | Old git repo, intermediate version | v2 (Apr 17-18) | Decide* |
| `Projects/LinuxSystemDiagnostics/THE-TODO/CodeMAID/CodeM.A.I.D/backup-live-pre-v2/openpaws/` | home | Flat copy inside old git repo | v1 (Apr 15) | **DELETE** |
| `Projects/ToDo/SessionExports/CodeMaid/` | home | HTML export + reference doc | n/a | Keep |
| `.local/share/Trash/files/openpaws (1)/openpaws` | home | Already in trash | old | **EMPTY TRASH** |
| `.config/codemaid/` | home | Active config dir | current | Keep |
| `.config/openpaws/` | home | Orphaned old config | old | Delete after check |
| `.local/share/pipx/venvs/codemaid/` | home | Installed binary venv | current | Keep |
| `.agents/` | home | Runtime data (db, skills, sessions) | current | Keep |
| `agents/sessions/` | home | New AgentSessionLogger module (in dev) | new | Keep — not a duplicate |
| `/mnt/Data/Projects/apps/CodeMAID/BACKUP/codemaid/` | Data | Backup of v3 on Data drive | v3 backup | Decide** |
| `/mnt/Data/Projects/apps/CodeMAID/resources/` | Data | Flat v1 copy on Data drive | v1 (Apr 15) | **DELETE** |
| `/mnt/Data/Projects/apps/CodeMAID/tests/` | Data | Tests on Data drive | — | Decide** |

---

## Version Map

```
Apr 15  →  v1 "flat openpaws"
            Single cli.py (341 lines), single tools.py (412 lines)
            Locations: resources/ (×2 — home and Data), backup-live-pre-v2/

Apr 17-18 → v2 "modular openpaws"
            cli/ and tools/ split out
            Location: LinuxSystemDiagnostics/.../openpaws/

Apr 18-19 → v3 "codemaid" (CURRENT)
            Full modular: cli/, tools/, sessions/, profiles/
            Location: Projects/CodeMAID/codemaid/
```

---

## Safe to Delete Right Now

No unique content, confirmed duplicates:

```bash
# 1. Dead flat copy inside active project (identical to backup-live-pre-v2)
rm -rf ~/Projects/CodeMAID/resources/

# 2. Same flat copy on Data drive
rm -rf /mnt/Data/Projects/apps/CodeMAID/resources/

# 3. v1 backup inside old git repo (identical to above)
rm -rf ~/Projects/LinuxSystemDiagnostics/THE-TODO/CodeMAID/CodeM.A.I.D/backup-live-pre-v2/

# 4. Openpaws backup junk files (46-byte hello.py files from testing)
rm -rf ~/.config/openpaws/backups/

# 5. Empty the trash
rm -rf ~/.local/share/Trash/files/"openpaws (1)"
```

---

## Needs a Decision Before Deleting

### * LinuxSystemDiagnostics old git repo
**Path:** `~/Projects/LinuxSystemDiagnostics/THE-TODO/CodeMAID/CodeM.A.I.D/`

Contains two Claude Code session transcripts from the OpenPaws dev era:
- `notgoingtohell.txt` (758 lines) — old Claude Code session debugging the streaming/line rendering bug
- `shadypestofiles-nolikedaylight.txt` (168 lines) — another session log
- `.aider.chat.history.md` (55KB) — aider session history

**If you want the "Ai Story" logs:** Move the `.txt` files to `~/Projects/Writing/The Ai Story/` first, then delete the whole `CodeM.A.I.D/` directory.
**If you don't need them:** Delete the whole thing.

```bash
# Option A — save the logs first
mv ~/Projects/LinuxSystemDiagnostics/THE-TODO/CodeMAID/CodeM.A.I.D/notgoingtohell.txt \
   ~/Projects/Writing/The\ Ai\ Story/
mv ~/Projects/LinuxSystemDiagnostics/THE-TODO/CodeMAID/CodeM.A.I.D/shadypestofiles-nolikedaylight.txt \
   ~/Projects/Writing/The\ Ai\ Story/
rm -rf ~/Projects/LinuxSystemDiagnostics/THE-TODO/CodeMAID/

# Option B — nuke it
rm -rf ~/Projects/LinuxSystemDiagnostics/THE-TODO/CodeMAID/
```

---

### ** Data drive CodeMAID BACKUP
**Path:** `/mnt/Data/Projects/apps/CodeMAID/BACKUP/codemaid/`

This is a v3 backup (has vault.py, modular structure). If git is your backup strategy for CodeMAID, this is redundant. If you don't have a remote git for CodeMAID yet, keep it until you do.

```bash
# Once you have a git remote pushed:
rm -rf /mnt/Data/Projects/apps/CodeMAID/BACKUP/
```

---

### ~/.config/openpaws/ audit.log
110KB audit log from the openpaws era. Useful only if you want to grep old command history. Otherwise:

```bash
rm -rf ~/.config/openpaws/
```

---

## Also: Two `agents` Directories

| Path | What it is | Action |
|------|-----------|--------|
| `~/.agents/` | Active runtime (db, skills, tools, instructions) | Keep — this IS the system |
| `~/agents/` | `AgentSessionLogger` Python module in development | Keep — new code, not a duplicate |

These need to be consolidated eventually. The `~/agents/sessions/logger.py` is a more complete session logger than what CodeMAID currently uses — it supports JSONL journaling, HTML reports, and multi-agent isolation. Worth integrating into CodeMAID rather than having two parallel session systems.

---

## Empty Folders

Run this after cleanup to find any leftover empty directories:

```bash
find ~/Projects /mnt/Data/Projects -type d -empty 2>/dev/null | grep -v ".git" | sort
```
