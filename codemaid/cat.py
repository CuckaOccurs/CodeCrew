"""Minimal banner for CodeMAID Stripped."""

def print_maid() -> None:
    print("\n[ CODEMAID - Stripped Mode ]\n")

def animate_title(seconds: float = 0.1, fps: int = 1) -> None:
    pass

def print_banner(console, work_dir="", provider="", model="") -> None:
    print_maid()
    if work_dir: print(f"  Path: {work_dir}")
    print(f"  AI:   {provider} / {model}\n")
