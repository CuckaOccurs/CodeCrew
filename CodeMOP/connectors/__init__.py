# CodeMOP — Connector Base Classes
# Every connector inherits from BaseConnector.
# Every connector returns the same standard
# session object. Tool doesn't matter to indexer.

from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
import logging
import re

log = logging.getLogger("codemop.connectors")


def empty_session() -> dict:
    """
    Standard session object.
    Every connector returns this structure.
    """
    return {
        "tool": "unknown",
        "project": "unknown",
        "model": "unknown",
        "profile": "unknown",
        "date": datetime.now().strftime(
            "%Y-%m-%d"),
        "outcome": "unknown",
        "decisions": [],
        "dead_ends": [],
        "summary": "",
        "filepath": "",
        "parsed_at": datetime.now().isoformat()
    }


class BaseConnector:
    """
    Base class for all connectors.
    Subclasses must implement
    can_handle() and parse().
    """

    def can_handle(self,
                   filepath: Path) -> bool:
        raise NotImplementedError

    def parse(self,
              filepath: Path) -> dict:
        raise NotImplementedError

    def _safe_parse(self,
                    filepath: Path) -> dict:
        try:
            return self.parse(filepath)
        except Exception as e:
            log.warning(
                f"{self.__class__.__name__} "
                f"failed on {filepath}: {e}")
            session = empty_session()
            session["filepath"] = str(filepath)
            return session

    def _extract_date(self,
                      filepath: Path) -> str:
        name = filepath.stem
        patterns = [
            r"(\d{4}-\d{2}-\d{2})",
            r"(\d{4}_\d{2}_\d{2})",
            r"(\d{8})"
        ]
        for pattern in patterns:
            match = re.search(pattern, name)
            if match:
                raw = match.group(1).replace(
                    "_", "-")
                if len(raw) == 8:
                    raw = (f"{raw[:4]}-"
                           f"{raw[4:6]}-"
                           f"{raw[6:]}")
                return raw

        mtime = filepath.stat().st_mtime
        return datetime.fromtimestamp(
            mtime).strftime("%Y-%m-%d")

    def _clean_text(self, text: str) -> str:
        class Stripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []

            def handle_data(self, data):
                self.text.append(data)

            def get_text(self):
                return " ".join(self.text)

        stripper = Stripper()
        stripper.feed(text)
        return " ".join(
            stripper.get_text().split())


class ConnectorRegistry:
    """
    Knows about all connectors.
    Auto detects which one to use.
    Generic is always the fallback.
    """

    def __init__(self):
        from codemop.connectors.openwebui import (
            OpenWebUIConnector)
        from codemop.connectors.picoder import (
            PiCoderConnector)
        from codemop.connectors.generic import (
            GenericConnector)

        # Most specific first
        self.connectors = [
            OpenWebUIConnector(),
            PiCoderConnector(),
            GenericConnector(),
        ]

    def detect(self,
               filepath: Path) -> BaseConnector:
        for connector in self.connectors:
            if connector.can_handle(filepath):
                log.info(
                    f"Using "
                    f"{connector.__class__.__name__}"
                    f" for {filepath.name}")
                return connector
        return self.connectors[-1]

    def parse(self, filepath: Path) -> dict:
        connector = self.detect(filepath)
        return connector._safe_parse(filepath)
