"""
CODEMAID Vault — Command Validation.
Three layers of protection:
  1. Denylist/Allowlist command filtering (this module)
  2. Path confinement checks (tools.py _check_confinement)
  3. Optional Firejail container wrapper (firejail_run)
"""

import re
import shutil
import subprocess
from typing import Tuple, Optional, List

# Severity Levels
FREE  = "free"
CAGE  = "cage"
SAFE  = "safe"

# Legacy aliases
VAULT   = SAFE
WARNING = CAGE
BLOCKED = SAFE

# ---------------------------------------------------------------------------
# Allowlist Mode — commands that are always permitted
# ---------------------------------------------------------------------------

ALLOWED_COMMANDS = [
    # File operations
    r"^ls\b",
    r"^cat\b",
    r"^head\b",
    r"^tail\b",
    r"^wc\b",
    r"^stat\b",
    r"^file\b",
    r"^du\b",
    r"^df\b",
    r"^find\s",
    r"^tree\b",

    # Search
    r"^grep\b",
    r"^egrep\b",
    r"^rg\b",
    r"^ack\b",

    # Git
    r"^git\s+(status|diff|log|branch|tag|show|describe|shortlog|blame)",

    # Build tools
    r"^make\b",
    r"^npm\s+(run|test|build|start)",
    r"^python3?\s+\S+\.py\b",
    r"^pytest\b",
    r"^cargo\s+(build|test|run|check)",
    r"^go\s+(build|test|run|vet)",

    # Version control / misc
    r"^git\s+add\b",
    r"^git\s+commit\b",
    r"^git\s+push\b",
    r"^git\s+pull\b",
    r"^git\s+fetch\b",
    r"^git\s+checkout\b",
    r"^git\s+merge\b",
    r"^git\s+rebase\b",
    r"^git\s+stash\b",

    # Safe system info
    r"^whoami\b",
    r"^hostname\b",
    r"^uname\b",
    r"^date\b",
    r"^pwd\b",
    r"^echo\b",
    r"^printf\b",
]

def _matches_allowlist(command: str) -> Tuple[bool, str]:
    """Check if command matches any allowed pattern."""
    cmd = command.strip()
    for pattern in ALLOWED_COMMANDS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return True, pattern
    return False, ""

# ---------------------------------------------------------------------------
# Denylist Mode — patterns that are always blocked
# ---------------------------------------------------------------------------

