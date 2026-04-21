"""
CODEMAID Web Tools — web_search, web_scrape, read_document.
"""

import ipaddress
import re
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any

import requests

from .common import _audit_log, _check_confinement

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information using Firecrawl.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_scrape",
            "description": "Fetch and read the text content of a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to scrape."},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read the text content of a PDF, Word, or Excel file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the document."},
                },
                "required": ["path"],
            },
        },
    },
]

# SSRF: hosts that are always blocked
_SSRF_BLOCKED_HOSTS = {
    "169.254.169.254",           # AWS/GCP/Azure instance metadata
    "100.100.100.200",           # Alibaba metadata
    "metadata.google.internal",
    "localhost",
    "127.0.0.1",
    "::1",
}


def _check_ssrf(url: str) -> str | None:
    """Return an error string if the URL targets a private/internal address, else None."""
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname or ""
    if hostname in _SSRF_BLOCKED_HOSTS:
        return f"🛡️ SSRF BLOCKED: Access to {hostname} is not allowed."
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return f"🛡️ SSRF BLOCKED: Access to private/internal IP {hostname} is not allowed."
    except ValueError:
        pass  # not a raw IP — hostname is fine
    return None


def execute(name: str, args: dict[str, Any], work_dir: str | Path, **kwargs: Any) -> dict[str, Any] | None:
    """Execute a web tool. Returns result dict or None if name not handled."""

    if name == "web_search":
        query = args.get("query")
        try:
            which_fc = subprocess.run(
                ["which", "firecrawl-search"], capture_output=True, text=True, timeout=5,
            )
            if which_fc.returncode == 0:
                cmd = ["firecrawl-search", query]
            else:
                return {"error": "Firecrawl not installed. Install with: npm i -g @mendable/firecrawl-cli"}
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20, cwd=work_dir)
            output = result.stdout
            if not output and result.returncode != 0:
                output = result.stderr or "No search results found."
            if len(output) > 4000:
                output = output[:4000] + "\n... [Search results truncated] ..."
            _audit_log("web_search", query, "ok")
            return {"results": output}
        except Exception as e:
            return {"error": f"Web search failed: {str(e)}"}

    elif name == "web_scrape":
        url = args.get("url")
        try:
            ssrf_err = _check_ssrf(url)
            if ssrf_err:
                return {"error": ssrf_err}

            which_fc = subprocess.run(
                ["which", "firecrawl-scrape"], capture_output=True, text=True, timeout=5,
            )
            if which_fc.returncode == 0:
                cmd = ["firecrawl-scrape", url]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=20, cwd=work_dir)
                output = result.stdout
                if not output and result.returncode != 0:
                    output = result.stderr or "No content found."
            else:
                # Fallback: requests + basic HTML-to-text
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                html = resp.text
                text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                output = text or html

            if len(output) > 4000:
                output = output[:4000] + "\n... [Content truncated] ..."
            _audit_log("web_scrape", url, "ok")
            return {"content": output}
        except Exception as e:
            return {"error": f"Web scrape failed: {str(e)}"}

    elif name == "read_document":
        path = Path(work_dir) / args["path"]
        resolved, err = _check_confinement(path, work_dir)
        if err:
            return {"error": err}
        if not resolved.exists():
            return {"error": f"File not found: {path}"}
        ext = resolved.suffix.lower()
        try:
            if ext == ".pdf":
                result = subprocess.run(
                    ["pdftotext", str(resolved), "-"],
                    capture_output=True, text=True, timeout=20,
                )
                output = result.stdout or result.stderr
            elif ext in (".docx", ".doc"):
                result = subprocess.run(
                    ["pandoc", str(resolved), "-t", "markdown"],
                    capture_output=True, text=True, timeout=20,
                )
                output = result.stdout or result.stderr
            elif ext in (".xlsx", ".xls", ".csv"):
                result = subprocess.run(
                    ["xlsx2csv", str(resolved), "-"],
                    capture_output=True, text=True, timeout=20,
                )
                if result.returncode != 0:
                    output = resolved.read_text(encoding="utf-8")
                else:
                    output = result.stdout or result.stderr
            else:
                return {"content": resolved.read_text(encoding="utf-8")}

            if not output:
                return {"content": "(Document is empty or unreadable)"}
            _audit_log("read_document", str(path), "ok")
            return {"content": output[:10000]}
        except Exception as e:
            return {"error": f"Read document failed: {str(e)}"}

    return None
