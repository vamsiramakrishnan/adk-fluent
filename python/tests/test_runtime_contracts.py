"""Runtime contract enforcement (.enforce_contracts())."""

import pytest
from pydantic import BaseModel

from adk_fluent import Agent


class _Needs(BaseModel):
    topic: str


class _Writes(BaseModel):
    findings: str


class _Ctx:
    def __init__(self, **state):
        self.state = dict(state)


def test_consumes_passes_when_present():
    agent = Agent("a", "gemini-2.5-flash").consumes(_Needs).enforce_contracts()
    cb = agent._callbacks["before_agent_callback"][-1]
    assert cb(_Ctx(topic="ai")) is None


def test_consumes_raises_when_missing():
    agent = Agent("a", "gemini-2.5-flash").consumes(_Needs).enforce_contracts()
    cb = agent._callbacks["before_agent_callback"][-1]
    with pytest.raises(ValueError, match="consumes"):
        cb(_Ctx())  # 'topic' absent


def test_produces_raises_when_not_written():
    agent = Agent("a", "gemini-2.5-flash").produces(_Writes).enforce_contracts()
    cb = agent._callbacks["after_agent_callback"][-1]
    with pytest.raises(ValueError, match="produces"):
        cb(_Ctx())  # 'findings' never written


def test_order_independent():
    """Schema is read live, so enforce_contracts before consumes still works."""
    agent = Agent("a", "gemini-2.5-flash").enforce_contracts().consumes(_Needs)
    cb = agent._callbacks["before_agent_callback"][-1]
    with pytest.raises(ValueError):
        cb(_Ctx())


def test_no_effect_without_schema():
    agent = Agent("a", "gemini-2.5-flash").enforce_contracts()
    for cb in agent._callbacks.get("before_agent_callback", []):
        assert cb(_Ctx()) is None
