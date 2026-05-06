# CodeMOP — Manager Of Personas
# ~/.agents/app/codemop/__init__.py

from pathlib import Path
import logging
import yaml

import os

# ── Root paths ────────────────────────────────────────
# Allow overriding via env var for cross-machine or symlinked setups
AGENTS_ROOT   = Path(os.getenv("AGENTS_ROOT", Path.home() / ".agents"))
APP_ROOT      = AGENTS_ROOT / "app"

# ── CodeMOP owned directories ─────────────────────────
PERSONAS_DIR  = APP_ROOT / "personas"
PROFILES_DIR  = APP_ROOT / "profiles"
PROJECTS_DIR  = APP_ROOT / "projects"
SESSIONS_DIR  = APP_ROOT / "sessions"
ARCHIVE_DIR   = APP_ROOT / "archive"
DB_DIR        = APP_ROOT / "db"
DB_PATH       = DB_DIR / "codemop.db"
CONFIG_PATH   = APP_ROOT / "config.yaml"

# ── Existing agent directories (read only) ────────────
TOOLS_DIR     = AGENTS_ROOT / "tools"
SKILLS_DIR    = AGENTS_ROOT / "skills"

# ── Default config ────────────────────────────────────
DEFAULT_CONFIG = {
    "user": {
        "name": "",
        "onboarding_complete": False
    },
    "ollama": {
        "url": "http://localhost:11434",
        "default_model": "llama3",
        "fallback_model": "llama3:7b",
        "gpu_layers": -1,
        "main_gpu": 0,
        "timeout": 120,
        "stream": True
    },
    "walker": {
        "root": str(Path.home() / "Projects"),
        "max_ascent": -1,
        "max_depth": -1,
        "exclude": [
            ".git",
            "node_modules",
            "__pycache__",
            "venv",
            ".venv"
        ]
    },
    "cleaner": {
        "active_retention_days": 30,
        "archive_retention_days": 90,
        "compress": True,
        "run_schedule": "0 2 * * 0"
    },
    "sessions": {
        "base_dir": str(APP_ROOT / "sessions"),
        "archive_dir": str(APP_ROOT / "archive")
    },
    "db": {
        "path": str(APP_ROOT / "db" / "codemop.db"),
        "vacuum_schedule": "monthly"
    },
    "connectors": [],
    "codemaid": {
        "host": "0.0.0.0",
        "port": 8080,
        "engine_url": "http://localhost:8080",
        "dark_mode": True
    }
}

# ── Logging ───────────────────────────────────────────
APP_ROOT.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(APP_ROOT / "codemop.log"),
        logging.StreamHandler()
    ]
)

log = logging.getLogger("codemop")

# ── Filesystem setup ──────────────────────────────────
def init_filesystem():
    """
    Create ~/.agents/app/ folder structure
    on first run. Safe to call every run —
    existing folders are never touched.
    """
    dirs = [
        APP_ROOT,
        PERSONAS_DIR,
        PROFILES_DIR,
        PROJECTS_DIR,
        SESSIONS_DIR,
        ARCHIVE_DIR,
        DB_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        log.debug(f"Ensured directory: {d}")

def init_config():
    """
    Write default config.yaml if it
    doesn't exist. Never overwrites.
    """
    if not CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(
                DEFAULT_CONFIG, f,
                default_flow_style=False,
                sort_keys=False)
        log.info(f"Created default config: {CONFIG_PATH}")

def load_config() -> dict:
    """
    Load config.yaml.
    Falls back to defaults if missing
    or malformed.
    """
    try:
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        log.warning(
            f"Could not load config: {e} "
            f"— using defaults")
        return DEFAULT_CONFIG

def bootstrap():
    """
    Full first run setup.
    Call once at any entry point.
    """
    init_filesystem()
    init_config()
    log.info("CodeMOP initialized")

# ── Auto bootstrap on import ──────────────────────────
bootstrap()
