"""
CODEMAID Agent — The brain with hands (Tool Use Loop).
"""
import json
import time
import concurrent.futures
from collections.abc import Callable
from pathlib import Path
from typing import Any

from codemaid.tools import TOOLS, execute_tool

DEFAULT_CONTEXT_TOKEN_LIMIT = 24_000
MIN_TOOL_DELAY = 0.05
CHARS_PER_TOKEN = 4

class Agent:
    _trace_console = None

    def __init__(
        self,
        provider: Any,
        work_dir: str | Path,
        system_prompt: str | None = None,
        context_token_limit: int | None = None,
        trace_callback: Callable[[str, str], None] | None = None,
        max_iterations: int = 20,
        tool_limits: dict[str, int] | None = None,
        summary_keep_turns: int = 6,
    ) -> None:
        self.provider = provider
        self.work_dir = work_dir
        self.history = []
        self.trace = False
        self.system_prompt = system_prompt
        self.context_token_limit = context_token_limit or DEFAULT_CONTEXT_TOKEN_LIMIT
        self.MAX_ITERATIONS = max_iterations
        self._tool_limits = tool_limits or {}
        self._tool_call_counts: dict[str, int] = {}
        self.plan_mode = False
        self.auto_commit = False
        self.vault_on = True
        self.vault_allowlist = False
        self.sudo_mode = False
        self.dry_run = False
        self.checkpoints: dict[str, list] = {}
        self._checkpoint_order: list[str] = []
        self.trace_callback = trace_callback
        self._auto_compact_threshold = 0.80
        self._summary_keep_turns = summary_keep_turns
        self._turn_count = 0

    def _estimate_tokens(self, text: str | None) -> int:
        if not text: return 0
        return len(text) // CHARS_PER_TOKEN

    def _estimate_messages_tokens(self, messages: list[dict]) -> int:
        total = 0
        for m in messages:
            total += self._estimate_tokens(str(m.get("content", "")))
            if "tool_calls" in m:
                total += self._estimate_tokens(json.dumps(m["tool_calls"]))
        return total

    def _summarize_turns(self, turns: list[dict]) -> str:
        """Ask the LLM to summarize old turns into compact bullet points."""
        lines = []
        for m in turns:
            role = m.get("role", "")
            content = str(m.get("content") or "")
            if role == "tool" and len(content) > 300:
                content = content[:300] + "…"
            if role in ("user", "assistant") or (role == "tool" and content.strip()):
                lines.append(f"{role.upper()}: {content[:400]}")
        text = "\n".join(lines)
        if not text.strip():
            return ""
        try:
            summary_messages = [
                {"role": "system", "content": "You are a concise context summarizer. Reply only with bullet points."},
                {"role": "user",   "content": (
                    "Summarize this conversation in 4-6 bullet points covering: "
                    "decisions made, files changed, current task state, key findings. "
                    "Be terse — this replaces the raw history to save context.\n\n" + text
                )},
            ]
            return self.provider.chat(summary_messages)
        except Exception:
            return "[summary unavailable]"

    def _maybe_compact(self) -> None:
        """Replace old turns with a summary when history grows past threshold."""
        token_limit      = self.context_token_limit
        compact_threshold = int(token_limit * self._auto_compact_threshold)
        keep             = self._summary_keep_turns

        if self._estimate_messages_tokens(self.history) <= compact_threshold:
            return
        if len(self.history) <= keep:
            return

        old_turns    = self.history[:-keep]
        recent_turns = self.history[-keep:]

        summary_text = self._summarize_turns(old_turns)
        if summary_text:
            summary_msg = {"role": "assistant", "content": f"[Session Summary]\n{summary_text}"}
            self.history = [summary_msg] + recent_turns
        else:
            self.history = recent_turns

    def _build_request_messages(self) -> list[dict[str, Any]]:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        dynamic = self.history[:]

        # Trim oversized tool outputs as a last resort
        for i, m in enumerate(dynamic):
            if m.get("role") == "tool":
                content = m.get("content", "")
                if len(content) > 800:
                    new_m = dict(m)
                    new_m["content"] = content[:800] + "…[trimmed]"
                    dynamic[i] = new_m

        messages.extend(dynamic)
        return messages

    def chat(
        self,
        user_message: str,
        on_tool_call: Callable[[str, dict], None] | None = None,
        on_tool_result: Callable[[str, Any], None] | None = None,
        on_confirm: Callable[[str, dict], bool] | None = None,
        on_chunk: Callable[[str], None] | None = None,
    ) -> str:
        self.history.append({"role": "user", "content": user_message})
        self._maybe_compact()
        iterations = 0
        seen_actions = []
        recent_responses = []

        self._tool_call_counts = {}
        while iterations < self.MAX_ITERATIONS:
            iterations += 1
            request_messages = self._build_request_messages()

            use_stream = on_chunk is not None and hasattr(self.provider, "chat_stream")
            if use_stream:
                response = self.provider.chat_stream(request_messages, tools=TOOLS, on_chunk=on_chunk)
            else:
                response = self.provider.chat(request_messages, tools=TOOLS)

            if self.trace:
                self._print_trace("→ LLM response", json.dumps(response, indent=2)[:2000])

            if "tool_calls" in response and response["tool_calls"]:
                self.history.append(response)
                tool_calls_to_run = []
                for call in response["tool_calls"]:
                    name = call.get("function", {}).get("name")
                    arguments = call.get("function", {}).get("arguments", "{}")
                    
                    action_key = f"{name}:{arguments}"
                    if action_key in seen_actions:
                        return "⚠️ I seem to be stuck in a loop. Let me try a different approach."
                    seen_actions.append(action_key)
                    if len(seen_actions) > 5: seen_actions.pop(0)

                    try:
                        args = json.loads(arguments) if isinstance(arguments, str) else arguments
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    tool_calls_to_run.append((call, name, args))

                if on_confirm:
                    confirmed = []
                    for item in tool_calls_to_run:
                        call, name, args = item
                        if not on_confirm(name, args):
                            self.history.append({
                                "role": "tool",
                                "tool_call_id": call.get("id", "unknown"),
                                "content": json.dumps({"error": f"User cancelled: {name}"}),
                            })
                        else:
                            confirmed.append(item)
                    tool_calls_to_run = confirmed
                    if not tool_calls_to_run: continue

                tool_results = []
                if len(tool_calls_to_run) > 1:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tool_calls_to_run)) as executor:
                        future_to_call = {}
                        for call, name, args in tool_calls_to_run:
                            limit = self._tool_limits.get(name)
                            if limit and self._tool_call_counts.get(name, 0) >= limit:
                                tool_results.append((call, name, {"error": f"rate limit reached for {name} ({limit}/session)"}))
                                continue
                            self._tool_call_counts[name] = self._tool_call_counts.get(name, 0) + 1
                            if on_tool_call: on_tool_call(name, args)
                            if self.trace: self._print_trace(f"→ tool call: {name}", json.dumps(args)[:500])

                            future = executor.submit(execute_tool, name, args, self.work_dir,
                                                     vault_on=self.vault_on,
                                                     vault_allowlist=self.vault_allowlist,
                                                     sudo_mode=self.sudo_mode,
                                                     dry_run=self.dry_run)
                            future_to_call[future] = (call, name)
                        
                        for future in concurrent.futures.as_completed(future_to_call):
                            call, name = future_to_call[future]
                            result = future.result()
                            if on_tool_result: on_tool_result(name, result)
                            tool_results.append((call, name, result))
                            if self.trace:
                                self._print_trace(f"← tool result: {name}", json.dumps(result)[:2000])
                else:
                    for call, name, args in tool_calls_to_run:
                        limit = self._tool_limits.get(name)
                        if limit and self._tool_call_counts.get(name, 0) >= limit:
                            tool_results.append((call, name, {"error": f"rate limit reached for {name} ({limit}/session)"}))
                            continue
                        self._tool_call_counts[name] = self._tool_call_counts.get(name, 0) + 1
                        if on_tool_call: on_tool_call(name, args)
                        if self.trace: self._print_trace(f"→ tool call: {name}", json.dumps(args)[:500])

                        result = execute_tool(name, args, self.work_dir,
                                              vault_on=self.vault_on,
                                              vault_allowlist=self.vault_allowlist,
                                              sudo_mode=self.sudo_mode,
                                              dry_run=self.dry_run)
                        
                        if on_tool_result: on_tool_result(name, result)
                        tool_results.append((call, name, result))
                        if self.trace:
                            self._print_trace(f"← tool result: {name}", json.dumps(result)[:2000])

                for call, name, result in tool_results:
                    if self.auto_commit and name in ("write_file", "edit_file") and "message" in result:
                        file_path = args.get("path", "unknown")
                        commit_result = self._auto_commit_file(file_path)
                        if commit_result: result["auto_commit"] = commit_result

                    self.history.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", "unknown"),
                        "name": name,
                        "content": json.dumps(result) if isinstance(result, dict) else str(result),
                    })
                    time.sleep(MIN_TOOL_DELAY)
                continue
            else:
                final_text = response.get("content", "")
                if not final_text.strip() or final_text.strip() == "...":
                    recent_responses.append(final_text)
                    if len(recent_responses) >= 3:
                        msg = "⚠️ Model is unresponsive. Try a manual search or a more specific prompt."
                        self.history.append({"role": "assistant", "content": msg}); return msg
                    continue
                else: recent_responses.clear()

                self.history.append({"role": "assistant", "content": final_text})
                self._turn_count += 1
                return final_text

        return "⚠️ Tool call limit reached. Please clarify."

    def rewind(self, n: int = 1) -> int:
        removed = 0
        for _ in range(n):
            idx = next((i for i in range(len(self.history)-1, -1, -1) if self.history[i]["role"] == "user"), None)
            if idx is None: break
            removed += len(self.history) - idx
            self.history = self.history[:idx]
        return removed

    def checkpoint(self, name: str | None = None) -> str:
        import copy
        if not name: name = f"cp{len(self._checkpoint_order) + 1}"
        self.checkpoints[name] = copy.deepcopy(self.history)
        if name not in self._checkpoint_order: self._checkpoint_order.append(name)
        return name

    def restore_checkpoint(self, name_or_index: str | int | None = None) -> tuple[bool, str]:
        if not self.checkpoints: return False, "No checkpoints."
        import copy
        if name_or_index is None: name = self._checkpoint_order[-1]
        elif isinstance(name_or_index, int):
            idx = name_or_index - 1
            if idx < 0 or idx >= len(self._checkpoint_order): return False, "Index out of range."
            name = self._checkpoint_order[idx]
        else: name = name_or_index
        if name not in self.checkpoints: return False, f"No checkpoint '{name}'."
        self.history = copy.deepcopy(self.checkpoints[name])
        return True, f"Restored '{name}'"

    def list_checkpoints(self) -> list[str]: return list(self._checkpoint_order)

    def _auto_commit_file(self, file_path: str) -> str | None:
        import subprocess as _sp
        try:
            _sp.run(["git", "add", file_path], capture_output=True, cwd=self.work_dir, timeout=10)
            r = _sp.run(["git", "commit", "-m", f"codemaid: auto-edit {file_path}"], capture_output=True, text=True, cwd=self.work_dir, timeout=10)
            return "✓ Auto-committed" if r.returncode == 0 else None
        except Exception: return None

    def _print_trace(self, label: str, content: str) -> None:
        if self.trace_callback: self.trace_callback(label, content); return
        from rich.panel import Panel
        if Agent._trace_console is None:
            from rich.console import Console
            Agent._trace_console = Console()
        Agent._trace_console.print(Panel(f"[dim]{content}[/dim]", title=label, border_style="dim"))
