"""
UIState — all mutable single-value state for the TUI, gathered in one dataclass.

Replaces the ~25 single-element list wrappers (e.g. ``vault_on = [True]``)
that were scattered through ``main.py`` as a closure-mutation workaround.
Attribute assignment works naturally on a dataclass instance, so nested
functions can write ``st.vault_on = False`` without needing ``nonlocal``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class UIState:
    # ── vault / mode flags ────────────────────────────────────────────────────
    vault_on:      bool = True
    sudo_mode:     bool = False
    dry_run:       bool = False
    shell_mode:    bool = False
    allowlist_mode: bool = False
    guard_mode:    bool = True

    # ── draw timing ───────────────────────────────────────────────────────────
    spin_frame:    int   = 0
    last_draw_t:   float = 0.0

    # ── vault severity of the last confirmed command ──────────────────────────
    last_vault:    str   = "free"   # matches vault.FREE constant

    # ── token tracking ────────────────────────────────────────────────────────
    token_count:   int   = 0
    turn_tokens:   int   = 0
    rate_tokens:   int   = 0
    rate_t:        float = 0.0
    token_rate:    float = 0.0

    # ── thinking / display ────────────────────────────────────────────────────
    show_thinking: bool  = True
    think_start:   float = 0.0
    current_tool:  Optional[Tuple[str, str]] = None
    tool_expanded: bool  = False

    # ── verb animation ────────────────────────────────────────────────────────
    verb_idx:      int   = 0
    verb_t:        float = 0.0

    # ── todo navigation ───────────────────────────────────────────────────────
    todo_idx:      int   = 0

    # ── message queue ─────────────────────────────────────────────────────────
    pending_msg:   Optional[str] = None

    # ── live streaming buffer ─────────────────────────────────────────────────
    live_buf:      str   = ""
    live_is_think: bool  = False

    # ── provider / model ──────────────────────────────────────────────────────
    prov_name:     str   = "ollama"
    model_idx:     int   = 0

    # ── input loop state ──────────────────────────────────────────────────────
    is_thinking:   bool  = False
    input_buffer:  str   = ""

    # ── scroll ────────────────────────────────────────────────────────────────
    scroll_offset: int   = 0   # lines from bottom; 0 = latest

    # ── activity overlay (tool calls / thinking — floats above input) ─────────
    tool_log:      list  = field(default_factory=list)  # [(icon, label)] recent activity
    TOOL_LOG_MAX:  int   = 5

    # ── service status (polled async, shown in header) ────────────────────────
    svc_ollama:    bool  = False
    svc_pi:        bool  = False

    # ── self-declared session name (set by the model) ─────────────────────────
    session_name:  Optional[str] = None
