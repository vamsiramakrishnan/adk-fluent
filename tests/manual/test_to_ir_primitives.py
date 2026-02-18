"""Tests for to_ir() on primitive builders."""
import pytest
from adk_fluent._ir import (
    TransformNode, TapNode, FallbackNode, RaceNode,
    GateNode, MapOverNode, TimeoutNode, RouteNode,
)


def test_fn_step_to_ir():
    from adk_fluent._base import _fn_step
    fn = lambda s: {"x": 1}
    ir = _fn_step(fn).to_ir()
    assert isinstance(ir, TransformNode)
    assert ir.fn is fn
    assert ir.semantics == "merge"


def test_tap_to_ir():
    from adk_fluent import tap
    fn = lambda s: print(s)
    ir = tap(fn).to_ir()
    assert isinstance(ir, TapNode)
    assert ir.fn is fn


def test_fallback_to_ir():
    from adk_fluent import Agent
    from adk_fluent._base import _FallbackBuilder
    a = Agent("a")
    b = Agent("b")
    ir = _FallbackBuilder("fb", [a, b]).to_ir()
    assert isinstance(ir, FallbackNode)
    assert len(ir.children) == 2


def test_gate_to_ir():
    from adk_fluent import gate
    ir = gate(lambda s: s.get("approved")).to_ir()
    assert isinstance(ir, GateNode)
    assert ir.message == "Approval required"


def test_race_to_ir():
    from adk_fluent import Agent, race
    ir = race(Agent("a"), Agent("b")).to_ir()
    assert isinstance(ir, RaceNode)
    assert len(ir.children) == 2


def test_map_over_to_ir():
    from adk_fluent import Agent, map_over
    ir = map_over("items", Agent("processor")).to_ir()
    assert isinstance(ir, MapOverNode)
    assert ir.list_key == "items"
    assert ir.item_key == "_item"


def test_timeout_to_ir():
    from adk_fluent import Agent
    from adk_fluent._base import _TimeoutBuilder
    ir = _TimeoutBuilder("to", Agent("a"), 30.0).to_ir()
    assert isinstance(ir, TimeoutNode)
    assert ir.seconds == 30.0


def test_route_to_ir():
    from adk_fluent import Agent
    from adk_fluent._routing import Route
    ir = Route("intent").eq("billing", Agent("b")).otherwise(Agent("d")).to_ir()
    assert isinstance(ir, RouteNode)
    assert ir.key == "intent"
    assert len(ir.rules) == 1
    assert ir.default is not None


def test_nested_to_ir_recursion():
    """to_ir() should recursively convert child builders."""
    from adk_fluent import Agent
    from adk_fluent._base import _FallbackBuilder
    a = Agent("a")
    b = Agent("b")
    ir = _FallbackBuilder("fb", [a, b]).to_ir()
    # Children should be IR nodes, not builders
    from adk_fluent._ir_generated import AgentNode
    for child in ir.children:
        assert isinstance(child, AgentNode)


def test_base_to_ir_raises():
    """BuilderBase.to_ir() should raise NotImplementedError."""
    from adk_fluent._base import BuilderBase
    class Dummy(BuilderBase):
        _ADK_TARGET_CLASS = None
        _KNOWN_PARAMS = frozenset()
        _ALIASES = {}
        _CALLBACK_ALIASES = {}
        _ADDITIVE_FIELDS = set()
    d = Dummy.__new__(Dummy)
    d._config = {"name": "test"}
    d._lists = {}
    d._callbacks = {}
    with pytest.raises(NotImplementedError):
        d.to_ir()
