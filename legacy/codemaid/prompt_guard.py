"""
CodeCrew Prompt Guard — The "Kitty Syntax Scanner" for AI Prompts.
Ensures no "Dirty Code" (hallucination-prone or risky prompts) leaves the Maid.
"""

import re
import shlex

class PromptIssue:
    def __init__(self, severity: str, description: str, suggestion: str):
        self.severity = severity
        self.description = description
        self.suggestion = suggestion

def scan_prompt(user_input: str, current_context_size: int) -> list[PromptIssue]:
    issues = []
    
    # 1. THE 50KB HALLUCINATION GUARD
    projected_size = current_context_size + len(user_input.encode())
    if projected_size > 50000:
        issues.append(PromptIssue(
            "CRITICAL",
            f"Context Breach: Prompt + History ({projected_size} bytes) exceeds the 50KB limit.",
            "Run /compress or /clear before proceeding to prevent hallucination."
        ))

    # 2. ATOMIC COMMAND GUARD (The "Audit First" Rule)
    # Flags multi-step destructive commands without a stated plan/audit
    destructive_keywords = ["delete", "remove", "rm ", "overwrite", "mv ", "rename"]
    if any(k in user_input.lower() for k in destructive_keywords):
        if not any(k in user_input.lower() for k in ["audit", "todo", "plan", "check"]):
            issues.append(PromptIssue(
                "WARNING",
                "Unplanned Destructive Action: You are asking to delete/move without an audit.",
                "Suggestion: Start with 'Audit the folder and create a TODO before deleting.'"
            ))

    # 3. LOOP DETECTION
    # Detects recursive-style phrasing that confuses LLMs
    loop_patterns = [
        r"(do|repeat|again).*(and then).*(do|repeat|again)",
        r"(for each).*(for each)",
    ]
    for pattern in loop_patterns:
        if re.search(pattern, user_input.lower()):
            issues.append(PromptIssue(
                "WARNING",
                "Potential Logic Loop detected in prompt.",
                "Suggestion: Break the task into smaller, linear steps."
            ))

    # 4. SHELL SYNTAX LEAK
    # Check if user accidentally typed a raw shell command into the chat
    if re.match(r"^(cd|ls|mkdir|rm|git|pip|python)\s+", user_input.lower()):
        issues.append(PromptIssue(
            "INFO",
            "Prompt looks like a raw shell command.",
            "Use '!' prefix or TAB mode to run shell commands directly."
        ))

    return issues
