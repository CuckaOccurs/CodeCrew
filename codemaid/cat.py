"""CODEMAID terminal display helpers."""

import sys
from rich.console import Console
from pathlib import Path

THEME = {
    "blue":      "#3584e4",
    "dark_blue": "#1a5fb4",
    "purple":    "#9141ac",
    "red":       "#e01b24",
    "yellow":    "#f5c211",
    "pink":      "#ff6b81",
    "white":     "#ffffff",
    "dim":       "#5e5c64",
    "green":     "#26a269",
}

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------
def _c(r, g, b, text, bold=False):
    return f"\033[{'1;' if bold else ''}38;2;{r};{g};{b}m{text}\033[0m"

_W = lambda t: _c(220, 220, 220, t, bold=True)   # white
_U = lambda t: _c( 90,  80, 130, t, bold=True)   # uniform (visible purple-dark)
_A = lambda t: _c(230, 230, 230, t, bold=True)    # apron (bright white)
_R = lambda t: _c(200,  30,  40, t, bold=True)    # red/stern
_G = lambda t: _c( 80,  76, 100, t)               # grey/dim

# ---------------------------------------------------------------------------
# ASCII Maid — frilly cap, apron, arms crossed, not impressed
#
#  _/‾\_/‾\_/‾\_/‾\_      <- frilled maid headpiece (wide, white)
#  ================        <- cap band
#       |    |
#   /‾‾‾‾‾‾‾‾‾‾‾‾\
#  |   ─       ─   |      <- stern eyes
#  |       ▼       |      <- nose
#  |    ───────    |      <- pressed mouth
#   \____________/
#     |  |   |  |         <- collar/neck
#   __|  |   |  |__
#  |     |░░░|     |      <- arms + apron
#  |     |░░░|     |
#  |_____|░░░|_____|
#        |   |
# ---------------------------------------------------------------------------

def _maid():
    # cap — wide frilly headband (the maid identifier)
    frill  = _W("_/") + _W("‾") + _W("\\_/") + _W("‾") + _W("\\_/") + _W("‾") + _W("\\_/") + _W("‾") + _W("\\_")
    band   = _W("==================")
    # face
    ht     = _W("/") + " " * 14 + _W("\\")
    eyes   = _W("|") + "   " + _R("─") + " " * 7 + _R("─") + "   " + _W("|")
    nose   = _W("|") + " " * 7 + _G("v") + " " * 7 + _W("|")
    mth    = _W("|") + "   " + _G("─" * 9) + "   " + _W("|")
    chin   = _W("\\") + _W("_" * 14) + _W("/")           # 16 wide
    # body connects flush to chin (same 16-char width, indent 3)
    shl    = _U("/") + " " * 14 + _U("\\")               # shoulder flare
    a1     = _U("|") + "    " + _W("|") + _A("░░░░░") + _W("|") + "   " + _U("|")
    a2     = _U("|") + "    " + _W("|") + _A("░░░░░") + _W("|") + "   " + _U("|")
    a3     = _U("|") + "    " + _W("|") + _A("░░░░░") + _W("|") + "   " + _U("|")
    hem    = _U("|") + "____" + _W("|") + _W("_____") + _W("|") + "___" + _U("|")
    legs   = " " * 6 + _W("| |") + " " * 7
    feet   = " " * 5 + _W("_| |_") + " " * 6

    return [
        f"  {frill}",
        f"  {band}",
        f"   {ht}",
        f"   {eyes}",
        f"   {nose}",
        f"   {mth}",
        f"   {chin}",
        f"   {shl}",
        f"   {a1}",
        f"   {a2}",
        f"   {a3}",
        f"   {hem}",
        f"   {legs}",
        f"   {feet}",
    ]


def print_maid() -> None:
    BLU = "\033[1;38;2;53;132;228m"
    PUR = "\033[1;38;2;145;65;172m"
    DIM = "\033[38;2;80;76;100m"
    RST = "\033[0m"

    sys.stdout.write("\n")
    for row in _maid():
        sys.stdout.write(f"{row}\n")
    sys.stdout.write("\n")
    sys.stdout.write(f"  {DIM}I'm here to clean up your shit.{RST}\n")
    sys.stdout.write(f"  {DIM}(because you refuse to){RST}\n")
    sys.stdout.write("\n")
    sys.stdout.flush()


def animate_title(seconds: float = 2.0, fps: int = 14) -> None:
    """Scroll a blue→purple→pink→red gradient through CODEMAID."""
    import time

    text   = "CODEMAID"
    n      = len(text)
    stops  = [
        (53,  132, 228),   # blue
        (145,  65, 172),   # purple
        (255, 107, 129),   # pink
        (200,  30,  40),   # red
    ]

    def _lerp(a, b, t):
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

    def _color(pos):
        pos = pos % 1.0
        seg = pos * (len(stops) - 1)
        idx = min(int(seg), len(stops) - 2)
        return _lerp(stops[idx], stops[idx + 1], seg - idx)

    frames = int(seconds * fps)
    delay  = 1.0 / fps

    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    try:
        for frame in range(frames):
            offset = frame / frames
            line   = "\r  "
            for i, ch in enumerate(text):
                r, g, b = _color((i / n) + offset)
                line += f"\033[1;38;2;{r};{g};{b}m{ch}"
            line += "\033[0m"
            sys.stdout.write(line)
            sys.stdout.flush()
            time.sleep(delay)
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.write("\n")
        sys.stdout.flush()


def _is_returning_user() -> bool:
    config_path = Path.home() / ".config" / "codemaid" / "config.json"
    legacy_path = Path.home() / ".config" / "codemaid" / "config.json"
    return config_path.exists() or legacy_path.exists()


def print_banner(console: Console,
                 work_dir: str = "",
                 provider: str = "",
                 model: str = "") -> None:
    """Full maid on first launch, minimal header on return."""
    DIM = "\033[38;2;80;76;100m"
    BLU = "\033[1;38;2;53;132;228m"
    PUR = "\033[1;38;2;145;65;172m"
    RST = "\033[0m"

    if not _is_returning_user():
        print_maid()

    animate_title(seconds=2.0, fps=14)
    sys.stdout.write(f"  {DIM}{provider}  ·  {model}{RST}\n")
    if work_dir:
        sys.stdout.write(f"  {DIM}{work_dir}{RST}\n")
    sys.stdout.write("\n")
    sys.stdout.flush()
