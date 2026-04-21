# 📋 TODO - CuckaOccurs Project Audit & Cleanup

*Last Updated: April 2024*

This list consolidates necessary updates, consistency fixes, and project-specific tasks identified during the audit.

---

## 🎯 HIGH PRIORITY - IMMEDIATE ACTIONS

**Complete by end of week:**
- [ ] **Consolidate `.agent/` and `.agents/`**: Decide on one hidden directory (prefer `~/.agents/`) and merge all CodeMAID/Personality files
- [ ] **CodeMAID Cleanup**: Remove any system-installed library files accidentally copied into project folders
- [ ] **Resume Standardization**: Create "Master Resume" in `~/.agents/identity/` and symlink to other locations
- [ ] **Empty Folder Cleanup**: Remove empty folders across home, data, and video drives

## 🔄 Directory & Organization Fixes
- **Consolidate `.agent/` and `.agents/`**: There is currently duplication and potential confusion between these two "hidden" directories. 
    - *Action*: Decide on one (likely `~/.agents/` as per the vision) and move all CodeMAID/Personality files there.
- **"The Ai Story" Content**: The directory `/home/cuckaoccurs/Projects/Writing/The Ai Story/` was identified as empty in some logs. 
    - *Action*: Import relevant session logs (e.g., `when-ai-hallucinates.md`, transcriptions) from `Writing/Counseling/` into this project.
- **Resume Standardization**: There are multiple versions of the resume (`resume.md`, `amrize-resume.odt`, etc.) across `Employment/` and `apps/Airmy/`.
    - *Action*: Create a "Master Resume" in `~/.agents/identity/` and symlink it to other locations.

## 🛠️ Project-Specific Repairs

### CodeMAID (High Priority)
- **Consolidation**: Complete the merge of "openpaws", "paws", and "codemaid" into a single, clean latest-version copy in `Projects/apps/CodeM.A.I.D/`.
- **System File Cleanup**: Identify and remove any system-installed library files that were accidentally copied into the project folders.

### MusicMe
- **Fix P0-1**: Implement auto-advance for track playback in `src-tauri/src/audio/mod.rs`.
- **Fix P0-2**: Resolve the seek bar issues (switch to symphonia or implement time-based estimation).
- **Fix P0-3**: Implement virtual scrolling in the track table to handle large libraries.

### NewsFeed
- **Cleanup Worker**: Remove duplicate logic in `app.py`'s `queue_cleanup_worker`.
- **UI Stubs**: Finalize the "Monitors" and "Connections" panels. Replace alert stubs (like `postToSubstack`) with actual API implementations.

## 📝 Document Updates
- **Update `personality_profile.md`**: Ensure it reflects recent breakthroughs or changes in the "CuckaOccurs" persona development.
- **Consolidate Session Logs**: Move relevant "Aha moments" from scattered `.txt` files in `apps/Airmy/conversations-db/` to a centralized "Research" or "Writing" folder.
