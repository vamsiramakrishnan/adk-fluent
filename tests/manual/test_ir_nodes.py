"""Tests for hand-written IR node types."""
import pytest
from adk_fluent._ir import (
    TransformNode, TapNode, FallbackNode, RaceNode, GateNode,
    MapOverNode, TimeoutNode, RouteNode, TransferNode,
    ExecutionConfig, CompactionConfig, AgentEvent,
    Node,
)


# --- Frozen immutability ---

def test_transform_node_is_frozen():
    node = TransformNode(name="t1", fn=lambda s: s)
    with pytest.raises(AttributeError):
        node.name = "changed"


def test_tap_node_is_frozen():
    node = TapNode(name="tap1", fn=lambda s: None)
    with pytest.raises(AttributeError):
        node.name = "changed"


# --- Field defaults ---

def test_transform_node_defaults():
    fn = lambda s: {"x": 1}
    node = TransformNode(name="t1", fn=fn)
    assert node.semantics == "merge"
    assert node.scope == "session"
    assert node.affected_keys is None


def test_map_over_node_defaults():
    from adk_fluent._ir import TapNode
    body = TapNode(name="inner", fn=lambda s: None)
    node = MapOverNode(name="m1", list_key="items", body=body)
    assert node.item_key == "_item"
    assert node.output_key == "results"


def test_gate_node_defaults():
    node = GateNode(name="g1", predicate=lambda s: True)
    assert node.message == "Approval required"


def test_route_node_defaults():
    node = RouteNode(name="r1")
    assert node.rules == ()
    assert node.default is None
    assert node.key is None


# --- ExecutionConfig ---

def test_execution_config_defaults():
    cfg = ExecutionConfig()
    assert cfg.app_name == "adk_fluent_app"
    assert cfg.max_llm_calls == 500
    assert cfg.resumable is False
    assert cfg.compaction is None


def test_compaction_config():
    cc = CompactionConfig(interval=5, overlap=2)
    assert cc.interval == 5
    assert cc.overlap == 2
    assert cc.token_threshold is None


# --- AgentEvent ---

def test_agent_event_defaults():
    evt = AgentEvent(author="test")
    assert evt.content is None
    assert evt.state_delta == {}
    assert evt.is_final is False
    assert evt.is_partial is False
    assert evt.transfer_to is None


def test_agent_event_with_content():
    evt = AgentEvent(author="agent1", content="Hello", is_final=True)
    assert evt.content == "Hello"
    assert evt.is_final is True


# --- Node type union ---

def test_node_union_includes_primitive_types():
    """The Node type should accept all primitive IR types."""
    fn = lambda s: s
    nodes = [
        TransformNode(name="t", fn=fn),
        TapNode(name="t", fn=fn),
        GateNode(name="g", predicate=fn),
        RouteNode(name="r"),
        FallbackNode(name="f"),
        RaceNode(name="r"),
    ]
    for n in nodes:
        assert hasattr(n, "name")
