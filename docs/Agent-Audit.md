This script (codemain.py) appears to be the main entry point and CLI interface for a project called CODEMAID. It is a
custom-written terminal application that acts as a wrapper for an AI agent, allowing interaction via the command line with
advanced features like safety checks, dual operating modes, and raw terminal rendering.

Here is a breakdown of how the script functions:

### 1. Core Architecture

It runs on a single-threaded event loop. Instead of using a standard input() prompt, it uses sys.stdin.read(1) in a while
True loop to listen for raw ASCII characters one by one. This allows for immediate interception and handling of special
keys (like ESC, TAB, Ctrl+S) without blocking the program.

### 2. Key Features

- Event Loop / Event Handling:
- TAB: Toggles between Chat Mode (sending text to the AI) and Shell Mode (executing raw terminal commands).
- ^S (Ctrl+S): Toggles Sudo Mode. This is a safety feature. If enabled, dangerous commands (identified by a regex
pattern in _on_confirm) are executed without requiring explicit authorization (or perhaps bypassing the prompt).
- ^D (Ctrl+D): Toggles Dry Run Mode (a simulation mode).
- ESC: An interrupt signal. If the AI is "thinking" (is_thinking flag is true), ESC sends an interrupt to stop the
generation.
- Safety (_on_confirm):
- The script uses a regex pattern to detect dangerous commands (e.g., rm, dd, mkfs, eval).
- If a dangerous command is attempted without Sudo mode being active, the program pauses, displays a "🔒 ELEVATED
PRIVILEGES REQUIRED" modal, and waits for user confirmation before running the command.
- UI/Rendering:
- It uses a custom drawing function (_draw) that uses ANSI escape codes to manipulate the terminal cursor (saving
position, clearing lines, and scrolling).
- It implements a status bar showing the current mode (SHELL vs CHAT), Vault status, and the active LLM model name.
- Logging:
- It imports session_tools to log inputs, outputs, tool calls, and tool results during the session.
- Dual Mode Execution:
- Chat Mode: Sends inputs to the agent.chat() function (implied internal class handling LLM interactions).
- Shell Mode: Bypasses the AI and uses subprocess.run() to execute the user's input as a system shell command.

### 3. Technical Components Used

- termios: Used to set the terminal to raw mode (tty.setcbreak) for character-by-character reading and restoring settings
on exit.
- select: Used to check for input readiness efficiently with a low timeout (0.05s) to avoid freezing the UI during idle
states.
- sys.stdout: Directly writes ANSI escape codes for styling and UI updates.

### Summary

This is a sophisticated, manual terminal interface. It prioritizes control and safety over convenience, offering features
like explicit confirmation for destructive commands and low-level input handling to support complex key bindings (like
toggling modes) standard input() functions cannot provide.

