# CodeMOP — Assembler
# Takes walker's ordered rtfm.md list and builds
# one unified context object. Root first,
# most specific last. Most specific always wins.
# Like CSS specificity.

from pathlib import Path
import frontmatter
import yaml
import logging
from datetime import datetime
from codemop import (
    APP_ROOT,
    PERSONAS_DIR,
    PROFILES_DIR,
    load_config,
)

log = logging.getLogger("codemop.assembler")


class Assembler:
    """
    Parses and merges rtfm.md files.
    Resolves personas and profiles.
    Builds one unified context object.
    """

    def __init__(self):
        self.config = load_config()
        self._persona_cache = {}
        self._profile_cache = {}

    # ── Main entry point ──────────────────────────────
    def assemble(self,
                 rtfm_files: list,
                 cwd: Path = None) -> dict:
        """
        Take ordered list from Walker.
        Parse, merge, resolve, return
        single unified context object.
        """
        if not rtfm_files:
            log.info("No rtfm files to assemble")
            return self._empty_context(cwd)

        log.info(
            f"Assembling {len(rtfm_files)} "
            f"rtfm files")

        # Parse each rtfm file
        parsed = []
        for filepath in rtfm_files:
            result = self._parse_rtfm(filepath)
            if result:
                parsed.append(result)
                log.debug(f"Parsed: {filepath}")

        if not parsed:
            log.warning(
                "No rtfm files could be parsed")
            return self._empty_context(cwd)

        # Merge root down — most specific wins
        merged = self._merge_rtfm_chain(parsed)

        # Resolve profile
        profile = self._resolve_profile(
            merged.get("profile"))

        # Resolve personas from profile or rtfm
        persona_names = (
            profile.get("personas", [])
            if profile
            else merged.get("personas", [])
        )
        personas = self._resolve_personas(
            persona_names)

        # Build instruction text
        instructions = self._build_instructions(
            personas, merged)

        # Resolve model — rtfm overrides profile
        ollama_cfg = self.config.get("ollama", {})
        model = (
            merged.get("model") or
            profile.get("preferred_model") or
            ollama_cfg.get(
                "default_model", "llama3")
        )
        fallback = (
            merged.get("fallback_model") or
            profile.get("fallback_model") or
            ollama_cfg.get(
                "fallback_model", "llama3:7b")
        )

        project_name = merged.get(
            "project",
            cwd.name if cwd else "unknown")

        context = {
            # Identity
            "profile": merged.get(
                "profile", "default"),
            "personas": persona_names,
            "persona_names": [
                p.get("persona_name", "Assistant")
                for p in personas
            ],
            # Model
            "model": model,
            "fallback_model": fallback,
            "min_context": merged.get(
                "min_context", 4096),
            # Project
            "project": project_name,
            "cwd": str(cwd or Path.cwd()),
            "status": merged.get(
                "status", "active"),
            "git": merged.get("git", False),
            # Tools
            "tools": merged.get("tools", []),
            # Instructions
            "instructions": instructions,
            # Session
            "session_dir": str(
                APP_ROOT / "sessions" /
                project_name),
            # Decisions injected by indexer
            "decisions": [],
            # Meta
            "assembled_at": (
                datetime.now().isoformat()),
            "rtfm_files": [
                str(f) for f in rtfm_files],
            "notes": merged.get("notes", ""),
        }

        log.info(
            f"Context assembled: "
            f"{context['project']} "
            f"— {context['model']}")

        return context

    # ── rtfm parsing ──────────────────────────────────
    def _parse_rtfm(self,
                    filepath: Path) -> dict:
        try:
            post = frontmatter.load(str(filepath))
            result = dict(post.metadata)
            result["_body"] = post.content
            result["_filepath"] = str(filepath)
            return result
        except Exception as e:
            log.warning(
                f"Could not parse "
                f"{filepath}: {e}")
            return {}

    def _merge_rtfm_chain(self,
                           parsed: list) -> dict:
        """
        Merge list of parsed rtfm dicts.
        Root first, most specific last.
        Lists accumulate. Scalars override.
        """
        merged = {}
        accumulated_body = []

        for rtfm in parsed:
            for key, value in rtfm.items():
                if key == "_body":
                    if value and value.strip():
                        accumulated_body.append(
                            value)
                    continue

                if key == "_filepath":
                    continue

                if key in (
                        "tools", "personas",
                        "addons", "exclude"):
                    existing = merged.get(key, [])
                    if isinstance(value, list):
                        merged[key] = list(
                            dict.fromkeys(
                                existing + value))
                    continue

                # Scalar — most specific wins
                merged[key] = value

        merged["_body"] = "\n\n".join(
            accumulated_body)

        if "inherits" in merged:
            merged = self._resolve_inheritance(
                merged)

        return merged

    def _resolve_inheritance(self,
                              merged: dict
                              ) -> dict:
        inherits_path = Path(
            merged["inherits"]).expanduser()

        if not inherits_path.exists():
            log.warning(
                f"Inherited rtfm not found: "
                f"{inherits_path}")
            return merged

        base = self._parse_rtfm(inherits_path)
        if not base:
            return merged

        combined = {**base, **merged}

        for key in (
                "tools", "personas",
                "addons", "exclude"):
            base_list = base.get(key, [])
            merged_list = merged.get(key, [])
            combined[key] = list(
                dict.fromkeys(
                    base_list + merged_list))

        return combined

    # ── Profile resolution ────────────────────────────
    def _resolve_profile(self,
                          profile_name: str
                          ) -> dict:
        if not profile_name:
            return {}

        if profile_name in self._profile_cache:
            return self._profile_cache[
                profile_name]

        profile_path = (PROFILES_DIR /
                        f"{profile_name}.yaml")

        if not profile_path.exists():
            log.warning(
                f"Profile not found: "
                f"{profile_name}")
            return {}

        try:
            with open(profile_path, 'r') as f:
                profile = yaml.safe_load(f)
            self._profile_cache[
                profile_name] = profile
            log.debug(
                f"Loaded profile: {profile_name}")
            return profile
        except Exception as e:
            log.warning(
                f"Could not load profile "
                f"{profile_name}: {e}")
            return {}

    # ── Persona resolution ────────────────────────────
    def _resolve_personas(self,
                           persona_names: list
                           ) -> list:
        personas = []

        for name in persona_names:
            if name in self._persona_cache:
                personas.append(
                    self._persona_cache[name])
                continue

            persona_path = (PERSONAS_DIR /
                            f"{name}.md")

            if not persona_path.exists():
                log.warning(
                    f"Persona not found: {name}")
                continue

            try:
                post = frontmatter.load(
                    str(persona_path))
                persona = dict(post.metadata)
                persona["_instruction"] = (
                    post.content)
                persona["_filepath"] = str(
                    persona_path)
                self._persona_cache[name] = persona
                personas.append(persona)
                log.debug(
                    f"Loaded persona: {name}")
            except Exception as e:
                log.warning(
                    f"Could not load persona "
                    f"{name}: {e}")

        return personas

    # ── Instruction builder ───────────────────────────
    def _build_instructions(self,
                             personas: list,
                             merged_rtfm: dict
                             ) -> str:
        """
        Combine persona instructions and
        project context into one system prompt.
        Order: who you are → where you are
        → known decisions (placeholder).
        """
        sections = []

        # 1. Persona instructions
        if personas:
            persona_text = []
            for p in personas:
                instruction = p.get(
                    "_instruction", "").strip()
                if instruction:
                    pname = p.get(
                        "persona_name", "")
                    if pname:
                        persona_text.append(
                            f"## {pname}\n"
                            f"{instruction}")
                    else:
                        persona_text.append(
                            instruction)
            if persona_text:
                sections.append(
                    "\n\n".join(persona_text))

        # 2. Project context from rtfm body
        body = merged_rtfm.get(
            "_body", "").strip()
        if body:
            project = merged_rtfm.get(
                "project", "this project")
            sections.append(
                f"## Project Context: "
                f"{project}\n{body}")

        # 3. Decisions placeholder
        sections.append(
            "## Known Decisions\n{decisions}")

        return "\n\n---\n\n".join(sections)

    # ── Decisions injection ───────────────────────────
    def inject_decisions(self,
                          context: dict,
                          decisions: list
                          ) -> dict:
        """
        Called by indexer after assembly.
        Replaces {decisions} placeholder
        with verified decisions from DB.
        """
        if not decisions:
            decision_text = (
                "No prior decisions recorded.")
        else:
            lines = []
            for d in decisions:
                lines.append(
                    f"- {d['decision']}\n"
                    f"  _{d.get('context', '')}_")
            decision_text = "\n".join(lines)

        context["instructions"] = (
            context["instructions"].replace(
                "{decisions}", decision_text))
        context["decisions"] = decisions
        return context

    # ── Empty context ─────────────────────────────────
    def _empty_context(self,
                        cwd: Path = None
                        ) -> dict:
        ollama_cfg = self.config.get("ollama", {})
        return {
            "profile": "default",
            "personas": [],
            "persona_names": [],
            "model": ollama_cfg.get(
                "default_model", "llama3"),
            "fallback_model": ollama_cfg.get(
                "fallback_model", "llama3:7b"),
            "min_context": 4096,
            "project": (
                cwd.name if cwd else "unknown"),
            "cwd": str(cwd or Path.cwd()),
            "status": "active",
            "git": False,
            "tools": [],
            "instructions": "",
            "session_dir": str(
                APP_ROOT / "sessions" /
                (cwd.name if cwd else "unknown")),
            "decisions": [],
            "assembled_at": (
                datetime.now().isoformat()),
            "rtfm_files": [],
            "notes": "",
        }

    def refresh_caches(self):
        """
        Clear persona and profile caches.
        Called by CodeMaid after editing files.
        """
        self._persona_cache.clear()
        self._profile_cache.clear()
        log.info("Assembler caches cleared")
