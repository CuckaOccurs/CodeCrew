#!/usr/bin/env python3
"""
CODEMAID Prompt Review — Kitty overlay for reviewing flagged prompts.
Usage: python3 prompt_review.py /tmp/codemaid_review_xxx.json
"""
import json
import os
import sys
import termios
import tty

_R = "\033[38;2;210;20;20m"
_Y = "\033[38;2;240;180;41m"
_A = "\033[38;2;80;140;220m"
_P = "\033[38;2;150;50;210m"
_K = "\033[38;2;220;50;130m"
_M = "\033[38;2;110;110;110m"
_T = "\033[38;2;170;170;170m"
_D = "\033[38;2;55;60;85m"
_Z = "\033[0m"
_B = "\033[1m"

_TYPE_COLOR = {
    "contradiction":      _R,
    "ambiguous":          _Y,
    "hallucination_risk": _R,
    "complex":            _Y,
    "destructive":        _R,
}

_TYPE_ICON = {
    "contradiction":      "✕",
    "ambiguous":          "?",
    "hallucination_risk": "⚠",
    "complex":            "⋯",
    "destructive":        "✕",
}


def _hr(w=62):
    return f"  {_D}{'─' * w}{_Z}\n"


def _render(prompt, issues, cleaned):
    w = 62
    out = "\033[2J\033[H"
    out += f"\n  {_R}{_B}⚠  Prompt Guard{_Z}\n"
    out += _hr(w)

    out += f"\n  {_M}prompt{_Z}\n"
    for line in prompt[:500].splitlines():
        out += f"  {_T}{line[:w]}{_Z}\n"
    out += "\n"

    out += f"  {_Y}issues{_Z}\n"
    for issue in issues:
        col  = _TYPE_COLOR.get(issue["type"], _Y)
        icon = _TYPE_ICON.get(issue["type"], "▸")
        out += f"  {col}{icon}  {issue['description']}{_Z}\n"
        if issue.get("span"):
            out += f"     {_D}'{issue['span']}'{_Z}\n"
    out += "\n"

    if cleaned:
        out += _hr(w)
        out += f"  {_A}cleaned version{_Z}\n"
        for line in cleaned[:500].splitlines():
            out += f"  {_T}{line[:w]}{_Z}\n"
        out += "\n"

    out += _hr(w)
    if cleaned:
        out += (f"  {_A}s{_Z}{_M}end as-is  "
                f"{_A}c{_Z}{_M}lean+send  "
                f"{_A}e{_Z}{_M}dit  "
                f"{_A}x{_Z}{_M}cancel{_Z}\n\n")
    else:
        out += (f"  {_A}s{_Z}{_M}end as-is  "
                f"{_A}e{_Z}{_M}dit  "
                f"{_A}x{_Z}{_M}cancel{_Z}\n\n")
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    path = sys.argv[1]
    with open(path) as f:
        data = json.load(f)

    prompt  = data["prompt"]
    issues  = data["issues"]
    cleaned = data.get("cleaned", "")

    sys.stdout.write(_render(prompt, issues, cleaned))
    sys.stdout.flush()

    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    result = {"action": "cancel", "prompt": prompt}

    try:
        tty.setcbreak(fd)
        while True:
            ch = sys.stdin.read(1).lower()

            if ch == "s":
                result = {"action": "send", "prompt": prompt}
                break

            elif ch == "c" and cleaned:
                result = {"action": "send", "prompt": cleaned}
                break

            elif ch == "e":
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
                sys.stdout.write(f"\n  {_A}edit (ctrl+d to finish):{_Z}\n")
                sys.stdout.flush()
                lines = []
                try:
                    while True:
                        line = input("  ")
                        lines.append(line)
                except EOFError:
                    pass
                edited = "\n".join(lines).strip() or prompt
                result = {"action": "send", "prompt": edited}
                break

            elif ch in ("x", "q", "\x1b"):
                result = {"action": "cancel", "prompt": prompt}
                break

    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            pass

    with open(path, "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()
