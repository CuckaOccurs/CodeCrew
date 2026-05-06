# CodeMOP — Onboarder
# First run wizard. Walks through nine steps.
# Generates personas via Ollama — they name themselves.
# Writes all config files. Installs cron.
# Never runs again unless reset.

from pathlib import Path
import json
import re
import yaml
import requests
import logging
import shutil
from datetime import datetime
from codemop import (
    APP_ROOT,
    AGENTS_ROOT,
    PERSONAS_DIR,
    PROFILES_DIR,
    PROJECTS_DIR,
    SESSIONS_DIR,
    ARCHIVE_DIR,
    DB_PATH,
    CONFIG_PATH,
    load_config,
    bootstrap,
)
from codemop.api import OllamaAPI
from codemop.cleaner import Cleaner

log = logging.getLogger("codemop.onboarder")

# ── Persona seeds ─────────────────────────────────────
PERSONA_SEEDS = {
    "coder": {
        "name": "Kai",
        "tags": ["coding", "architecture",
                 "debugging", "review"],
        "style": "collaborative",
        "seed": (
            "You are a senior software developer "
            "with deep experience in clean, "
            "readable, cross-platform code. "
            "You think before you type. "
            "You explain your reasoning. "
            "You treat the human as a capable "
            "partner, not a student."
        )
    },
    "debugger": {
        "name": "Trace",
        "tags": ["debugging", "testing",
                 "tracing", "logging"],
        "style": "methodical",
        "seed": (
            "You are a methodical debugger. "
            "You never guess. You trace, log, "
            "and verify. You isolate before "
            "fixing. You read the entire error "
            "message every single time."
        )
    },
    "writer": {
        "name": "Wren",
        "tags": ["writing", "editing",
                 "documentation", "clarity"],
        "style": "precise",
        "seed": (
            "You are a precise and clear writer. "
            "You believe every word should earn "
            "its place. You write for the reader, "
            "not the writer. You edit ruthlessly "
            "and explain naturally."
        )
    },
    "brainstormer": {
        "name": "Sparks",
        "tags": ["ideation", "architecture",
                 "planning", "theory"],
        "style": "expansive",
        "seed": (
            "You are a creative systems thinker. "
            "You explore before committing. "
            "You throw ten ideas at the wall "
            "knowing two will stick. You know "
            "when to stop thinking and start "
            "building."
        )
    },
    "researcher": {
        "name": "Archer",
        "tags": ["research", "analysis",
                 "synthesis", "fact-checking"],
        "style": "thorough",
        "seed": (
            "You are a thorough researcher. "
            "You verify before asserting. "
            "You distinguish between what is "
            "known, what is likely, and what "
            "is speculation."
        )
    },
    "counselor": {
        "name": "Sage",
        "tags": ["support", "listening",
                 "guidance", "empathy"],
        "style": "warm",
        "seed": (
            "You are a warm and grounded counselor. "
            "You listen before advising. "
            "You ask one question at a time. "
            "You hold space without judgment."
        )
    },
    "chef": {
        "name": "Jules",
        "tags": ["cooking", "baking",
                 "nutrition", "technique"],
        "style": "passionate",
        "seed": (
            "You are a red seal chef with deep "
            "respect for ingredients, technique, "
            "and the people you feed. You explain "
            "the why behind every method. "
            "You make cooking feel possible."
        )
    }
}

NAME_PROMPT = """You are {name}. Introduce yourself in 2-3 sentences based on this persona.
Be direct. Be real. No corporate speak. No fluff.
Start with "I'm {name}."

Persona:
{seed}

Respond ONLY with your introduction."""

PERSONA_PROMPT = """You are writing a persona
instruction file for an AI assistant.

Given this seed description, write a full,
detailed instruction set in first person.
Include how you think, how you communicate,
what you prioritise, what you refuse to do,
how you handle uncertainty, and how you hand
off to other personas when needed.

Seed:
{seed}

Your name is: {name}

Write the full instruction text only.
No YAML. No headers. Just the instruction prose.
3-5 paragraphs."""


