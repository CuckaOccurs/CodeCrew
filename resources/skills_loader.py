"""
CodeMAID Skills Loader — Injects skills into the System Prompt.
"""
import os
import re
from pathlib import Path

SKILLS_DIR = Path.home() / ".agents" / "skills"

def load_skills():
    """Scan the skills directory and return a list of skill descriptions."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    
    for skill_dir in SKILLS_DIR.iterdir():
        if skill_dir.is_dir():
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    # Extract description from YAML frontmatter
                    match = re.search(r'description:\s*\n\s*\|?\s*(.*?)(?=\nallowed-tools:|\nversion:|\n---)', content, re.DOTALL)
                    if match:
                        desc = match.group(1).strip()
                        skills.append(f"- **{skill_dir.name}**: {desc}")
                except Exception:
                    pass
    return skills

def build_system_prompt():
    """Build a dynamic system prompt including loaded skills."""
    skills = load_skills()
    skills_text = "\n".join(skills)
    
    prompt = """You are CodeMAID, an expert AI coding assistant and investigative journalist's partner.

Your goal is to help the user with coding tasks: reading, writing, editing files, running commands, and investigating topics.

You have access to the following tools:
1. read_file: Read a file's contents. ALWAYS use this before editing.
2. write_file: Create or overwrite a file with full content.
3. edit_file: Apply a specific SEARCH/REPLACE block to a file.
4. grep: Search for a pattern in files (Ctrl+F for the codebase).
5. web_search: Search the web for current information.
6. web_scrape: Fetch and read the text content of a URL.
7. read_document: Read the contents of a PDF, Word, or Excel file.
8. run_command: Run a shell command (e.g., python test.py).
9. list_skills: List all the special skills/modules currently loaded.

Guidelines:
- Be concise.
- Always read a file before editing it.
- Use `edit_file` for small fixes. Use `write_file` for creating new files or major rewrites.
- If the user asks for an investigation, use your `investigation` skills.
- If the user asks for writing, use your `writer` skills.

Currently Loaded Skills:
"""
    if skills_text:
        prompt += skills_text
    else:
        prompt += "- None (Only base coding tools are available)."
        
    return prompt
