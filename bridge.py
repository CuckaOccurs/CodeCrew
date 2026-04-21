"""
CodeCrew Web-Maid Bridge
Exposes a minimal API for the WebUI to communicate with the CodeCrew IDE Engine.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import os

app = FastAPI()

class Command(BaseModel):
    action: str
    payload: dict

# This acts as the gateway to the CodeCrew IDE Engine
# We use the existing codemaid engine directly.
@app.post("/execute")
async def execute(cmd: Command):
    # Only allow validated actions (audit, execute, status)
    if cmd.action not in ["audit", "execute", "status"]:
        raise HTTPException(status_code=403, detail="Unauthorized action")
    
    # In a real impl, this would pipe to the running CodeCrew engine process
    # For now, we simulate the execution flow
    return {"status": "success", "message": f"Forwarding {cmd.action} to CodeCrew IDE..."}

@app.get("/status")
async def status():
    # Bridge to the MOP heartbeat
    return {"network": "GREEN", "active_tasks": []}
