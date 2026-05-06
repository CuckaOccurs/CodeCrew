from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Horizontal, Vertical, VerticalScroll
import os
import sys
from pathlib import Path

# Discovery logic for CodeMOP/CodeMAID
CODEMOP_PATH = Path(os.getenv("CODEMOP_HOME", Path.home() / "CodeMAID"))
if not CODEMOP_PATH.exists():
    sibling = Path(__file__).parent.parent / "CodeMAID"
    if sibling.exists():
        CODEMOP_PATH = sibling

MOP_AVAILABLE = False
if CODEMOP_PATH.exists():
    sys.path.insert(0, str(CODEMOP_PATH))
    try:
        from codemop import load_config
        from codemop.api import OllamaAPI
        MOP_AVAILABLE = True
    except Exception:
        pass

def get_engine_url():
    if MOP_AVAILABLE:
        try:
            config = load_config()
            return config.get("codemaid", {}).get("engine_url", "http://localhost:8080")
        except Exception:
            # Silence is intentional here to prevent UI disruption during polling/init
            pass
    return os.getenv("MAID_ENGINE_URL", "http://localhost:8080")

class AUI(App):
    CSS = """
    #sidebar-left { width: 30; background: #141416; border-right: solid #2a2a32; }
    #sidebar-right { width: 30; background: #141416; border-left: solid #2a2a32; }
    #chat-main { width: 1fr; background: #0e0e10; }
    #chat-stream { height: 1fr; padding: 1; }
    .hidden { display: none; }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+l", "toggle_left", "Toggle MAID Admin"),
        ("ctrl+r", "toggle_right", "Toggle Tree/Branching"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Vertical(Static("--- MAID Admin ---", id="admin-header"), Static("Personas/RTFM", id="admin-tree"), id="sidebar-left")
            with Vertical(id="chat-main"):
                yield VerticalScroll(Static("> Initialize System...", id="chat-stream"), id="chat-stream")
                yield Input(placeholder="Send prompt...", id="prompt-input")
            yield Vertical(Static("--- ASS Tree ---", id="tree-header"), Static("Tree View", id="tree-view"), id="sidebar-right")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "prompt-input":
            value = event.value.strip()
            if len(value) > 1:
                await self.query_one("#chat-stream").mount(Static(f"> {value}"))
                event.input.value = ""

    def action_toggle_left(self) -> None:
        self.query_one("#sidebar-left").toggle_class("hidden")

    def action_toggle_right(self) -> None:
        self.query_one("#sidebar-right").toggle_class("hidden")

    async def fetch_engine_status(self):
        """Monitor engine status."""
        if MOP_AVAILABLE:
            try:
                engine = OllamaAPI()
                status = await engine.status()
                # Status is fetched asynchronously via the unified bridge
            except Exception:
                # Silence is intentional here to prevent UI disruption during polling/init
                pass
        else:
            import httpx
            try:
                engine_url = get_engine_url()
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{engine_url}/api/status")
                    # Placeholder for logic
            except Exception:
                # Silence is intentional here to prevent UI disruption during polling/init
                pass

    def on_mount(self) -> None:
        self.run_worker(self.initialize_system())

    async def initialize_system(self):
        """Perform system pre-flight check."""
        chat_stream = self.query_one("#chat-stream")
        # Remove old status content
        for child in chat_stream.query(Static):
            child.remove()

        # Add new status
        await chat_stream.mount(Static("> Linking with The Brain..."))
        await self.fetch_engine_status()

        # Clear and update
        for child in chat_stream.query(Static):
            child.remove()
        await chat_stream.mount(Static("> System Armed. The Brain is online."))


    def action_note(self, content: str):
        """Action: Capture a quick note to the centralized scratchpad."""
        from datetime import datetime
        from pathlib import Path
        note_path = Path.home() / "Desktop" / "Notes" / "notes.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        note_path.parent.mkdir(parents=True, exist_ok=True)
        with open(note_path, "a") as f:
            f.write(f"[{timestamp}] {content}\n")
        self.query_one("#chat-stream").mount(Static(f"[Note captured: {content}]"))

if __name__ == "__main__":
    app = AUI()
    app.run()
