"""Tests for new CodeMAID features: trace_callback, edit_plan, and run_command security."""

import json
import tempfile
from pathlib import Path
import pytest
from codemaid.tools import execute_tool
from codemaid.agent import Agent

@pytest.fixture
def work_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td

def test_edit_plan_tool(work_dir):
    args = {
        "reasoning": "Update tests",
        "edits": [
            {"path": "test.py", "description": "Add more assertions"}
        ]
    }
    result = execute_tool("edit_plan", args, work_dir)
    assert "plan" in result
    assert "Strategy: Update tests" in result["plan"]
    assert "- test.py: Add more assertions" in result["plan"]

def test_run_command_security_blocking(work_dir):
    # Test that multi-command chaining is blocked
    result = execute_tool("run_command", {"command": "ls; rm -rf /"}, work_dir)
    assert "error" in result
    assert "VAULT BLOCKED" in result["error"]
    
    # Test that redirection is blocked
    result = execute_tool("run_command", {"command": "echo hello > out.txt"}, work_dir)
    assert "error" in result
    assert "VAULT BLOCKED" in result["error"]

def test_agent_trace_callback():
    trace_received = []
    def my_callback(label, content):
        trace_received.append((label, content))
        
    class MockProvider:
        def chat(self, messages, tools=None):
            return {"role": "assistant", "content": "hello"}
            
    agent = Agent(MockProvider(), "/tmp", trace_callback=my_callback)
    agent.trace = True
    agent.chat("hi")
    
    # Should have at least one trace for LLM response
    assert len(trace_received) > 0
    assert any("LLM response" in t[0] for t in trace_received)
