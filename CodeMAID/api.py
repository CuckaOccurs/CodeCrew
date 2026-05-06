# CodeMOP — Ollama API Bridge
# Handles health checks, model management,
# chat requests, GPU status, session logging.
# Never crashes — always falls back.

import httpx
import json
import logging
from datetime import datetime
from codemop import (
    APP_ROOT,
    load_config,
)

from codemop.guard import SyntaxGuard

log = logging.getLogger("codemop.api")


class OllamaAPI:
    """
    Bridge between CodeMOP and Ollama.
    """

    def __init__(self):
        self.config = load_config()
        self.ollama = self.config.get("ollama", {})
        self.base_url = self.ollama.get(
            "url", "http://localhost:11434")
        self.timeout = self.ollama.get(
            "timeout", 120)
        self.guard = SyntaxGuard()
        self._gpu_cache = None
        self._gpu_cache_time = None

    # ── Health ────────────────────────────────────────
    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception as e:
            log.warning(
                f"Ollama not reachable: {e}")
            return False

    async def status(self) -> dict:
        running = await self.health_check()
        models = (await self.available_models()
                  if running else [])
        gpu = (await self.gpu_status()
               if running else {})
        return {
            "running": running,
            "url": self.base_url,
            "models": models,
            "gpu": gpu,
            "checked_at": (
                datetime.now().isoformat())
        }

    # ── Models ────────────────────────────────────────
    async def available_models(self) -> list:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                data = r.json()
                models = []
                for m in data.get("models", []):
                    models.append({
                        "name": m.get("name"),
                        "size": m.get("size"),
                        "modified": m.get(
                            "modified_at"),
                        "details": m.get(
                            "details", {})
                    })
                return models
        except Exception as e:
            log.warning(
                f"Could not fetch models: {e}")
            return []

    async def ensure_model(self, model: str) -> str:
        """
        Check model is available.
        Attempt pull if not.
        Fall back if pull fails.
        """
        available = [
            m["name"] for m in
            await self.available_models()]

        if model in available:
            return model

        log.info(
            f"Model {model} not found "
            f"— attempting pull")

        if await self._pull_model(model):
            return model

        fallback = self.ollama.get(
            "fallback_model", "llama3")
        log.warning(
            f"Pull failed — falling back "
            f"to {fallback}")
        return fallback

    async def _pull_model(self, model: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/pull",
                    json={"name": model}
                ) as r:
                    async for line in r.aiter_lines():
                        if line:
                            data = json.loads(line)
                            status = data.get(
                                "status", "")
                            log.info(f"Pull: {status}")
                            if status == "success":
                                return True
            return False
        except Exception as e:
            log.warning(f"Pull failed: {e}")
            return False

    async def list_running_models(self) -> list:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/api/ps")
                data = r.json()
                return [
                    m.get("name")
                    for m in data.get("models", [])
                ]
        except Exception as e:
            log.warning(f"Could not fetch running models: {e}")
            return []

    async def unload_model(self, model: str) -> bool:
        """
        Unload model from VRAM.
        Useful when switching between
        large models on limited VRAM.
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "keep_alive": 0
                    })
            log.info(f"Unloaded: {model}")
            return True
        except Exception as e:
            log.warning(
                f"Could not unload "
                f"{model}: {e}")
            return False

    # ── GPU ───────────────────────────────────────────
    async def gpu_status(self) -> dict:
        # Return cache if fresh (60 seconds)
        if self._gpu_cache is not None and self._gpu_cache_time:
            elapsed = (datetime.now() - self._gpu_cache_time).total_seconds()
            if elapsed < 60:
                return self._gpu_cache

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/api/ps")
                data = r.json()
                gpus = {}
                for m in data.get("models", []):
                    gpus[m.get("name")] = {
                        "vram_used": m.get(
                            "size_vram"),
                        "model": m.get("name")
                    }
                
                self._gpu_cache = gpus
                self._gpu_cache_time = datetime.now()
                return gpus
        except Exception as e:
            log.debug(f"API GPU status failed, falling back to smi: {e}")
            smi_data = self._nvidia_smi_status()
            self._gpu_cache = smi_data
            self._gpu_cache_time = datetime.now()
            return smi_data

    def _nvidia_smi_status(self) -> dict:
        import subprocess
        try:
            result = subprocess.run([
                "nvidia-smi",
                "--query-gpu="
                "index,name,memory.used,"
                "memory.total,"
                "temperature.gpu,"
                "utilization.gpu",
                "--format=csv,noheader,nounits"
            ], capture_output=True, text=True)

            gpus = {}
            for line in (result.stdout
                               .strip()
                               .split("\n")):
                if not line.strip():
                    continue
                parts = [
                    p.strip()
                    for p in line.split(",")]
                if len(parts) >= 6:
                    idx = parts[0]
                    gpus[idx] = {
                        "index": idx,
                        "name": parts[1],
                        "vram_used_mb": int(
                            parts[2]),
                        "vram_total_mb": int(
                            parts[3]),
                        "temp_c": int(parts[4]),
                        "utilization_pct": int(
                            parts[5])
                    }
            return gpus
        except Exception as e:
            log.warning(f"nvidia-smi check failed: {e}")
            return {}

    # ── Vault ─────────────────────────────────────────
    def _vault_guard(self, context: dict, message: str) -> bool:
        """
        Check if the message/action is allowed in the current vault mode.
        Safe: Read only. No disk modification.
        Cage: Project folder only. Safe commands.
        Free: Full access.
        """
        vault = context.get("vault", "safe").lower()
        cwd = context.get("cwd")
        is_allowed, reason = self.guard.check_message(message, vault, cwd)
        
        if not is_allowed:
            log.warning(f"Vault [{vault}] blocked action: {reason}")
            return False, reason
            
        return True, ""

    # ── Chat ──────────────────────────────────────────
    async def chat(self,
             context: dict,
             message: str,
             stream: bool = True) -> str:
        """
        Send assembled context as system prompt
        and user message to Ollama.
        Returns full response string.
        """
        allowed, reason = self._vault_guard(context, message)
        if not allowed:
            return f"Action blocked by Vault: {reason}"

        model = await self.ensure_model(
            context.get("model", "llama3"))

        system_prompt = (
            self._build_system_prompt(context))

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            "stream": stream,
            "options": {
                "num_ctx": context.get(
                    "min_context", 4096)
            }
        }

        log.info(
            f"Chat initiated",
            extra={"model": model, "project": context.get("project")}
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                full_response = ""

                if stream:
                    async with client.stream(
                        "POST", f"{self.base_url}/api/chat",
                        json=payload
                    ) as r:
                        async for line in r.aiter_lines():
                            if line:
                                data = json.loads(line)
                                chunk = (
                                    data.get("message", {})
                                        .get("content", ""))
                                full_response += chunk
                                if data.get("done"):
                                    break
                else:
                    r = await client.post(
                        f"{self.base_url}/api/chat",
                        json=payload)
                    data = r.json()
                    full_response = (
                        data.get("message", {})
                            .get("content", ""))

                self._log_exchange(
                    context, message, full_response)

                return full_response

        except Exception as e:
            log.error(
                f"Chat request failed: {e}")
            return (
                f"Error communicating "
                f"with Ollama: {e}")

    async def stream_chat(self,
                    context: dict,
                    message: str):
        """
        Generator version of chat.
        Yields chunks as they arrive.
        For use in CodeMaid live UI.
        """
        allowed, reason = self._vault_guard(context, message)
        if not allowed:
            yield f"Action blocked by Vault: {reason}"
            return

        model = await self.ensure_model(
            context.get("model", "llama3"))

        system_prompt = (
            self._build_system_prompt(context))

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            "stream": True,
            "options": {
                "num_ctx": context.get(
                    "min_context", 4096)
            }
        }

        full_response = ""

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat",
                    json=payload
                ) as r:
                    async for line in r.aiter_lines():
                        if line:
                            data = json.loads(line)
                            chunk = (
                                data.get("message", {})
                                    .get("content", ""))
                            full_response += chunk
                            yield chunk
                            if data.get("done"):
                                break

            self._log_exchange(
                context, message, full_response)

        except Exception as e:
            log.error(
                f"Stream chat failed: {e}")
            yield f"Error: {e}"

    # ── System prompt ─────────────────────────────────
    def _build_system_prompt(self,
                              context: dict
                              ) -> str:
        instructions = context.get(
            "instructions", "")

        decisions = context.get("decisions", [])
        if decisions:
            lines = [
                f"- {d['decision']}"
                for d in decisions]
            decision_text = "\n".join(lines)
        else:
            decision_text = (
                "No prior decisions recorded.")

        prompt = instructions.replace(
            "{decisions}", decision_text)

        prompt += (
            f"\n\n---\n\n"
            f"## Current Session\n"
            f"Project: {context.get('project')}\n"
            f"Directory: {context.get('cwd')}\n"
            f"Model: {context.get('model')}\n"
            f"Profile: {context.get('profile')}\n"
        )

        log.debug(
            f"System prompt: "
            f"{len(prompt)} chars")
        return prompt

    # ── Session logging ───────────────────────────────
    def _log_exchange(self,
                      context: dict,
                      message: str,
                      response: str):
        """
        Write exchange to JSONL session log.
        One file per day per project.
        """
        session_dir = Path(
            context.get(
                "session_dir",
                str(APP_ROOT / "sessions" /
                    "unknown")))
        session_dir.mkdir(
            parents=True, exist_ok=True)

        today = datetime.now().strftime(
            "%Y-%m-%d")
        log_file = (session_dir /
                    f"{today}_session.jsonl")

        exchange = {
            "timestamp": (
                datetime.now().isoformat()),
            "project": context.get("project"),
            "model": context.get("model"),
            "profile": context.get("profile"),
            "personas": context.get(
                "personas", []),
            "message": message,
            "response": response,
            "cwd": context.get("cwd")
        }

        try:
            with open(log_file, 'a') as f:
                f.write(
                    json.dumps(exchange) + "\n")
        except Exception as e:
            log.warning(
                f"Could not log exchange: {e}")

    async def branch(self, parent_id: str, content: str) -> dict:
        """
        Branch an existing conversation from a parent message.
        """
        # Logic to look up conversation state by parent_id
        # and initiate new completion flow.
        return {"status": "forked", "parent_id": parent_id, "new_message_id": "..."}
