"""Tests for S.capture() — bridge conversation history to session state."""

import pytest

from adk_fluent import Agent, S
from adk_fluent._base import CaptureAgent, _CaptureBuilder
from adk_fluent._ir import CaptureNode, Node
from adk_fluent._transforms import StateDelta
from adk_fluent.backends.adk import ADKBackend
from adk_fluent.workflow import Pipeline


class TestCaptureFactory:
    """S.capture() returns a callable with correct attributes."""

    def test_returns_callable(self):
        fn = S.capture("user_input")
        assert callable(fn)

    def test_has_correct_name(self):
        fn = S.capture("user_input")
        assert fn.__name__ == "capture_user_input"

    def test_has_capture_key_attribute(self):
        fn = S.capture("query")
        assert fn._capture_key == "query"

    def test_callable_returns_empty_state_delta(self):
        fn = S.capture("user_input")
        result = fn({"some": "state"})
        assert isinstance(result, StateDelta)
        assert result.updates == {}


class TestCaptureComposition:
    """S.capture() composes with >> to create a Pipeline."""

    def test_capture_rshift_agent_creates_pipeline(self):
        p = S.capture("user_input") >> Agent("writer").model("gemini-2.5-flash")
        assert isinstance(p, Pipeline)

    def test_agent_rshift_capture_creates_pipeline(self):
        p = Agent("reader").model("gemini-2.5-flash") >> S.capture("user_input")
        assert isinstance(p, Pipeline)

    def test_capture_in_chain(self):
        p = (
            S.capture("user_input")
            >> Agent("writer").model("gemini-2.5-flash")
            >> S.capture("feedback")
        )
        assert isinstance(p, Pipeline)
        built = p.build()
        assert len(built.sub_agents) == 3


class TestCaptureNode:
    """CaptureNode IR type exists and has correct fields."""

    def test_is_frozen_dataclass(self):
        node = CaptureNode(name="cap", key="user_input")
        with pytest.raises(AttributeError):
            node.name = "other"

    def test_has_name_field(self):
        node = CaptureNode(name="cap", key="user_input")
        assert node.name == "cap"

    def test_has_key_field(self):
        node = CaptureNode(name="cap", key="user_input")
        assert node.key == "user_input"

    def test_in_node_union(self):
        assert CaptureNode in Node.__args__


class TestCaptureBuilder:
    """_CaptureBuilder produces CaptureAgent and CaptureNode."""

    def test_build_returns_capture_agent(self):
        builder = _CaptureBuilder("capture_query", "query")
        agent = builder.build()
        assert isinstance(agent, CaptureAgent)
        assert agent.name == "capture_query"
        assert agent._capture_key == "query"

    def test_to_ir_returns_capture_node(self):
        builder = _CaptureBuilder("capture_query", "query")
        node = builder.to_ir()
        assert isinstance(node, CaptureNode)
        assert node.name == "capture_query"
        assert node.key == "query"

    def test_fn_step_detects_capture_key(self):
        from adk_fluent._base import _fn_step

        fn = S.capture("user_input")
        builder = _fn_step(fn)
        assert isinstance(builder, _CaptureBuilder)


class TestBackendCompileCapture:
    """Backend compiles CaptureNode to CaptureAgent."""

    def test_compile_capture_node(self):
        backend = ADKBackend()
        node = CaptureNode(name="capture_input", key="user_input")
        agent = backend._compile_node(node)
        assert isinstance(agent, CaptureAgent)
        assert agent.name == "capture_input"
        assert agent._capture_key == "user_input"


class TestPipelineWithCapture:
    """Pipeline with S.capture >> Agent builds successfully."""

    def test_pipeline_build_has_capture_agent_first(self):
        p = S.capture("user_input") >> Agent("writer").model("gemini-2.5-flash")
        built = p.build()
        assert isinstance(built.sub_agents[0], CaptureAgent)
        assert built.sub_agents[0]._capture_key == "user_input"

    def test_pipeline_ir_has_capture_node(self):
        p = S.capture("user_input") >> Agent("writer").model("gemini-2.5-flash")
        ir = p.to_ir()
        from adk_fluent._ir_generated import SequenceNode

        assert isinstance(ir, SequenceNode)
        assert isinstance(ir.children[0], CaptureNode)
        assert ir.children[0].key == "user_input"
