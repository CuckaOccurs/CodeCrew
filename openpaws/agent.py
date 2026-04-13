"""
OpenPaws Agent — The brain with hands (Tool Use Loop).
"""
import json
from openpaws.tools import TOOLS, execute_tool

SYSTEM_PROMPT = """You are OpenPaws, an expert AI coding assistant.

Your goal is to help the user with coding tasks: reading, writing, editing files, and running commands.

You have access to the following tools:
1. read_file: Read a file's contents. ALWAYS use this before editing.
2. write_file: Create or overwrite a file with full content.
3. edit_file: Apply a specific SEARCH/REPLACE block to a file. (Only for small changes).
4. focus: Deep-search the entire codebase for a pattern.
5. grep: Search for a pattern in files (Ctrl+F for the codebase).
6. run_command: Run a shell command (e.g., python test.py).
7. web_search: Search the web for current information.
8. web_scrape: Fetch and read the text content of a URL.
9. read_document: Read PDF, Word, or Excel files.
10. diff_preview: Show a diff of the last edit made to a file.
11. undo_edit: Restore a file from its last backup.
12. read_multiple: Read multiple files in one call.
13. list_dir: List files and directories with types and sizes.

Guidelines:
- Be concise.
- Always read a file before editing it.
- Use edit_file for small fixes. Use write_file for creating new files or major rewrites.
- If you need to run a test or script, use run_command.
- If the user asks a general question, answer it directly without tools."""


class Agent:
    MAX_ITERATIONS = 20

    def __init__(self, provider, work_dir):
        self.provider = provider
        self.work_dir = work_dir
        self.history = []
        self.trace = False

    def chat(self, user_message):
        """Send a message, handle tool calls, return the final text response."""
        self.history.append({"role": "user", "content": user_message})
        iterations = 0
        seen_actions = []
        recent_responses = []

        while iterations < self.MAX_ITERATIONS:
            iterations += 1
            response = self.provider.chat(self.history, tools=TOOLS)

            if self.trace:
                self._print_trace("→ LLM response", json.dumps(response, indent=2)[:2000])

            if "tool_calls" in response and response["tool_calls"]:
                self.history.append(response)

                for call in response["tool_calls"]:
                    function = call.get("function", {})
                    name = function.get("name")
                    arguments = function.get("arguments", "{}")

                    action_key = f"{name}:{arguments}"
                    if action_key in seen_actions:
                        return "⚠️ I seem to be stuck in a loop trying to " + name + ". Let me try a different approach."

                    seen_actions.append(action_key)
                    if len(seen_actions) > 5:
                        seen_actions.pop(0)

                    if self.trace:
                        self._print_trace(f"→ tool call: {name}", arguments[:500])

                    try:
                        args = json.loads(arguments) if isinstance(arguments, str) else arguments
                    except (json.JSONDecodeError, TypeError):
                        args = {}

                    result = execute_tool(name, args, self.work_dir)

                    if self.trace:
                        result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                        self._print_trace(f"← tool result: {name}", result_str[:2000])

                    self.history.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", "unknown"),
                        "content": json.dumps(result) if isinstance(result, dict) else str(result),
                    })
                continue
            else:
                final_text = response.get("content", "")
                stripped = final_text.strip()

                # Detect repeated empty/useless responses
                if stripped in ("", "..."):
                    recent_responses.append(stripped)
                    if len(recent_responses) >= 3:
                        self.history.append({
                            "role": "assistant",
                            "content": "⚠️ I'm having trouble getting a response from the model. Please try again."
                        })
                        return "⚠️ Model is not responding. Try again."
                else:
                    recent_responses.clear()

                self.history.append({"role": "assistant", "content": final_text})
                return final_text

        warning = "⚠️ I've reached my limit for tool calls without a clear answer. Could you clarify what you're looking for?"
        self.history.append({"role": "assistant", "content": warning})
        return warning

    def _print_trace(self, label, content):
        """Print trace output in a readable format."""
        from rich.panel import Panel
        from rich.console import Console
        c = Console()
        c.print(Panel(f"[dim]{content}[/dim]", title=label, border_style="dim"))
