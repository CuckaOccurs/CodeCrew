"""
CodeCrew Web-Maid Bridge
Exposes a minimal API for the WebUI to communicate with the CodeCrew IDE Engine.
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import subprocess
import os
import json
import uvicorn
from typing import Optional
from datetime import datetime

app = FastAPI()

class ChatRequest(BaseModel):
    text: str
    model: Optional[str] = None
    provider: Optional[str] = None

# Stats tracking for dashboard
STATS = {
    "requests": 0,
    "last_active": "Never",
    "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_content = f"""
    <html>
        <head>
            <title>CodeCrew | AI Server Dashboard</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 0; }}
                .container {{ max-width: 900px; margin: 50px auto; padding: 20px; }}
                .header {{ border-bottom: 1px solid #30363d; padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }}
                h1 {{ color: #58a6ff; margin: 0; font-size: 24px; }}
                .card-grid {{ display: grid; grid-template-columns: repeat(3, 1/3); gap: 20px; }}
                .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 20px; text-align: center; }}
                .card h2 {{ font-size: 14px; color: #8b949e; margin-top: 0; text-transform: uppercase; }}
                .card p {{ font-size: 24px; font-weight: bold; margin: 10px 0 0; color: #f0f6fc; }}
                .status-green {{ color: #3fb950; }}
                .logs {{ margin-top: 40px; background: #010409; border: 1px solid #30363d; border-radius: 6px; padding: 15px; font-family: monospace; height: 300px; overflow-y: auto; }}
                .log-entry {{ margin-bottom: 5px; border-bottom: 1px solid #21262d; padding-bottom: 5px; font-size: 12px; }}
                .footer {{ margin-top: 50px; text-align: center; color: #8b949e; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>CodeCrew AI Server</h1>
                    <div class="status-green">● ONLINE</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px;">
                    <div class="card">
                        <h2>Uptime</h2>
                        <p>{STATS['start_time']}</p>
                    </div>
                    <div class="card">
                        <h2>Total Requests</h2>
                        <p>{STATS['requests']}</p>
                    </div>
                    <div class="card">
                        <h2>Last Active</h2>
                        <p>{STATS['last_active']}</p>
                    </div>
                </div>

                <div class="logs" id="logs">
                    <div class="log-entry">Server initialized and listening on 0.0.0.0:3030...</div>
                    <div class="log-entry">Waiting for connections from 10.0.0.38...</div>
                </div>

                <div class="footer">
                    CodeCrew IDE Engine v4.2.0 | Node: 10.0.0.68
                </div>
            </div>
            <script>
                // Auto-refresh the page every 30 seconds
                setTimeout(() => {{ location.reload(); }}, 30000);
            </script>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/chat")
async def chat(req: ChatRequest):
    STATS["requests"] += 1
    STATS["last_active"] = datetime.now().strftime("%H:%M:%S")

    cmd = ["python3", "-m", "codemaid.main", "rpc"]
...

    if req.model:
        cmd.extend(["--model", req.model])
    if req.provider:
        cmd.extend(["--provider", req.provider])
    
    try:
        # Start the RPC engine
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Send the chat request in JSONL format
        chat_msg = {"id": "web-1", "type": "chat", "text": req.text}
        proc.stdin.write(json.dumps(chat_msg) + "\n")
        proc.stdin.flush()
        
        # Collect response
        full_response = ""
        for line in proc.stdout:
            data = json.loads(line)
            if data.get("type") == "done":
                full_response = data.get("text")
                break
            if data.get("type") == "error":
                raise Exception(data.get("text"))
        
        proc.stdin.close()
        proc.terminate()
        
        return {"status": "success", "response": full_response}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def status():
    return {"network": "GREEN", "server": "10.0.0.68", "client_allowed": "10.0.0.38"}

if __name__ == "__main__":
    # Listen on all interfaces so the other computer can connect
    uvicorn.run(app, host="0.0.0.0", port=3030)
