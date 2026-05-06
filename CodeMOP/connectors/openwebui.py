# CodeMOP — OpenWebUI Connector
# Parses OpenWebUI HTML session exports.

from pathlib import Path
from bs4 import BeautifulSoup
import re
import logging
from codemop.connectors import (
    BaseConnector,
    empty_session,
)

log = logging.getLogger(
    "codemop.connectors.openwebui")


class OpenWebUIConnector(BaseConnector):

    FINGERPRINTS = [
        "open-webui",
        "openwebui",
        "chat-export",
    ]

    def can_handle(self,
                   filepath: Path) -> bool:
        if filepath.suffix.lower() != ".html":
            return False
        try:
            with open(filepath, 'r',
                      encoding='utf-8',
                      errors='ignore') as f:
                header = f.read(2048).lower()
            return any(
                fp in header
                for fp in self.FINGERPRINTS)
        except Exception:
            return False

    def parse(self,
              filepath: Path) -> dict:
        session = empty_session()
        session["tool"] = "openwebui"
        session["filepath"] = str(filepath)
        session["date"] = self._extract_date(
            filepath)

        with open(filepath, 'r',
                  encoding='utf-8',
                  errors='ignore') as f:
            html = f.read()

        soup = BeautifulSoup(html, 'html.parser')

        session["model"] = self._extract_model(
            soup)
        session["project"] = (
            self._extract_project(soup, filepath))

        messages = self._extract_messages(soup)
        overview = self._extract_overview(soup)

        if overview:
            session["summary"] = overview.get(
                "summary", "")
            session["decisions"] = overview.get(
                "decisions", [])
            session["dead_ends"] = overview.get(
                "dead_ends", [])
            session["outcome"] = "completed"
        else:
            session["summary"] = (
                self._summarize_tail(messages))
            session["outcome"] = "reference"

        log.info(
            f"OpenWebUI parsed: "
            f"{len(messages)} messages "
            f"{len(session['decisions'])} "
            f"decisions")

        return session

    def _extract_model(self,
                       soup: BeautifulSoup
                       ) -> str:
        for meta in soup.find_all("meta"):
            if "model" in meta.get(
                    "name", "").lower():
                return meta.get(
                    "content", "unknown")

        for tag in soup.find_all(
                attrs={"data-model": True}):
            return tag["data-model"]

        for script in soup.find_all("script"):
            text = script.string or ""
            match = re.search(
                r'"model"\s*:\s*"([^"]+)"', text)
            if match:
                return match.group(1)

        return "unknown"

    def _extract_project(self,
                         soup: BeautifulSoup,
                         filepath: Path) -> str:
        title = soup.find("title")
        if title and title.string:
            return title.string.strip()

        h1 = soup.find("h1")
        if h1:
            return h1.get_text().strip()

        return filepath.parent.name

    def _extract_messages(self,
                          soup: BeautifulSoup
                          ) -> list:
        messages = []

        for msg in soup.find_all(
                attrs={"data-role": True}):
            role = msg.get("data-role", "")
            content = self._clean_text(
                msg.get_text())
            if content:
                messages.append({
                    "role": role,
                    "content": content
                })

        if not messages:
            for msg in soup.find_all(
                    class_=re.compile(
                        r"message|chat-message")):
                content = self._clean_text(
                    msg.get_text())
                if content:
                    messages.append({
                        "role": "unknown",
                        "content": content
                    })

        return messages

    def _extract_overview(self,
                          soup: BeautifulSoup
                          ) -> dict:
        overview_section = None

        for candidate in soup.find_all(
                id=re.compile(
                    r"overview|summary", re.I)):
            overview_section = candidate
            break

        if not overview_section:
            for candidate in soup.find_all(
                    class_=re.compile(
                        r"overview|summary",
                        re.I)):
                overview_section = candidate
                break

        if not overview_section:
            for heading in soup.find_all(
                    ["h1", "h2", "h3", "h4"]):
                if "overview" in heading\
                        .get_text().lower():
                    overview_section = (
                        heading.find_next_sibling())
                    break

        if not overview_section:
            return None

        return self._parse_overview_text(
            overview_section.get_text())

    def _parse_overview_text(self,
                              text: str) -> dict:
        result = {
            "summary": "",
            "decisions": [],
            "dead_ends": []
        }

        lines = text.strip().split("\n")
        current_section = None
        summary_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            lower = line.lower()

            if any(x in lower for x in [
                    "decision", "resolved",
                    "confirmed", "agreed"]):
                current_section = "decisions"
                continue
            elif any(x in lower for x in [
                    "dead end", "abandoned",
                    "tried", "failed approach"]):
                current_section = "dead_ends"
                continue
            elif any(x in lower for x in [
                    "summary", "overview",
                    "conclusion"]):
                current_section = "summary"
                continue

            if line.startswith(
                    ("-", "•", "*", "·")):
                content = line.lstrip(
                    "-•*· ").strip()
                if current_section == "decisions":
                    result["decisions"].append({
                        "decision": content,
                        "context": "",
                        "verified": True
                    })
                elif (current_section ==
                      "dead_ends"):
                    result["dead_ends"].append(
                        content)
                elif (current_section ==
                      "summary"):
                    summary_lines.append(content)
            else:
                if current_section == "summary":
                    summary_lines.append(line)
                elif not current_section:
                    summary_lines.append(line)

        result["summary"] = " ".join(
            summary_lines)
        return result

    def _summarize_tail(self,
                        messages: list) -> str:
        if not messages:
            return "No messages found"
        tail = messages[-3:]
        parts = []
        for m in tail:
            role = m.get("role", "unknown")
            content = m.get("content", "")[:200]
            parts.append(f"{role}: {content}...")
        return " | ".join(parts)
