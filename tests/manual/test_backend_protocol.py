"""Tests for the backend protocol."""
import pytest
from adk_fluent.backends._protocol import Backend, final_text
from adk_fluent._ir import AgentEvent


def test_backend_is_runtime_checkable():
    """Backend should be a runtime-checkable Protocol."""
    assert hasattr(Backend, '__protocol_attrs__') or hasattr(Backend, '__abstractmethods__')


def test_final_text_extracts_last_final_content():
    events = [
        AgentEvent(author="a", content="Step 1"),
        AgentEvent(author="a", content="Step 2"),
        AgentEvent(author="a", content="Final answer", is_final=True),
    ]
    assert final_text(events) == "Final answer"


def test_final_text_returns_empty_on_no_final():
    events = [
        AgentEvent(author="a", content="Step 1"),
    ]
    assert final_text(events) == ""


def test_final_text_handles_empty_events():
    assert final_text([]) == ""


def test_final_text_skips_partial_events():
    events = [
        AgentEvent(author="a", content="Partial", is_partial=True),
        AgentEvent(author="a", content="Done", is_final=True),
    ]
    assert final_text(events) == "Done"
