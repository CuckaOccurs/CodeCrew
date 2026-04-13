"""
OpenPaws Skills Loader — Injects skills into the System Prompt.
"""
import os
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

SKILLS_DIR = Path.home() / ".agents" / "skills"

def _extract_frontmatter(content):
    """Extract YAML frontmatter using regex fallback if yaml is not available."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 2:
        return {}
    yaml_block = parts[1].strip()
    if HAS_YAML:
        try:
            return yaml.safe_load(yaml_block) or {}
        except Exception:
            pass
    # Regex fallback
    import re
    match = re.search(r'description:\s*\n?\s*\|?\s*(.*?)(?=\n[a-z-]+:|\n---|\Z)', yaml_block, re.DOTALL)
    if match:
        return {"description": match.group(1).strip()}
    return {}

def load_skills():
    """Scan the skills directory and return a list of skill descriptions."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if skill_dir.is_dir():
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    meta = _extract_frontmatter(content)
                    desc = meta.get("description", "No description available.")
                    skills.append(f"- **{skill_dir.name}**: {desc}")
                except (OSError, UnicodeDecodeError):
                    pass
    return skills

def build_system_prompt():
    """Build a dynamic system prompt including loaded skills."""
    skills = load_skills()
    skills_text = "\n".join(skills)
    
    prompt = """You are OpenPaws, an expert AI coding assistant and investigative journalist's partner.

Your goal is to help the user with coding tasks: reading, writing, editing files, running commands, and investigating topics.

You have access to the following tools:
1. read_file: Read a file's contents. ALWAYS use this before editing.
2. write_file: Create or overwrite a file with full content.
3. edit_file: Apply a specific SEARCH/REPLACE block to a file.
4. focus: Deep-search the entire codebase for a pattern.
5. grep: Search for a pattern in files (Ctrl+F for the codebase).
6. web_search: Search the web for current information.
7. web_scrape: Fetch and read the text content of a URL.
8. read_document: Read the contents of a PDF, Word, or Excel file.
9. diff_preview: Show a diff of the last edit made to a file.
10. undo_edit: Restore a file from its last backup.
11. read_multiple: Read multiple files in one call.
12. list_dir: List files and directories with types and sizes.
13. run_command: Run a shell command (e.g., python test.py).
14. list_skills: List all the special skills/modules currently loaded.

Guidelines:
- Be concise.
- Always read a file before editing it.
- Use edit_file for small fixes. Use write_file for creating new files or major rewrites.
- If the user asks for an investigation, use your investigation skills.
- If the user asks for writing, use your writer skills.

Currently Loaded Skills:
"""
    if skills_text:
        prompt += skills_text
    else:
        prompt += "- None (Only base coding tools are available)."
        
    return prompt
