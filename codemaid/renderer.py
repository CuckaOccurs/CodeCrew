"""
CODEMAID Renderer — Clean chat + floating activity overlay.

Layout:
  ── status bar: persona │ Pi ● │ Ollama ● │ skills/rules/lean ──
  [chat history — scrollable]
  ── thin bar ──────────────────────────
  [activity overlay: tool log, queue, thinking/status]
  ── thin bar ──────────────────────────
  [input line]
  ── thin bar ──────────────────────────
"""
import shutil

from .config import _A, _P, _R, _I, _D, _Z

_DIM  = "\033[38;2;30;50;65m"   # bar/border — deep blue-grey, Night Owl

_SPIN = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class Renderer:
    def __init__(self, st, draw_lock, history, todos, agent,
                 work_dir, profile_name, load_status, render_fn):
        self.st           = st
        self.draw_lock    = draw_lock
        self.history      = history
        self.todos        = todos
        self.agent        = agent
        self.work_dir     = work_dir
        self.profile_name = profile_name
        self.load_status  = load_status
        self.render_fn    = render_fn

    def on_resize(self):
        pass

    # ── status bar (top) ─────────────────────────────────────────────────────

    def _status_bar(self, w: int) -> str:
        dot_on  = f"{_I}●{_Z}"
        dot_off = f"{_R}●{_Z}"

        # name tile
        display_name = self.st.session_name or (self.profile_name or 'maid').capitalize()
        name = f"{_A}{display_name}{_Z}"

        # service dots
        pi_dot     = dot_on if self.st.svc_pi     else dot_off
        ollama_dot = dot_on if self.st.svc_ollama else dot_off

        # loaded context summary
        ls = self.load_status or {}
        parts = []
        if ls.get("skills"):    parts.append(f"S:{ls.get('skill_count',0)}")
        if ls.get("rules"):     parts.append(f"R:{ls.get('rule_count',0)}")
        if ls.get("instructions"): parts.append("I")
        loaded = f"{_D}  {('  '.join(parts)) or '—'}{_Z}"

        sep = f"{_DIM} │ {_Z}"
        bar = (f"{_DIM}─{_Z} {name}{sep}"
               f"Pi {pi_dot}{sep}"
               f"Ollama {ollama_dot}"
               f"{loaded}")
        return bar

    # ── activity overlay lines ───────────────────────────────────────────────

    def _overlay_lines(self, w: int) -> list[str]:
        lines = []

        # queued messages
        for msg in self.st.tool_log:
            icon, label = msg if isinstance(msg, tuple) else ("·", msg)
            lines.append(f"  {_D}{icon}  {label[:w-6]}{_Z}")

        # current tool (most prominent)
        if self.st.current_tool:
            label, _ = self.st.current_tool
            lines.append(f"  {_I}⚒  {label[:w-6]}{_Z}")

        # thinking spinner
        if self.st.is_thinking:
            sp = _SPIN[self.st.spin_frame % 10]
            lines.append(f"  {_R}●{_Z} {_A}{sp}{_Z} {_P}thinking...{_Z}")

        return lines

    # ── draw ─────────────────────────────────────────────────────────────────

    def draw(self):
        with self.draw_lock:
            w, h = shutil.get_terminal_size()
            bar  = f"{_DIM}{'─' * w}{_Z}"

            overlay = self._overlay_lines(w)
            # layout heights: status(1) + 3 bars + 1 input + overlay lines
            reserved     = 1 + 3 + 1 + len(overlay)
            history_h    = max(1, h - reserved)

            # scroll
            total  = len(self.history)
            offset = max(0, min(self.st.scroll_offset, max(0, total - history_h)))
            end    = total - offset
            start  = max(0, end - history_h)

            out = "\033[H\033[2J"

            # status bar
            out += self._status_bar(w) + "\n"

            # chat history
            for _, ansi_str in self.history[start:end]:
                out += ansi_str

            # pad to push overlay flush against the bars
            rendered_lines = sum(s.count("\n") + 1 for _, s in self.history[start:end])
            pad = history_h - rendered_lines
            if pad > 0:
                out += "\n" * pad

            # top bar
            out += bar + "\n"

            # activity overlay
            for line in overlay:
                out += line + "\n"

            # middle bar
            out += bar + "\n"

            # input
            mode = "!" if self.st.shell_mode else ">"
            out += f"  {_A}{mode}{_Z} {self.st.input_buffer}\n"

            # bottom bar
            out += bar

            import sys
            sys.stdout.write(out)
            sys.stdout.flush()

    # ── helpers ──────────────────────────────────────────────────────────────

    def bubble_right(self, text: str) -> str:
        from .config import _T
        return f"{_T}YOU:{_Z} {text}\n"

    def tool_summary(self, name: str, args: dict) -> tuple[str, str]:
        from .config import _tool_label
        return _tool_label(name, args), ""

    def push_tool_log(self, icon: str, label: str) -> None:
        self.st.tool_log.append((icon, label))
        if len(self.st.tool_log) > self.st.TOOL_LOG_MAX:
            self.st.tool_log.pop(0)

    def clear_tool_log(self) -> None:
        self.st.tool_log.clear()
