# CodeMOP — Syntax Guard
# Screens AI intent and proposed code for dangerous patterns.
# "The maid cleans the code before it touches the floor."

import re
import logging
from pathlib import Path

log = logging.getLogger("codemop.guard")

class SyntaxGuard:
    def __init__(self):
        # ... (rest of init remains same)
        self.forbidden_patterns = [
            r"rm\s+-rf\s+/",             # Root wipe
            r"rm\s+-rf\s+~",             # Home wipe
            r"mkfs\.",                   # Filesystem formatting
            r"dd\s+if=",                 # Raw disk writing
            r"> /dev/sd",                # Device overwriting
            r"chmod\s+-R\s+777",         # Global insecure permissions
            r":\(\)\{ :\|:& \};:",       # Fork bomb
        ]

        # Patterns that trigger warnings or require "Free" mode
        self.destructive_patterns = [
            r"\brm\s+",
            r"\bdrop\s+table\b",
            r"\btruncate\s+table\b",
            r"\bwipe\b",
            r"\bformat\b",
            r"\bdelete\s+from\b",
        ]

        # Logic loop patterns (hallucination guards)
        self.loop_patterns = [
            r"while\s+True:\s*pass",     # Busy wait loop
            r"while\s+1:\s*pass",
            r"for\s+.*\s+in\s+itertools\.count\(\):", # Infinite iterator without break
        ]

    def check_message(self, message: str, vault_mode: str, cwd: str = None) -> tuple[bool, str]:
        """
        Check a message/intent against the vault security model.
        Returns (is_allowed, reason).
        """
        vault = vault_mode.lower()
        
        # Free mode: Everything allowed, but we still log critical patterns
        if vault == "free":
            for p in self.forbidden_patterns:
                if re.search(p, message, re.IGNORECASE):
                    log.warning(f"Vault [FREE] detected CRITICAL pattern: {p}")
            return True, ""

        # Check forbidden patterns (blocked in Safe/Cage)
        for p in self.forbidden_patterns:
            if re.search(p, message, re.IGNORECASE):
                return False, f"Critical security violation detected: {p}"

        # Safe mode: No destructive commands at all
        if vault == "safe":
            for p in self.destructive_patterns:
                if re.search(p, message, re.IGNORECASE):
                    return False, f"Destructive command blocked in SAFE mode: {p}"

        # Cage mode: Check for attempts to break out of CWD
        if vault == "cage":
            if cwd:
                base = Path(cwd).resolve()
                # Find things that look like paths (contain / or ..)
                potential_paths = re.findall(r"([a-zA-Z0-9._\-/~]+)", message)
                for p in potential_paths:
                    if "/" in p or ".." in p:
                        try:
                            # Resolve path relative to base if it's not absolute
                            path = Path(p).expanduser()
                            if not path.is_absolute():
                                path = base / path
                            
                            resolved = path.resolve()
                            if not str(resolved).startswith(str(base)):
                                return False, f"Path escape attempt detected in CAGE mode: {p}"
                        except Exception:
                            # If we can't resolve it, but it contains .., block it just in case
                            if ".." in p:
                                return False, f"Suspicious path detected in CAGE mode: {p}"
            
            # Fallback for when cwd is not provided or additional safety
            if "../.." in message or "/etc/" in message or "/var/" in message:
                 return False, "Path escape attempt detected in CAGE mode (string match)."

        # Check for potential hallucinated loops in code blocks
        if "```" in message:
            code_blocks = re.findall(r"```(?:python|bash)?(.*?)```", message, re.DOTALL)
            for block in code_blocks:
                for p in self.loop_patterns:
                    if re.search(p, block):
                        return False, f"Potential infinite loop detected in code block: {p}"

        return True, ""

    def sanitize(self, text: str) -> str:
        """
        In the future: replace dangerous strings with placeholders.
        For now: just a placeholder for the NewsFeed/PestoDict sanitization logic.
        """
        return text
