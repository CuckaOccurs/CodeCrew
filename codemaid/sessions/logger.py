import uuid
from .storage import SQLiteStorage

class SessionLogger:
    def __init__(self, storage=None):
        self.storage = storage or SQLiteStorage()
        self.current_session_id = None

    def start_session(self, agent_id, profile=None):
        self.current_session_id = f"{agent_id}_{uuid.uuid4().hex[:8]}"
        self.storage.save_session(self.current_session_id, agent_id, profile=profile)
        return self.current_session_id

    def resume_last(self, agent_id=None):
        """Load the last session's summary for context injection. Does not reopen it."""
        last = self.storage.last_session(agent_id)
        if last and last.get("summary"):
            return last["summary"]
        return None

    def get_last_session_info(self, agent_id=None):
        """Return metadata about the last session."""
        return self.storage.last_session(agent_id)

    def save_summary(self, summary):
        if self.current_session_id:
            self.storage.save_summary(self.current_session_id, summary)

    def log_input(self, text):
        if self.current_session_id:
            self.storage.save_event(self.current_session_id, "input", {"text": text})

    def log_output(self, text):
        if self.current_session_id:
            self.storage.save_event(self.current_session_id, "output", {"text": text})

    def log_tool_call(self, name, args):
        if self.current_session_id:
            self.storage.save_event(self.current_session_id, "tool_call", {"name": name, "args": args})

    def log_tool_result(self, name, result):
        if self.current_session_id:
            self.storage.save_event(self.current_session_id, "tool_result", {"name": name, "result": result})

    def log_error(self, message):
        if self.current_session_id:
            self.storage.save_event(self.current_session_id, "error", {"message": message})

    def end_session(self, status="completed"):
        if self.current_session_id:
            self.storage.end_session(self.current_session_id, status)
            self.current_session_id = None
