"""Tests for OpenPaws tools — security, correctness, and functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from openpaws.tools import execute_tool, _check_confinement


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def work_dir():
    """Create a temporary working directory for each test."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def sample_file(work_dir):
    """Create a sample file for read/edit tests."""
    path = Path(work_dir) / "hello.py"
    path.write_text("def greet(name):\n    return f'Hello, {name}!'\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

class TestReadFile:
    def test_read_existing_file(self, work_dir, sample_file):
        result = execute_tool("read_file", {"path": "hello.py"}, work_dir)
        assert "content" in result
        assert "greet" in result["content"]

    def test_read_nonexistent_file(self, work_dir):
        result = execute_tool("read_file", {"path": "nope.py"}, work_dir)
        assert "error" in result

    def test_read_file_outside_workdir(self, work_dir):
        result = execute_tool("read_file", {"path": "../../etc/passwd"}, work_dir)
        assert "error" in result
        assert "Access denied" in result["error"]


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------

class TestWriteFile:
    def test_write_new_file(self, work_dir):
        result = execute_tool("write_file", {
            "path": "new.txt",
            "content": "hello world\n",
        }, work_dir)
        assert "message" in result
        assert (Path(work_dir) / "new.txt").exists()

    def test_write_file_outside_workdir(self, work_dir):
        result = execute_tool("write_file", {
            "path": "../../etc/evil",
            "content": "pwned",
        }, work_dir)
        assert "error" in result
        assert "Access denied" in result["error"]

    def test_write_nested_directory(self, work_dir):
        result = execute_tool("write_file", {
            "path": "a/b/c/deep.txt",
            "content": "nested\n",
        }, work_dir)
        assert "message" in result
        assert (Path(work_dir) / "a/b/c/deep.txt").exists()


# ---------------------------------------------------------------------------
# edit_file
# ---------------------------------------------------------------------------

class TestEditFile:
    def test_exact_match_edit(self, work_dir, sample_file):
        result = execute_tool("edit_file", {
            "path": "hello.py",
            "search": "greet",
            "replace": "welcome",
        }, work_dir)
        assert "message" in result
        content = sample_file.read_text(encoding="utf-8")
        assert "welcome" in content

    def test_edit_empty_search(self, work_dir, sample_file):
        result = execute_tool("edit_file", {
            "path": "hello.py",
            "search": "   ",
            "replace": "x",
        }, work_dir)
        assert "error" in result
        assert "empty" in result["error"].lower()

    def test_edit_nonexistent_file(self, work_dir):
        result = execute_tool("edit_file", {
            "path": "ghost.py",
            "search": "x",
            "replace": "y",
        }, work_dir)
        assert "error" in result


# ---------------------------------------------------------------------------
# diff_preview & undo_edit
# ---------------------------------------------------------------------------

class TestEditSafety:
    def test_undo_edit(self, work_dir, sample_file):
        original = sample_file.read_text(encoding="utf-8")

        # Make an edit (creates a backup)
        execute_tool("edit_file", {
            "path": "hello.py",
            "search": "greet",
            "replace": "welcome",
        }, work_dir)

        # Undo
        result = execute_tool("undo_edit", {"path": "hello.py"}, work_dir)
        assert "message" in result

        restored = sample_file.read_text(encoding="utf-8")
        assert restored == original

    def test_diff_preview(self, work_dir, sample_file):
        execute_tool("edit_file", {
            "path": "hello.py",
            "search": "greet",
            "replace": "welcome",
        }, work_dir)

        result = execute_tool("diff_preview", {"path": "hello.py"}, work_dir)
        assert "diff" in result
        assert "+def welcome" in result["diff"]
        assert "-def greet" in result["diff"]


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------

class TestRunCommand:
    def test_run_command_returns_dict(self, work_dir):
        result = execute_tool("run_command", {"command": "echo hello"}, work_dir)
        assert isinstance(result, dict)
        assert "output" in result

    def test_run_command_exit_code(self, work_dir):
        result = execute_tool("run_command", {"command": "false"}, work_dir)
        assert result["exit_code"] != 0


# ---------------------------------------------------------------------------
# read_document
# ---------------------------------------------------------------------------

class TestReadDocument:
    def test_read_document_path_traversal(self, work_dir):
        result = execute_tool("read_document", {"path": "../../etc/passwd"}, work_dir)
        assert "error" in result
        assert "Access denied" in result["error"]


# ---------------------------------------------------------------------------
# list_dir
# ---------------------------------------------------------------------------

class TestListDir:
    def test_list_dir(self, work_dir, sample_file):
        result = execute_tool("list_dir", {}, work_dir)
        assert "listing" in result
        assert "hello.py" in result["listing"]


# ---------------------------------------------------------------------------
# grep / focus
# ---------------------------------------------------------------------------

class TestSearch:
    def test_grep(self, work_dir, sample_file):
        result = execute_tool("grep", {"pattern": "greet"}, work_dir)
        assert "matches" in result

    def test_focus(self, work_dir, sample_file):
        result = execute_tool("focus", {"pattern": "greet"}, work_dir)
        assert "focus_results" in result


# ---------------------------------------------------------------------------
# read_multiple
# ---------------------------------------------------------------------------

class TestReadMultiple:
    def test_read_multiple(self, work_dir, sample_file):
        p2 = Path(work_dir) / "second.txt"
        p2.write_text("second file", encoding="utf-8")
        result = execute_tool("read_multiple", {"paths": ["hello.py", "second.txt"]}, work_dir)
        assert "hello.py" in result
        assert "second.txt" in result


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class TestAgent:
    def test_agent_has_chat_method(self):
        from openpaws.agent import Agent
        assert hasattr(Agent, "chat")
        assert callable(Agent.chat)

    def test_agent_max_iterations(self):
        from openpaws.agent import Agent
        assert Agent.MAX_ITERATIONS == 20