BLOCKED_PATTERNS = [
    # Filesystem destruction
    r"rm\s+-[rRfF]+\s+/",            # Recursive force delete from root
    r"rm\s+-[rRfF]+\s+~",            # Recursive force delete home
    r"rm\s+-[rRfF]+\s+\*",           # Recursive force delete all
    r"rm\s+-fr\s+/",                 # Flag order variant: -fr instead of -rf
    r"rm\s+-fr\s+~",
    r"rm\s+-fr\s+\*",
    r"rm\s+-rf\s+/",                 # Original -rf patterns
    r"rm\s+-rf\s+~",
    r"rm\s+-rf\s+\*",
    r"dd\s+if=/dev/zero",            # Zeroing disks
    r"dd\s+if=/dev/random",
    r"mkfs",                         # Formatting filesystems
    r">\s+/dev/sd[a-z]",             # Writing directly to block devices
    r"chmod\s+777\s+/",              # Chmodding root to world-writable
    r"find\s+.+-delete",             # Find with delete action
    r"find\s+.+\|\s*xargs\s+rm",     # Find piped to xargs rm

    # System control
    r"sudo\s+reboot",                # Rebooting
    r"sudo\s+init\s+0",              # Shutting down
    r"sudo\s+shutdown",              # Shutting down

    # Pipe-to-shell (untrusted remote execution)
    r"curl.*\|\s*(ba)?sh",           # Piping curl to sh/bash
    r"curl.*\|\s*zsh",               # Piping curl to zsh
    r"curl.*\|\s*fish",              # Piping curl to fish
    r"wget.*\|\s*(ba)?sh",           # Piping wget to sh/bash
    r"fetch\s+.*\|\s*(ba)?sh",       # BSD fetch piped to shell

    # Interpreter-mediated execution
    r"python3?\s+-c",                # Python one-liners
    r"perl\s+-e",                    # Perl one-liners
    r"ruby\s+-e",                    # Ruby one-liners
    r"node\s+-e",                    # Node.js one-liners
    r"lua\s+-e",                     # Lua one-liners
    r"php\s+-r",                     # PHP one-liners

    # Eval and encoded execution
    r"\beval\b",                     # eval command
    r"base64\s+(-d|--decode)",       # Base64 decode piped to shell
    r"xxd\s+-r",                     # Hex decode
    r"echo\s+.*\|\s*base64",         # Echo piped to base64

    # Credential harvesting
    r"cat\s+~/.ssh/",                # SSH key theft
    r"cat\s+/etc/shadow",            # Password hash theft
    r"\bprintenv\b",                 # Environment variable dump
    r"\benv\b\s*$",                  # Standalone env command (credential dump)
    r"history\s*>\s*",               # Exfiltrating shell history

    # Reverse shells and network exfiltration
    r"nc\s+-[elp]",                  # Netcat listener/reverse shell
    r"netcat\s+-[elp]",
    r"bash\s+-i\s+>&",              # Interactive bash redirect
    r"exec\s+\d+><",                # File descriptor redirection (reverse shell)

    # Shell meta-bypass attempts
    r"\$\(.*\)",                     # Command substitution $(...)
    r"`.*`",                         # Command substitution `...`
    r"^sh\b",                        # sh as the command itself (not as a file extension)
    r"^bash\b",                      # bash as the command itself
    r"^zsh\b",                       # zsh as the command itself
    r";\s*\S",                       # Command chaining with semicolon
    r"\s>\s*\S",                     # Output redirection (echo hello > file)
    r"\s>>\s*\S",                    # Append redirection

    # SSRF (cloud metadata theft)
    r"169\.254\.169\.254",           # AWS/GCP/Azure metadata endpoint
    r"100\.100\.100\.200",           # Alibaba metadata endpoint
]

# Patterns that trigger a warning (logged but allowed)
WARNING_PATTERNS = [
    r"rm\s+-rf",                # General recursive delete
    r"sudo\s+apt\s+remove",     # Removing system packages
    r"pip\s+uninstall",         # Removing python packages
    r"kill\s+-9",               # Force killing processes
    r"systemctl\s+stop",        # Stopping services
]

def validate_command(command: str, allowlist: bool = False, sudo_mode: bool = False) -> Tuple[str, str]:
    """
    Validate a shell command against the safety policy.

    Args:
        command: The raw command string to validate.
        allowlist: If True, only allow known-safe commands. If False (default),
                   use denylist mode (block known-dangerous, allow rest).
        sudo_mode: If True, bypass all blocks (full power).

    Returns:
        (severity, message) — one of SAFE/WARNING/BLOCKED with a description.
    """
    cmd = command.strip()

    if sudo_mode:
        return FREE, "SUDO MODE ACTIVE: Bypassing validation."

    if allowlist:
        ok, pattern = _matches_allowlist(cmd)
        if ok:
            return FREE, f"Allowed (matches {pattern})"
        return SAFE, f"🛡️ ALLOWLIST BLOCKED: '{cmd[:60]}' is not in the safe command list."

    cmd_lower = cmd.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, cmd_lower):
            return SAFE, f"🛡️ VAULT BLOCKED: Command matches dangerous pattern '{pattern}'."

    for pattern in WARNING_PATTERNS:
        if re.search(pattern, cmd_lower):
            return CAGE, f"⚠️ VAULT WARNING: Command matches sensitive pattern '{pattern}'. Proceeding with caution."

    return FREE, "Command validated."

def firejail_run(cmd_args: List[str], work_dir: str) -> List[str]:
    """Wrap a command in a Firejail sandbox if available."""
    if not shutil.which("firejail"):
        return cmd_args

    # Basic Firejail profile:
    # --private: hide home directory
    # --net=none: disable network access
    # --quiet: don't show firejail header
    # --noprofile: use a basic default sandbox
    wrapper = [
        "firejail",
        "--quiet",
        "--noprofile",
        "--net=none",
        f"--whitelist={work_dir}",
        "--private",
    ]
    return wrapper + cmd_args
