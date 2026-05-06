# CodeMOP — Pi-Coder Connector
# Parses Pi-Coder HTML session exports.

from pathlib import Path
from bs4 import BeautifulSoup
import re
import logging
from codemop.connectors import (
    BaseConnector,
    empty_session,
)

log = logging.getLogger(
    "codemop.connectors.picoder")


class PiCoderConnector(BaseConnector):

    FINGERPRINTS = [
        "pi-coder",
        "picoder",
        "pi_coder",
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
        session["tool"] = "picoder"
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
            f"Pi-Coder parsed: "
            f"{len(messages)} messages")

        return session

    def _extract_model(self,
                       soup: BeautifulSoup
                       ) -> str:
        for tag in soup.find_all(
                class_=re.compile(
                    r"model|status-bar", re.I)):
            text = tag.get_text().strip()
            if text:
                return text

        for tag in soup.find_all(
                attrs={"data-model": True}):
            return tag["data-model"]

        return "unknown"

    def _extract_project(self,
                         soup: BeautifulSoup,
                         filepath: Path) -> str:
        title = soup.find("title")
        if title and title.string:
            return title.string.strip()
        return filepath.parent.name

    def _extract_messages(self,
                          soup: BeautifulSoup
                          ) -> list:
        messages = []

        for msg in soup.find_all(
                class_=re.compile(
                    r"message|turn|exchange",
                    re.I)):
            content = self._clean_text(
                msg.get_text())
            if content and len(content) > 10:
                role = "unknown"
                if msg.find(class_=re.compile(
                        r"user|human", re.I)):
                    role = "user"
                elif msg.find(class_=re.compile(
                        r"assistant|ai|bot",
                        re.I)):
                    role = "assistant"

                messages.append({
                    "role": role,
                    "content": content
                })

        return messages

    def _extract_overview(self,
                          soup: BeautifulSoup
                          ) -> dict:
        for heading in soup.find_all(
                ["h1", "h2", "h3", "h4"]):
            text = heading.get_text().lower()
            if any(x in text for x in [
                    "overview", "summary",
                    "session recap"]):
                sibling = (
                    heading.find_next_sibling())
                if sibling:
                    from codemop.connectors\
                        .openwebui import (
                        OpenWebUIConnector)
                    ow = OpenWebUIConnector()
                    return ow._parse_overview_text(
                        sibling.get_text())
        return None

    def _summarize_tail(self,
                        messages: list) -> str:
        if not messages:
            return "No messages found"
        tail = messages[-3:]
        parts = []
        for m in tail:
            content = m.get("content", "")[:200]
            parts.append(f"{content}...")
        return " | ".join(parts)