class Onboarder:
    def __init__(self):
        self._validate_environment()
        self._check_gpu()
        self.api = OllamaAPI()

    def _validate_environment(self):
        required_vars = ["AGENTS_ROOT", "CODEMOP_HOME"]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")
        log.info("Environment validation successful.")

        self.state = {
            "user_name": "",
            "root_dir": str(
                Path.home() / "Projects"),
            "max_ascent": -1,
            "selected_personas": [],
            "generated_personas": {},
            "profile_name": "",
            "preferred_model": "",
            "fallback_model": "",
            "connectors": [],
            "active_retention": 30,
            "archive_retention": 90,
            "imports": []
        }

    # ── Main flow ─────────────────────────────────────
    def run(self) -> bool:
        log.info("Starting onboarder")

        steps = [
            self._step_welcome,
            self._step_ollama,
            self._step_workspace,
            self._step_personas,
            self._step_profile,
            self._step_connectors,
            self._step_sessions,
            self._step_imports,
            self._step_finalize,
        ]

        for step in steps:
            try:
                step()
            except KeyboardInterrupt:
                log.info("Onboarding cancelled")
                return False
            except Exception as e:
                log.warning(
                    f"Step error in "
                    f"{step.__name__}: {e} "
                    f"— continuing")

        self._mark_complete()
        log.info("Onboarding complete")
        return True

    # ── Steps ─────────────────────────────────────────
    def _step_welcome(self):
        self._print_header("Welcome to CodeMOP")
        print(
            "CodeMOP is your AI infrastructure.\n"
            "It manages personas, profiles, and\n"
            "session memory for your local AI.\n")

        name = self._prompt(
            "What's your name?", default="")
        self.state["user_name"] = name
        print(f"\nGreat to meet you, {name}.\n")

    def _step_ollama(self):
        self._print_header("Finding Ollama")

        running = self.api.health_check()

        if not running:
            print(
                "⚠  Ollama doesn't appear to be "
                "running.\n"
                "   Start it with: ollama serve\n"
                "   Continuing with defaults.\n")
            self.state["preferred_model"] = \
                "qwen2.5:14b"
            self.state["fallback_model"] = \
                "qwen2.5:7b"
            return

        print("✓  Ollama is running\n")

        models = self.api.available_models()
        if not models:
            print(
                "   No models pulled yet.\n"
                "   Try: ollama pull qwen2.5:14b\n")
            self.state["preferred_model"] = \
                "qwen2.5:14b"
            self.state["fallback_model"] = \
                "qwen2.5:7b"
            return

        print("Available models:")
        for i, m in enumerate(models):
            size_gb = round(
                m.get("size", 0) / 1e9, 1)
            print(
                f"  {i+1}. {m['name']} "
                f"({size_gb}GB)")

        print()
        preferred = self._prompt_choice(
            "Preferred model (number)?",
            [m["name"] for m in models],
            default=0)
        self.state["preferred_model"] = preferred

        fallback = self._prompt_choice(
            "Fallback model (number)?",
            [m["name"] for m in models],
            default=min(1, len(models)-1))
        self.state["fallback_model"] = fallback

        print(
            f"\n✓  Primary: {preferred}\n"
            f"✓  Fallback: {fallback}\n")

    def _step_workspace(self):
        self._print_header("Your Workspace")

        print(
            "Where do your projects live?\n")

        root = self._prompt(
            "Projects root directory?",
            default=self.state["root_dir"])

        root_path = Path(root).expanduser()
        if not root_path.exists():
            create = self._prompt_yn(
                f"  {root} doesn't exist. "
                f"Create it?",
                default=True)
            if create:
                root_path.mkdir(
                    parents=True, exist_ok=True)
                print(f"  ✓  Created {root}\n")

        self.state["root_dir"] = str(root_path)

        print(
            "\nHow far up should CodeMOP look?\n"
            "  1. 2 levels up\n"
            "  2. 3 levels up\n"
            "  3. 5 levels up\n"
            "  4. Unlimited\n")

        depth_map = {
            "1": 2, "2": 3,
            "3": 5, "4": -1}
        choice = self._prompt(
            "Choice [1-4]?", default="4")
        self.state["max_ascent"] = \
            depth_map.get(choice, -1)

        print(
            f"\n✓  Root: {root}\n"
            f"✓  Depth: "
            f"{'Unlimited' if self.state['max_ascent'] == -1 else self.state['max_ascent']}"
            f"\n")

    def _step_personas(self):
        self._print_header("Your AI Team")

        print(
            "Select the kinds of work you do.\n"
            "Each persona will introduce itself.\n")

        options = list(PERSONA_SEEDS.keys())
        for i, name in enumerate(options):
            print(
                f"  {i+1}. {name.capitalize()}")

        print()
        raw = self._prompt(
            "Select personas (e.g. 1,2,3)?",
            default="1,2,4")

        selected = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(options):
                    selected.append(options[idx])

        if not selected:
            selected = [
                "coder", "debugger",
                "brainstormer"]

        self.state["selected_personas"] = selected

        print(
            f"\nGenerating your team of "
            f"{len(selected)}...\n")

        print(f"  Warming up {self.state['preferred_model']}...")
        try:
            requests.post(
                f"{self.api.base_url}/api/generate",
                json={
                    "model": self.state["preferred_model"],
                    "prompt": "hi",
                    "stream": False,
                    "keep_alive": -1
                },
                timeout=300)
        except Exception:
            pass

        used_names = set()
        for persona_key in selected:
            seed = PERSONA_SEEDS[persona_key]
            print(
                f"  Creating your "
                f"{persona_key}...",
                end=" ", flush=True)

            default_name = seed.get("name", persona_key.capitalize())
            chosen_name = self._prompt(
                f"  Name for your {persona_key}?",
                default=default_name)
            seed = dict(seed)
            seed["name"] = chosen_name
            persona = self._generate_persona(
                persona_key, seed, used_names)
            self.state[
                "generated_personas"]\
                [persona_key] = persona

            name = persona.get(
                "persona_name", "Unknown")
            print(f"meet {name}")
            intro = persona.get(
                "introduction", "")
            print(f"\n  \"{intro[:120]}...\"\n")

        keep = self._prompt_yn(
            "Keep this team?", default=True)
        if not keep:
            self.state["generated_personas"] = {}
            self._step_personas()

    def _step_profile(self):
        self._print_header(
            "Your Default Profile")

        name = self._prompt(
            "Name your default profile?",
            default="default")
        self.state["profile_name"] = name

        print(
            f"\n✓  Profile '{name}' will use:\n")
        for p in self.state["selected_personas"]:
            persona = self.state[
                "generated_personas"].get(p, {})
            pname = persona.get(
                "persona_name", p)
            print(f"   · {pname} ({p})")
        print()

    def _step_connectors(self):
        self._print_header("Connect Your Tools")

        connectors = []

        owui = self._detect_openwebui()
        if owui:
            print(
                f"✓  OpenWebUI detected: {owui}")
            connectors.append({
                "name": "openwebui",
                "url": owui,
                "enabled": True
            })
        else:
            url = self._prompt(
                "OpenWebUI URL (enter to skip)?",
                default="")
            if url:
                connectors.append({
                    "name": "openwebui",
                    "url": url,
                    "enabled": True
                })

        picoder = self._detect_picoder()
        if picoder:
            print(
                f"✓  Pi-Coder detected: {picoder}")
            connectors.append({
                "name": "picoder",
                "url": picoder,
                "enabled": True
            })
        else:
            url = self._prompt(
                "Pi-Coder URL (enter to skip)?",
                default="")
            if url:
                connectors.append({
                    "name": "picoder",
                    "url": url,
                    "enabled": True
                })

        self.state["connectors"] = connectors
        print()

    def _step_sessions(self):
        self._print_header("Session Memory")

        print(
            "How long should sessions be kept?\n")

        active = self._prompt(
            "Active sessions (days)?",
            default="30")
        archive = self._prompt(
            "Archived sessions (days)?",
            default="90")

        try:
            self.state["active_retention"] = \
                int(active)
            self.state["archive_retention"] = \
                int(archive)
        except ValueError:
            self.state["active_retention"] = 30
            self.state["archive_retention"] = 90

        print(
            f"\n✓  Active: "
            f"{self.state['active_retention']} "
            f"days\n"
            f"✓  Archive: "
            f"{self.state['archive_retention']} "
            f"days\n")

    def _step_imports(self):
        self._print_header(
            "Import Existing Sessions")

        known = {
            "goose": Path.home() / ".goose",
            "aider": Path.home() / ".aider",
            "claude": Path.home() / ".claude",
        }

        found = {
            tool: path
            for tool, path in known.items()
            if path.exists()
        }

        if not found:
            print(
                "No existing agent folders "
                "found. Starting fresh.\n")
            return

        print("Found existing agent data:\n")
        for tool, path in found.items():
            print(f"  · {tool} at {path}")

        print()
        do_import = self._prompt_yn(
            "Import existing sessions?",
            default=True)

        if not do_import:
            return

        imports = []
        for tool, path in found.items():
            choice = self._prompt_yn(
                f"  Import from {tool}?",
                default=True)
            if choice:
                imports.append({
                    "tool": tool,
                    "path": str(path)
                })

        self.state["imports"] = imports
        print()

    def _step_finalize(self):
        self._print_header("Setting Up CodeMOP")

        print("Writing configuration...", end=" ")
        self._write_config()
        print("✓")

        print("Writing persona files...", end=" ")
        self._write_personas()
        print("✓")

        print("Writing profile...", end=" ")
        self._write_profile()
        print("✓")

        print("Installing cron job...", end=" ")
        cleaner = Cleaner()
        ok = cleaner.install_cron()
        print("✓" if ok else "⚠ skipped")

        if self.state["imports"]:
            print(
                "Importing sessions...",
                end=" ")
            self._import_sessions()
            print("✓")

        pname = self.state["profile_name"]
        model = self.state["preferred_model"]
        root = Path(
            self.state["root_dir"]).name

        print(
            f"\n┌─────────────────────────────┐\n"
            f"│  CodeMOP is ready.          │\n"
            f"│                             │\n"
            f"│  Profile: {pname:<18}│\n"
            f"│  Model:   {model[:18]:<18}│\n"
            f"│  Root:    {root:<18}│\n"
            f"│                             │\n"
            f"│  Run CodeMaid to manage     │\n"
            f"│  your setup anytime.        │\n"
            f"└─────────────────────────────┘\n")

    # ── Persona generation ────────────────────────────
    def _generate_persona(self,
                          persona_key: str,
                          seed: dict,
                          used_names: set = None) -> dict:
        seed_text = seed["seed"]

        name, introduction = \
            self._generate_introduction(seed_text, seed.get("name", "Assistant"), used_names)

        instruction = \
            self._generate_instruction(
                seed_text, name)

        return {
            "persona_key": persona_key,
            "persona_name": name,
            "introduction": introduction,
            "instruction": instruction,
            "tags": seed.get("tags", []),
            "style": seed.get("style", ""),
            "seed": seed_text
        }

    def _strip_thinking(self, text: str) -> str:
        return re.sub(
            r"<think>.*?</think>",
            "",
            text,
            flags=re.DOTALL
        ).strip()

    def _generate_introduction(self,
                                seed: str,
                                persona_name: str = "Assistant",
                                used_names: set = None
                                ) -> tuple:
        if used_names is None:
            used_names = set()

        if not self.api.health_check():
            return (persona_name, seed[:100])

        model = self.state.get("preferred_model", "")
        if not model:
            models = self.api.available_models()
            if models:
                model = models[0]["name"]
            else:
                return (persona_name, seed[:100])

        prompt = NAME_PROMPT.format(
            name=persona_name, seed=seed)

        try:
            r = requests.post(
                f"{self.api.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=120)

            raw = r.json().get("response", "").strip()
            text = self._strip_thinking(raw)
            if not text:
                return (persona_name, seed[:100])

            used_names.add(persona_name)
            return (persona_name, text)

        except Exception as e:
            log.warning(f"Introduction failed: {e}")
            return (persona_name, seed[:100])

    def _generate_instruction(self,
                               seed: str,
                               name: str) -> str:
        if not self.api.health_check():
            return seed

        model = self.state.get(
            "preferred_model", "")
        if not model:
            return seed

        prompt = PERSONA_PROMPT.format(
            seed=seed, name=name)

        try:
            r = requests.post(
                f"{self.api.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=300)

            return r.json().get(
                "response", seed).strip()

        except Exception as e:
            log.warning(
                f"Instruction failed: {e}")
            return seed

    # ── File writing ──────────────────────────────────
    def _write_config(self):
        config = {
            "user": {
                "name": self.state["user_name"],
                "onboarding_complete": False
            },
            "ollama": {
                "url": "http://localhost:11434",
                "default_model": self.state[
                    "preferred_model"],
                "fallback_model": self.state[
                    "fallback_model"],
                "gpu_layers": -1,
                "main_gpu": 0,
                "timeout": 120,
                "stream": True
            },
            "walker": {
                "root": self.state["root_dir"],
                "max_ascent": self.state[
                    "max_ascent"],
                "max_depth": -1,
                "exclude": [
                    ".git", "node_modules",
                    "__pycache__",
                    "venv", ".venv"
                ]
            },
            "cleaner": {
                "active_retention_days":
                    self.state["active_retention"],
                "archive_retention_days":
                    self.state["archive_retention"],
                "compress": True,
                "run_schedule": "0 2 * * 0"
            },
            "sessions": {
                "base_dir": str(SESSIONS_DIR),
                "archive_dir": str(ARCHIVE_DIR)
            },
            "db": {
                "path": str(DB_PATH),
                "vacuum_schedule": "monthly"
            },
            "connectors": self.state["connectors"],
            "codemaid": {
                "host": "0.0.0.0",
                "port": 8080,
                "dark_mode": True
            }
        }

        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(
                config, f,
                default_flow_style=False,
                sort_keys=False)

    def _write_personas(self):
        PERSONAS_DIR.mkdir(
            parents=True, exist_ok=True)

        for key, persona in self.state[
                "generated_personas"].items():
            filepath = PERSONAS_DIR / f"{key}.md"

            fm = {
                "name": key,
                "persona_name": persona[
                    "persona_name"],
                "version": "1.0",
                "author": self.state["user_name"],
                "tags": persona.get("tags", []),
                "style": persona.get("style", ""),
                "models": [
                    self.state["preferred_model"]
                ],
                "fallback_models": [
                    self.state["fallback_model"]
                ],
                "min_context": 4096,
                "generated_at": (
                    datetime.now().isoformat()),
                "introduction": persona[
                    "introduction"]
            }

            content = "---\n"
            content += yaml.dump(
                fm,
                default_flow_style=False,
                sort_keys=False)
            content += "---\n\n"
            content += persona["instruction"]

            with open(filepath, 'w') as f:
                f.write(content)

            log.debug(
                f"Wrote persona: {filepath.name}")

    def _write_profile(self):
        PROFILES_DIR.mkdir(
            parents=True, exist_ok=True)

        name = self.state["profile_name"]
        filepath = PROFILES_DIR / f"{name}.yaml"

        profile = {
            "name": name,
            "version": "1.0",
            "description": (
                f"Default profile for "
                f"{self.state['user_name']}"),
            "personas": self.state[
                "selected_personas"],
            "preferred_model": self.state[
                "preferred_model"],
            "fallback_model": self.state[
                "fallback_model"],
            "min_context": 4096,
            "tools": [
                c["name"]
                for c in self.state["connectors"]
                if c.get("enabled")
            ],
            "created_at": (
                datetime.now().isoformat())
        }

        with open(filepath, 'w') as f:
            yaml.dump(
                profile, f,
                default_flow_style=False,
                sort_keys=False)

    def _import_sessions(self):
        from codemop.indexer import Indexer
        indexer = Indexer()

        for imp in self.state["imports"]:
            tool = imp["tool"]
            path = Path(imp["path"])
            dest = (SESSIONS_DIR /
                    f"imported_{tool}")
            dest.mkdir(
                parents=True, exist_ok=True)

            copied = 0
            for f in path.rglob("*"):
                if (f.is_file() and
                        f.suffix in (
                            ".html", ".md",
                            ".txt", ".jsonl")):
                    try:
                        shutil.copy2(
                            f, dest / f.name)
                        copied += 1
                    except Exception:
                        pass

            log.info(
                f"Imported {copied} files "
                f"from {tool}")
            indexer.process_directory(dest)

    # ── Detection ─────────────────────────────────────
    def _detect_openwebui(self) -> str:
        for url in [
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
        ]:
            try:
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    return url
            except Exception:
                pass
        return ""

    def _detect_picoder(self) -> str:
        for url in [
            "http://localhost:8501",
            "http://localhost:7860",
            "http://127.0.0.1:8501",
        ]:
            try:
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    return url
            except Exception:
                pass
        return ""

    # ── Completion ────────────────────────────────────
    def _mark_complete(self):
        try:
            config = load_config()
            config["user"][
                "onboarding_complete"] = True
            with open(CONFIG_PATH, 'w') as f:
                yaml.dump(
                    config, f,
                    default_flow_style=False,
                    sort_keys=False)
        except Exception as e:
            log.warning(
                f"Could not mark complete: {e}")

    def is_complete(self) -> bool:
        config = load_config()
        return config.get("user", {}).get(
            "onboarding_complete", False)

    def reset(self):
        config = load_config()
        config["user"][
            "onboarding_complete"] = False
        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(
                config, f,
                default_flow_style=False,
                sort_keys=False)
        log.info("Onboarding reset")

    # ── UI helpers ────────────────────────────────────
    def _print_header(self, title: str):
        width = 40
        print(f"\n{'─' * width}")
        print(f"  {title}")
        print(f"{'─' * width}\n")

    def _prompt(self,
                question: str,
                default: str = "") -> str:
        hint = (f" [{default}]"
                if default else "")
        try:
            answer = input(
                f"{question}{hint}: ").strip()
            return answer if answer else default
        except (EOFError, KeyboardInterrupt):
            return default

    def _prompt_yn(self,
                   question: str,
                   default: bool = True) -> bool:
        hint = "Y/n" if default else "y/N"
        try:
            answer = input(
                f"{question} [{hint}]: "
            ).strip().lower()
            if not answer:
                return default
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return default

    def _prompt_choice(self,
                       question: str,
                       choices: list,
                       default: int = 0) -> str:
        try:
            answer = input(
                f"{question} [{default+1}]: "
            ).strip()
            if not answer:
                return choices[default]
            idx = int(answer) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
            return choices[default]
        except (ValueError, IndexError,
                EOFError, KeyboardInterrupt):
            return choices[default]


# ── CLI entry point ───────────────────────────────────
def main():
    import sys
    onboarder = Onboarder()

    if "--reset" in sys.argv:
        onboarder.reset()
        print(
            "Onboarding reset. "
            "Run codemop-setup to start again.")
    elif onboarder.is_complete():
        print(
            "Onboarding already complete.\n"
            "Run with --reset to start over.")
    else:
        onboarder.run()


if __name__ == "__main__":
    main()

    def _check_gpu(self):
        """Pre-flight check for NVIDIA CUDA drivers."""
        import shutil
        if shutil.which("nvidia-smi"):
            log.info("NVIDIA drivers detected. CUDA ready.")
            return True
        elif shutil.which("rocm-smi"):
            log.info("AMD ROCm drivers detected. ROCm ready.")
            return True
        else:
            log.warning("No GPU drivers detected. CPU-only mode will be slow.")
            return False
