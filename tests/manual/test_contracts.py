"""Tests for produces/consumes inter-agent contracts."""
import pytest
from pydantic import BaseModel


class Intent(BaseModel):
    category: str
    confidence: float


class Resolution(BaseModel):
    ticket_id: str
    status: str


def test_produces_sets_writes_keys():
    from adk_fluent import Agent
    a = Agent("classifier").produces(Intent)
    ir = a.to_ir()
    assert ir.writes_keys == frozenset({"category", "confidence"})
    assert ir.produces_type is Intent


def test_consumes_sets_reads_keys():
    from adk_fluent import Agent
    a = Agent("resolver").consumes(Intent)
    ir = a.to_ir()
    assert ir.reads_keys == frozenset({"category", "confidence"})
    assert ir.consumes_type is Intent


def test_produces_and_consumes_together():
    from adk_fluent import Agent
    a = Agent("resolver").consumes(Intent).produces(Resolution)
    ir = a.to_ir()
    assert ir.reads_keys == frozenset({"category", "confidence"})
    assert ir.writes_keys == frozenset({"ticket_id", "status"})


def test_produces_returns_self():
    from adk_fluent import Agent
    a = Agent("a")
    result = a.produces(Intent)
    assert result is a


def test_consumes_returns_self():
    from adk_fluent import Agent
    a = Agent("a")
    result = a.consumes(Intent)
    assert result is a


def test_pipeline_to_ir_propagates_contracts():
    from adk_fluent import Agent
    pipeline = Agent("a").produces(Intent) >> Agent("b").consumes(Intent)
    ir = pipeline.to_ir()
    child_a = ir.children[0]
    child_b = ir.children[1]
    assert child_a.writes_keys == frozenset({"category", "confidence"})
    assert child_b.reads_keys == frozenset({"category", "confidence"})


def test_produces_with_non_pydantic_raises():
    from adk_fluent import Agent
    with pytest.raises(TypeError, match="Pydantic"):
        Agent("a").produces(dict)
