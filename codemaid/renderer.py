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

from .config import _A, _P, _R, _I, _D, _Z, _G, _Y, _T, _tool_label

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
        # Force a full screen clear on resize to prevent ghosting
        import sys
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        self.draw()

    # ── status bar (top) ─────────────────────────────────────────────────────

    def _status_bar(self, w: int) -> str:
        # RGB Status logic: GREEN (Ready), YELLOW (No local RTFM), RED (Offline)
        status_color = _G
        if not self.st.svc_pi or not self.st.svc_ollama:
            status_color = _R
        elif not self.load_status or not self.load_status.get("instructions"):
            status_color = _Y

        dot = f"{status_color}●{_Z}"
        display_name = self.st.session_name or (self.profile_name or 'maid').capitalize()
        name = f"{_A}{display_name}{_Z}"

        pi_stat     = f"{_G}Pi{_Z}" if self.st.svc_pi else f"{_R}Pi{_Z}"
        ollama_stat = f"{_G}Oll{_Z}" if self.st.svc_ollama else f"{_R}Oll{_Z}"

        sep = f"{_DIM}│{_Z}"
        ctx_k = sum(len(str(m).encode()) for m in (self.agent.history if self.agent else [])) // 1024
        
        return (f" {dot} {name} {sep} {pi_stat} {sep} {ollama_stat} {sep} "
                f"{_D}Ctx: {ctx_k}K/50K{_Z}")

    # ── activity overlay lines ───────────────────────────────────────────────

    def _overlay_lines(self, w: int) -> list[str]:
        lines = []

        # ── LIVE TASK MAP ──
        if self.st.is_thinking:
            lines.append(f"  {_D}┌── TASK MAP ───────────────────────────{_Z}")
            if self.st.current_tool:
                label, _ = self.st.current_tool
                lines.append(f"  {_D}│{_Z} {_G}▶ ACTIVE:{_Z} {label[:w-15]}")

            recent_logs = self.st.tool_log[-2:]
            for icon, label in recent_logs:
                lines.append(f"  {_D}│{_Z} {_D}✓ DONE:   {label[:w-15]}{_Z}")
            lines.append(f"  {_D}└──────────────────────────────────────{_Z}")

        # thinking spinner
        if self.st.is_thinking:
            sp = _SPIN[self.st.spin_frame % 10]
            lines.append(f"  {_P}{sp} The Crew is analyzing...{_Z}")

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

            # Move to home instead of clear to reduce flicker
            # \033[H = move to top-left
            out = "\033[H"

            # status bar
            out += self._status_bar(w) + "\033[K\n"

            # chat history - we clear each line as we go with \033[K
            lines_printed = 0
            for _, ansi_str in self.history[start:end]:
                # We need to be careful with multi-line strings
                for line in ansi_str.splitlines():
                    if lines_printed < history_h:
                        out += line[:w] + "\033[K\n"
                        lines_printed += 1
            
            # Fill remaining history area
            while lines_printed < history_h:
                out += "\033[K\n"
                lines_printed += 1

            # top bar
            out += bar + "\033[K\n"

            # activity overlay
            for line in overlay:
                out += line + "\033[K\n"

            # middle bar
            out += bar + "\033[K\n"

            # input
            mode = "!" if self.st.shell_mode else ">"
            # Ensure input doesn't overflow terminal width and cause wrapping issues
            input_text = self.st.input_buffer
            max_input_w = w - 6
            if len(input_text) > max_input_w:
                input_text = "..." + input_text[-(max_input_w-3):]
            
            input_line = f"  {_A}{mode}{_Z} {input_text}"
            out += input_line + "\033[K\n"

            # bottom bar
            out += bar + "\033[K"

            # park cursor at end of input buffer
            input_row = 1 + history_h + 1 + len(overlay) + 1 + 1
            cursor_col = 4 + len(input_text)
            out += f"\033[{input_row};{cursor_col}H"

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
