# MAID — My AI Dashboard
# Full MOP manager. FastAPI + htmx.
# Personas, Instructions, Profiles, Models, Sessions, Config.

import uvicorn
import yaml
import json
import subprocess
import requests
import frontmatter
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime
import logging

from codemop import (
    APP_ROOT,
    PERSONAS_DIR,
    PROFILES_DIR,
    CONFIG_PATH,
    load_config,
    log,
)

from codemop.api import OllamaAPI

# ── Setup ─────────────────────────────────────────────
app = FastAPI(title="MAID")
templates = Jinja2Templates(
    directory=str(Path(__file__).parent / "templates"))

INSTRUCTIONS_DIR = APP_ROOT / "instructions"
INSTRUCTIONS_DIR.mkdir(parents=True, exist_ok=True)

engine = OllamaAPI()

# ── Persona helpers ───────────────────────────────────

def load_all_personas() -> list:
    personas = []
    if PERSONAS_DIR.exists():
        for f in sorted(PERSONAS_DIR.glob("*.md")):
            if f.suffix == ".bak":
                continue
            try:
                post = frontmatter.load(str(f))
                meta = dict(post.metadata)
                meta["id"] = f.stem
                meta["body"] = post.content
                personas.append(meta)
            except Exception as e:
                log.warning(f"Could not load {f}: {e}")
    return personas

def load_persona(pid: str) -> dict:
    path = PERSONAS_DIR / f"{pid}.md"
    if not path.exists():
        return {}
    post = frontmatter.load(str(path))
    meta = dict(post.metadata)
    meta["id"] = pid
    meta["body"] = post.content
    return meta

def save_persona(pid: str, data: dict) -> bool:
    path = PERSONAS_DIR / f"{pid}.md"
    if path.exists():
        (PERSONAS_DIR / f"{pid}.md.bak").write_text(path.read_text())
    try:
        body = data.pop("body", "")
        post = frontmatter.Post(body, **data)
        path.write_text(frontmatter.dumps(post))
        return True
    except Exception as e:
        log.error(f"Save persona failed: {e}")
        return False

# ── Instruction helpers ───────────────────────────────

def load_all_instructions() -> list:
    instrs = []
    if INSTRUCTIONS_DIR.exists():
        for f in sorted(INSTRUCTIONS_DIR.glob("*.md")):
            instrs.append({
                "id": f.stem,
                "body": f.read_text(errors="replace"),
            })
    return instrs

def save_instruction(iid: str, body: str) -> bool:
    path = INSTRUCTIONS_DIR / f"{iid}.md"
    if path.exists():
        (INSTRUCTIONS_DIR / f"{iid}.md.bak").write_text(path.read_text())
    try:
        path.write_text(body)
        return True
    except Exception as e:
        log.error(f"Save instruction failed: {e}")
        return False

# ── Profile helpers ───────────────────────────────────

def load_all_profiles() -> list:
    profiles = []
    if PROFILES_DIR.exists():
        for f in sorted(list(PROFILES_DIR.glob("*.md")) + list(PROFILES_DIR.glob("*.yaml"))):
            try:
                if f.suffix == ".yaml":
                    with open(f) as fh:
                        data = yaml.safe_load(fh)
                    data["id"] = f.stem
                    data["format"] = "yaml"
                else:
                    post = frontmatter.load(str(f))
                    data = dict(post.metadata)
                    data["id"] = f.stem
                    data["body"] = post.content
                    data["format"] = "md"
                profiles.append(data)
            except Exception as e:
                log.warning(f"Could not load profile {f}: {e}")
    return profiles

# ── Status API ────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    status = await engine.status()
    return {
        "ollama": status["running"],
        "models": status["models"],
        "running": await engine.list_running_models(),
        "gpu": status["gpu"],
        "personas": len(load_all_personas()),
        "instructions": len(load_all_instructions()),
        "profiles": len(load_all_profiles()),
        "checked_at": status["checked_at"],
    }

# ── Persona API ───────────────────────────────────────

@app.get("/api/personas")
async def api_personas():
    return load_all_personas()

@app.get("/api/personas/{pid}")
async def api_persona_get(pid: str):
    p = load_persona(pid)
    if not p:
        raise HTTPException(404, "Not found")
    return p

@app.post("/api/personas/{pid}")
async def api_persona_save(pid: str, request: Request):
    data = await request.json()
    if save_persona(pid, data):
        return {"ok": True}
    raise HTTPException(500, "Save failed")

@app.post("/api/personas/new")
async def api_persona_new(request: Request):
    data = await request.json()
    pid = data.get("id", "").strip().lower().replace(" ", "-")
    if not pid:
        raise HTTPException(400, "id required")
    path = PERSONAS_DIR / f"{pid}.md"
    if path.exists():
        raise HTTPException(409, "Already exists")
    if save_persona(pid, data):
        return {"ok": True, "id": pid}
    raise HTTPException(500, "Save failed")

@app.delete("/api/personas/{pid}")
async def api_persona_delete(pid: str):
    path = PERSONAS_DIR / f"{pid}.md"
    if not path.exists():
        raise HTTPException(404, "Not found")
    archive = APP_ROOT / "Please Delete Me... Let Me Go..."
    archive.mkdir(parents=True, exist_ok=True)
    path.rename(archive / f"{pid}.md")
    return {"ok": True}

# ── Instruction API ───────────────────────────────────

@app.get("/api/instructions")
async def api_instructions():
    return load_all_instructions()

@app.get("/api/instructions/{iid}")
async def api_instruction_get(iid: str):
    path = INSTRUCTIONS_DIR / f"{iid}.md"
    if not path.exists():
        raise HTTPException(404, "Not found")
    return {"id": iid, "body": path.read_text(errors="replace")}

@app.post("/api/instructions/{iid}")
async def api_instruction_save(iid: str, request: Request):
    data = await request.json()
    if save_instruction(iid, data.get("body", "")):
        return {"ok": True}
    raise HTTPException(500, "Save failed")

@app.post("/api/instructions/new")
async def api_instruction_new(request: Request):
    data = await request.json()
    iid = data.get("id", "").strip().lower().replace(" ", "-")
    if not iid:
        raise HTTPException(400, "id required")
    path = INSTRUCTIONS_DIR / f"{iid}.md"
    if path.exists():
        raise HTTPException(409, "Already exists")
    if save_instruction(iid, data.get("body", f"# {iid}\n")):
        return {"ok": True, "id": iid}
    raise HTTPException(500, "Save failed")

# ── Config API ────────────────────────────────────────

@app.get("/api/config")
async def api_config_get():
    try:
        return load_config()
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/config")
async def api_config_save(request: Request):
    data = await request.json()
    bak = Path(str(CONFIG_PATH) + ".bak")
    bak.write_text(CONFIG_PATH.read_text())
    try:
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Main dashboard ────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={}
    )

# ── Run ───────────────────────────────────────────────

def main():
    config = load_config().get("codemaid", {})
    host = config.get("host", "0.0.0.0")
    port = config.get("port", 8080)
    log.info(f"MAID starting on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()

@app.post("/api/chat/branch")
async def api_chat_branch(request: Request):
    data = await request.json()
    parent_id = data.get("parent_id")
    content = data.get("content")
    
    # Branch via engine
    result = await engine.branch(parent_id, content)
    return result
