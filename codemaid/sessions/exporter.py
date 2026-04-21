import json
from pathlib import Path
from datetime import datetime

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>CodeM.A.I.D Session: {session_id}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #1a1a1b; color: #d7dadc; line-height: 1.6; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ color: #5384e4; border-bottom: 1px solid #343536; padding-bottom: 10px; }}
        .meta {{ color: #818384; font-size: 0.9em; margin-bottom: 20px; }}
        .event {{ background-color: #272729; border: 1px solid #343536; border-radius: 5px; margin-bottom: 15px; padding: 15px; }}
        .event-header {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-weight: bold; cursor: pointer; }}
        .type-input {{ color: #ffd54f; }}
        .type-output {{ color: #81c784; }}
        .type-tool_call {{ color: #64b5f6; }}
        .type-tool_result {{ color: #ba68c8; }}
        .type-error {{ color: #e57373; }}
        .timestamp {{ color: #818384; font-size: 0.8em; }}
        .content {{ white-space: pre-wrap; word-wrap: break-word; font-family: 'Consolas', 'Monaco', monospace; font-size: 0.9em; }}
        pre {{ background: #121213; padding: 10px; border-radius: 3px; overflow-x: auto; }}
        .hidden {{ display: none; }}
    </style>
    <script>
        function toggle(id) {{
            const el = document.getElementById(id);
            el.classList.toggle('hidden');
        }}
    </script>
</head>
<body>
    <div class="container">
        <h1>CodeM.A.I.D Session History</h1>
        <div class="meta">
            Session ID: {session_id}<br>
            Agent: {agent_id}<br>
            Started: {started_at}<br>
        </div>
        <div class="timeline">
            {events_html}
        </div>
    </div>
</body>
</html>
"""

EVENT_TEMPLATE = """
<div class="event">
    <div class="event-header" onclick="toggle('e{index}')">
        <span class="type-{type}">{type_upper}</span>
        <span class="timestamp">{timestamp}</span>
    </div>
    <div class="content" id="e{index}">
        <pre>{content}</pre>
    </div>
</div>
"""

def generate_html(session, events):
    events_html = ""
    for i, event in enumerate(events):
        content = event["content"]
        if isinstance(content, dict):
            content = json.dumps(content, indent=2)
        
        events_html += EVENT_TEMPLATE.format(
            index=i,
            type=event["event_type"],
            type_upper=event["event_type"].upper().replace("_", " "),
            timestamp=event["timestamp"],
            content=content
        )
    
    return HTML_TEMPLATE.format(
        session_id=session["session_id"],
        agent_id=session["agent_id"],
        started_at=session["started_at"],
        events_html=events_html
    )

def export_session(storage, session_id, output_path):
    session = storage.load_session(session_id)
    events = storage.load_events(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    html = generate_html(session, events)
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
