"""
CODEMAID Skills Loader — Injects skills, instructions, rules, and dict into the System Prompt.
"""
import os
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

AGENTS_DIR  = Path.home() / ".agents"
SKILLS_DIR  = AGENTS_DIR / "skills"
RULES_DIR   = AGENTS_DIR / "rules"
DICT_DIR    = AGENTS_DIR / "dict"

def _extract_frontmatter(content):
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
    import re
    match = re.search(r'description:\s*\n?\s*\|?\s*(.*?)(?=\n[a-z-]+:|\n---|\Z)', yaml_block, re.DOTALL)
    if match:
        return {"description": match.group(1).strip()}
    return {}

def load_skills():
    """Scan ~/.agents/skills/ recursively and return skill descriptions."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    for skill_file in sorted(SKILLS_DIR.rglob("SKILL.md")):
        try:
            content = skill_file.read_text(encoding="utf-8")
            meta = _extract_frontmatter(content)
            desc = meta.get("description", "No description available.")
            skills.append(f"- **{skill_file.parent.name}**: {desc}")
        except (OSError, UnicodeDecodeError):
            pass
    return skills

def load_instructions() -> str:
    """Load ~/.agents/instructions.md (user bio and working style)."""
    f = AGENTS_DIR / "instructions.md"
    if f.exists():
        try:
            return f.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            pass
    return ""

def load_rules() -> str:
    """Load all rule files from ~/.agents/rules/."""
    if not RULES_DIR.exists():
        return ""
    rules = []
    for f in sorted(RULES_DIR.glob("*.md")):
        try:
            rules.append(f.read_text(encoding="utf-8").strip())
        except (OSError, UnicodeDecodeError):
            pass
    return "\n\n".join(rules)

def load_dict(name: str = "pestdict") -> dict:
    """Load a substitution dictionary from ~/.agents/dict/<name>.yaml."""
    if not HAS_YAML:
        return {}
    f = DICT_DIR / f"{name}.yaml"
    if not f.exists():
        return {}
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        flat = {}
        for section in data.values():
            if isinstance(section, dict):
                flat.update(section)
        return flat
    except Exception:
        return {}

def get_load_status(load_cfg: dict | None = None) -> dict:
    """Return what's currently available to load — used by the header bar."""
    lc = load_cfg or {}
    instructions_file = AGENTS_DIR / "instructions.md"
    rules_files       = list(RULES_DIR.glob("*.md")) if RULES_DIR.exists() else []
    dict_files        = [DICT_DIR / f"{d}.yaml" for d in lc.get("dicts", ["pestdict"])]
    skill_dirs        = list(SKILLS_DIR.rglob("SKILL.md")) if SKILLS_DIR.exists() else []
    return {
        "instructions": lc.get("instructions", True) and instructions_file.exists(),
        "rules":        lc.get("rules", True) and len(rules_files) > 0,
        "skills":       lc.get("skills", True) and len(skill_dirs) > 0,
        "dicts":        [d.stem for d in dict_files if d.exists()],
        "skill_count":  len(skill_dirs),
        "rule_count":   len(rules_files),
    }

def build_system_prompt(profile_name: str = "default", load_cfg: dict | None = None) -> str:
    """Build system prompt: instructions + persona + rules + backbone + skills."""
    lc = load_cfg or {}

    # 1. User context
    instructions = load_instructions() if lc.get("instructions", True) else ""

    # 2. Persona
    profiles_dir = Path(__file__).parent / "profiles"
    personality_file = profiles_dir / f"{profile_name}.md"
    if not personality_file.exists():
        personality_file = profiles_dir / "default.md"
    persona = ""
    if personality_file.exists():
        try:
            persona = personality_file.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            pass

    # 3. Rules
    rules = load_rules() if lc.get("rules", True) else ""

    # 4. Active dicts summary
    dict_note = ""
    active_dicts = lc.get("dicts", [])
    if active_dicts:
        dict_note = "## Active Substitution Dicts\n" + "\n".join(f"- {d}" for d in active_dicts)

    # 5. Backbone
    backbone = (
        "## Operating Instructions (The APP Backbone)\n"
        "You are the execution body of CodeM.A.I.D.\n"
        "- **Sensing**: Always read_file before editing to ensure context.\n"
        "- **Acting**: Use edit_file for precision, write_file for creation.\n"
        "- **Integrity**: Follow the persona instructions provided above strictly.\n"
        "- **Safety**: If you encounter a blocked command, inform the user they can use 'Ctrl+S' to grant Sudo privileges.\n"
    )

    # 6. Skills
    skills = load_skills() if lc.get("skills", True) else []

    parts = []
    if instructions:
        parts.append("## Who You Are Working With\n" + instructions)
    if persona:
        parts.append(persona)
    if rules:
        parts.append("## Rules\n" + rules)
    if dict_note:
        parts.append(dict_note)
    parts.append(backbone)
    if skills:
        parts.append("## Loaded Skills\n" + "\n".join(skills))

    return "\n\n".join(parts)
