"""Tests for generated IR node types."""

import pytest


def test_agent_node_exists():
    from adk_fluent._ir_generated import AgentNode

    assert AgentNode is not None


def test_sequence_node_exists():
    from adk_fluent._ir_generated import SequenceNode

    assert SequenceNode is not None


def test_parallel_node_exists():
    from adk_fluent._ir_generated import ParallelNode

    assert ParallelNode is not None


def test_loop_node_exists():
    from adk_fluent._ir_generated import LoopNode

    assert LoopNode is not None


def test_agent_node_is_frozen():
    from adk_fluent._ir_generated import AgentNode

    node = AgentNode(name="test")
    with pytest.raises(AttributeError):
        node.name = "changed"


def test_agent_node_has_model_field():
    from adk_fluent._ir_generated import AgentNode

    node = AgentNode(name="test", model="gemini-2.5-flash")
    assert node.model == "gemini-2.5-flash"


def test_agent_node_has_instruction_field():
    from adk_fluent._ir_generated import AgentNode

    node = AgentNode(name="test", instruction="Help the user")
    assert node.instruction == "Help the user"


def test_agent_node_has_children():
    from adk_fluent._ir_generated import AgentNode

    child = AgentNode(name="child")
    parent = AgentNode(name="parent", children=(child,))
    assert len(parent.children) == 1
    assert parent.children[0].name == "child"


def test_agent_node_has_callbacks():
    from adk_fluent._ir_generated import AgentNode

    fn = lambda ctx: None
    node = AgentNode(name="test", callbacks={"before_model": (fn,)})
    assert "before_model" in node.callbacks


def test_agent_node_has_adk_fluent_extensions():
    from adk_fluent._ir_generated import AgentNode

    node = AgentNode(name="test", writes_keys=frozenset({"intent"}))
    assert "intent" in node.writes_keys


def test_sequence_node_has_children():
    from adk_fluent._ir_generated import AgentNode, SequenceNode

    c1 = AgentNode(name="a")
    c2 = AgentNode(name="b")
    seq = SequenceNode(name="pipe", children=(c1, c2))
    assert len(seq.children) == 2


def test_loop_node_has_max_iterations():
    from adk_fluent._ir_generated import AgentNode, LoopNode

    body = AgentNode(name="step")
    loop = LoopNode(name="loop", children=(body,), max_iterations=5)
    assert loop.max_iterations == 5


def test_all_node_type_union():
    """The full Node union should include both generated and hand-written types."""
    from adk_fluent._ir import TransformNode
    from adk_fluent._ir_generated import AgentNode

    # Both should be valid Node types
    assert AgentNode is not None
    assert TransformNode is not None
