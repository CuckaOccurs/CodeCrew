"""
CODEMAID Prompt Guard

Catches prompts likely to cause agent loops or hallucinations before they
reach the model. The goal is not to block — it's to warn the user so they
can tighten the prompt and let the context system do its job.
"""
import re
from dataclasses import dataclass
from typing import List

LOOP_RISK          = "loop_risk"
HALLUCINATION_RISK = "hallucination_risk"
CONTEXT_GAP        = "context_gap"
CONTRADICTION      = "contradiction"

@dataclass
class PromptIssue:
    type: str
    description: str
    severity: str    # "warn" | "block"
    span: str = ""


# ── Loop triggers ─────────────────────────────────────────────────────────────
# Prompts that tend to send agents into infinite or near-infinite cycles

_LOOP_PATTERNS = [
    (r'\bkeep (doing|trying|going|fixing|running|checking|looping)\b',
     "Open-ended 'keep doing' — agent may loop indefinitely"),
    (r'\brepeat (this|that|until|for (all|every|each))\b',
     "Repeat instruction without a clear stop condition"),
    (r'\buntil (it works|done|finished|complete|perfect|correct)\b',
     "Vague completion condition — loop risk"),
    (r'\bfix (everything|all (the )?(errors?|issues?|bugs?|problems?))\b',
     "Broad 'fix everything' — no scoped target, likely to loop"),
    (r'\bdo (this|that) for (all|every|each) (file|function|class|method|line)\b',
     "Unscoped iteration — consider limiting to specific files"),
    (r'\btry (again|it again|different|another way) (if|when|until)\b',
     "Retry loop without exit condition"),
    (r'\bkeep (asking|prompting|checking) (me|the user|until)\b',
     "Agent-initiated loop back to user"),
    (r'\brecurs(e|ively|ion)\b',
     "Recursive instruction — ensure there is a base case"),
    (r'\b(continuously|constantly|forever|indefinitely)\b',
     "No defined stop — agent will run until token limit"),
]

# ── Hallucination triggers ────────────────────────────────────────────────────
# Prompts that invite the model to invent context it doesn't have

_HALLUCINATION_PATTERNS = [
    (r'\b(you (said|told|mentioned|promised|agreed)|you know (what|that))\b',
     "References prior session — model has no persistent memory"),
    (r'\b(last (time|session|conversation|run)|as (we|you) (discussed|agreed|said))\b',
     "Cross-session reference — context resets each run"),
    (r'\b(remember (when|that|how)|you (remember|know) (this|that|me))\b',
     "Memory claim — model cannot recall previous sessions"),
    (r'\b(fill in|make (it|something) up|guess (what|the|it)|assume (the|it))\b',
     "Explicit invitation to hallucinate — model will comply"),
    (r'\b(probably|likely|should be|might be) (in|at|called|named)\b',
     "Uncertain reference — model may invent a plausible but wrong answer"),
    (r'\bwhat (was|were|did) (we|you|i) (doing|working on|building|fixing)\b',
     "Asks model to reconstruct lost context — hallucination likely"),
    (r'\byou (always|never|usually|typically) (do|did|say|handle)\b',
     "Behavioral claim about model — may produce confabulation"),
    (r'\b(the|that) (function|file|class|variable|method) (we|you) (made|wrote|built|created)\b',
     "References unnamed prior work — model may invent a match"),
]

# ── Context gaps ──────────────────────────────────────────────────────────────
# Prompts that are too vague to act on without the context system being loaded

_CONTEXT_GAP_PATTERNS = [
    (r'^\s*(do|fix|update|change|edit|check|run|test|make)\s+(it|that|this)\s*[.!?]?\s*$',
     "Too vague — no target specified. Load context or be more specific."),
    (r'\b(the|that) (thing|stuff|code|part|bit)\b',
     "Vague reference — which thing? Which part?"),
    (r'\b(do|fix|handle) (the rest|the others|the remaining)\b',
     "Unscoped remainder — remaining what? From where?"),
    (r'\blike (before|last time|we did|you did)\b',
     "References undefined prior pattern"),
    (r'\b(same as|similar to) (before|last|the other|what you did)\b',
     "Similarity reference with no anchor in current context"),
]

# ── Contradictions ────────────────────────────────────────────────────────────

_CONTRADICTION_PATTERNS = [
    (r'\b(delete|remove|rm)\b.{0,80}\b(backup|keep|save|preserve)\b',
     "Delete and preserve same target — contradictory"),
    (r'\bnever\b.{0,60}\balways\b',
     "Never / always in same instruction — contradictory"),
    (r"\bdon'?t\b.{0,60}\bbut\b.{0,60}\bdo\b",
     "Don't / do in same instruction — may confuse model"),
    (r'\b(read.only|no.write|don.?t (edit|change|modify))\b.{0,80}\b(edit|write|change|modify|update)\b',
     "Read-only constraint then write instruction — contradictory"),
]


def analyze_prompt(text: str) -> List[PromptIssue]:
    """
    Analyze a user prompt for loop risk, hallucination triggers, context gaps,
    and contradictions. Returns a list of issues — empty means prompt looks clean.
    """
    issues: List[PromptIssue] = []
    low = text.lower().strip()

    for pattern, desc in _LOOP_PATTERNS:
        m = re.search(pattern, low)
        if m:
            issues.append(PromptIssue(LOOP_RISK, desc, "warn", m.group(0)[:60]))

    for pattern, desc in _HALLUCINATION_PATTERNS:
        m = re.search(pattern, low)
        if m:
            issues.append(PromptIssue(HALLUCINATION_RISK, desc, "warn", m.group(0)[:60]))

    for pattern, desc in _CONTEXT_GAP_PATTERNS:
        m = re.search(pattern, low)
        if m:
            issues.append(PromptIssue(CONTEXT_GAP, desc, "warn", m.group(0)[:60]))

    for pattern, desc in _CONTRADICTION_PATTERNS:
        m = re.search(pattern, low, re.DOTALL)
        if m:
            issues.append(PromptIssue(CONTRADICTION, desc, "warn", m.group(0)[:60]))

    return issues


def check_looks_like_command(text: str) -> None:
    """Removed — not the guard's job. Use ! prefix for shell commands."""
    return None
