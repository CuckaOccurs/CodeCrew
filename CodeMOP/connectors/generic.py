# CodeMOP — Generic Connector
# Handles any session file OpenWebUI and
# Pi-Coder connectors can't handle.
# Uses Ollama to generate summary.
# Always the last resort. Always returns something.

from pathlib import Path
from bs4 import BeautifulSoup
import json
import re
import logging
import requests
from codemop.connectors import (
    BaseConnector,
    empty_session,
)
from codemop import load_config

log = logging.getLogger(
    "codemop.connectors.generic")

SUMMARY_PROMPT = """You are a session analyzer.
Given this conversation extract the following.
Return ONLY valid JSON, no preamble, no markdown.

{{
    "summary": "One paragraph overview",
    "decisions": [
        {{
            "decision": "What was decided",
            "context": "Why it was decided",
            "verified": true
        }}
    ],
    "dead_ends": [
        "Approach tried and abandoned"
    ],
    "outcome": "completed or abandoned or reference"
}}

Conversation:
{conversation}
"""


class GenericConnector(BaseConnector):
    """
    Handles HTML, JSONL, plain text, markdown.
    Uses Ollama to generate summary when
    no structured overview exists.
    Always the last resort connector.
    """

    def can_handle(self,
                   filepath: Path) -> bool:
        # Generic handles everything
        return True

    def parse(self,
              filepath: Path) -> dict:
        session = empty_session()
        session["tool"] = "generic"
        session["filepath"] = str(filepath)
        session["date"] = self._extract_date(
            filepath)
        session["project"] = filepath.parent.name

        suffix = filepath.suffix.lower()

        if suffix == ".html":
            text = self._extract_html_text(
                filepath)
        elif suffix == ".jsonl":
            text = self._extract_jsonl_text(
                filepath)
        elif suffix in (".md", ".txt", ".log"):
            text = filepath.read_text(
                encoding='utf-8',
                errors='ignore')
        else:
            text = filepath.read_text(
                encoding='utf-8',
                errors='ignore')

        if not text or len(text) < 50:
            log.warning(
                f"Generic: too little text "
                f"in {filepath.name}")
            return session

        overview = self._generate_overview(text)

        if overview:
            session["summary"] = overview.get(
                "summary", "")
            session["decisions"] = overview.get(
                "decisions", [])
            session["dead_ends"] = overview.get(
                "dead_ends", [])
            session["outcome"] = overview.get(
                "outcome", "reference")
        else:
            session["summary"] = text[:500]
            session["outcome"] = "reference"

        log.info(
            f"Generic parsed: {filepath.name}")

        return session

    def _extract_html_text(self,
                           filepath: Path
                           ) -> str:
        with open(filepath, 'r',
                  encoding='utf-8',
                  errors='ignore') as f:
            html = f.read()
        soup = BeautifulSoup(html, 'html.parser')
        return self._clean_text(soup.get_text())

    def _extract_jsonl_text(self,
                            filepath: Path
                            ) -> str:
        lines = []
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    msg = data.get("message", "")
                    resp = data.get(
                        "response", "")
                    if msg:
                        lines.append(
                            f"User: {msg}")
                    if resp:
                        lines.append(
                            f"Assistant: {resp}")
        except Exception as e:
            log.warning(
                f"JSONL extraction error: {e}")
        return "\n".join(lines)

    def _generate_overview(self,
                           text: str) -> dict:
        config = load_config()
        base_url = (config
                    .get("ollama", {})
                    .get("url",
                         "http://localhost:11434"))

        model = self._get_smallest_model(base_url)
        if not model:
            log.warning(
                "No model available for "
                "generic summarization")
            return {}

        # Truncate to avoid context overflow
        truncated = text[:2000]
        if len(text) > 2000:
            truncated += "\n[truncated]"

        prompt = SUMMARY_PROMPT.format(
            conversation=truncated)

        try:
            r = requests.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60)

            raw = r.json().get("response", "")
            raw = re.sub(
                r"```json|```", "", raw).strip()

            return json.loads(raw)

        except json.JSONDecodeError as e:
            log.warning(
                f"Could not parse summary "
                f"JSON: {e}")
            return {}
        except Exception as e:
            log.warning(
                f"Ollama summarization "
                f"failed: {e}")
            return {}

    def _get_smallest_model(self,
                            base_url: str
                            ) -> str:
        try:
            r = requests.get(
                f"{base_url}/api/tags",
                timeout=5)
            models = r.json().get("models", [])

            if not models:
                return ""

            sorted_models = sorted(
                models,
                key=lambda m: m.get("size", 0))

            return sorted_models[0].get(
                "name", "")

        except Exception:
            return ""
