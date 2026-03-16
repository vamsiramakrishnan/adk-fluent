"""Tests for the Temporal backend (Phase 5 of five-layer decoupling)."""

import pytest

from adk_fluent._ir import TransformNode
from adk_fluent._ir_generated import AgentNode, LoopNode, ParallelNode, SequenceNode
from adk_fluent.backends.temporal import TemporalBackend, TemporalRunnable
from adk_fluent.compile import EngineCapabilities


class TestTemporalBackendCapabilities:
    def test_capabilities(self):
        backend = TemporalBackend()
        cap = backend.capabilities
        assert cap.durable is True
        assert cap.replay is True
        assert cap.checkpointing is True
        assert cap.signals is True
        assert cap.distributed is True
        assert cap.streaming is False  # Temporal doesn't natively support streaming

    def test_name(self):
        assert TemporalBackend().name == "temporal"


class TestTemporalCompile:
    def test_compile_agent_node(self):
        """AgentNode compiles to an activity (non-deterministic)."""
        backend = TemporalBackend()
        node = AgentNode(name="researcher", model="gemini-2.5-flash")
        result = backend.compile(node)

        assert isinstance(result, TemporalRunnable)
        assert len(result.node_plan) == 1
        plan = result.node_plan[0]
        assert plan["node_type"] == "AgentNode"
        assert plan["temporal_type"] == "activity"
        assert plan["deterministic"] is False
        assert plan["checkpoint"] is True
        assert plan["name"] == "researcher"

    def test_compile_sequence(self):
        """SequenceNode compiles to a workflow (deterministic)."""
        backend = TemporalBackend()
        a = AgentNode(name="a", model="gemini-2.5-flash")
        b = AgentNode(name="b", model="gemini-2.5-flash")
        seq = SequenceNode(name="pipeline", children=(a, b))
        result = backend.compile(seq)

        assert len(result.node_plan) == 1
        plan = result.node_plan[0]
        assert plan["node_type"] == "SequenceNode"
        assert plan["temporal_type"] == "workflow"
        assert plan["deterministic"] is True
        assert len(plan["children"]) == 2
        assert plan["children"][0]["temporal_type"] == "activity"
        assert plan["children"][1]["temporal_type"] == "activity"

    def test_compile_parallel(self):
        """ParallelNode compiles to a workflow with concurrent activities."""
        backend = TemporalBackend()
        a = AgentNode(name="web", model="gemini-2.5-flash")
        b = AgentNode(name="papers", model="gemini-2.5-flash")
        par = ParallelNode(name="fanout", children=(a, b))
        result = backend.compile(par)

        plan = result.node_plan[0]
        assert plan["node_type"] == "ParallelNode"
        assert plan["temporal_type"] == "workflow"
        assert len(plan["children"]) == 2

    def test_compile_loop(self):
        """LoopNode compiles to a workflow with checkpointed iterations."""
        backend = TemporalBackend()
        a = AgentNode(name="writer", model="gemini-2.5-flash")
        loop = LoopNode(name="refine", children=(a,), max_iterations=3)
        result = backend.compile(loop)

        plan = result.node_plan[0]
        assert plan["node_type"] == "LoopNode"
        assert plan["temporal_type"] == "workflow"
        assert plan["checkpoint"] is True
        assert plan["max_iterations"] == 3

    def test_compile_transform(self):
        """TransformNode compiles to inline workflow code (deterministic)."""
        backend = TemporalBackend()
        transform = TransformNode(name="t1", fn=lambda s: s)
        result = backend.compile(transform)

        plan = result.node_plan[0]
        assert plan["node_type"] == "TransformNode"
        assert plan["temporal_type"] == "inline"
        assert plan["deterministic"] is True
        assert plan["checkpoint"] is False

    def test_compile_nested_pipeline(self):
        """Nested pipeline compiles recursively."""
        backend = TemporalBackend()
        inner = SequenceNode(name="inner", children=(
            AgentNode(name="a"),
            TransformNode(name="t", fn=lambda s: s),
        ))
        outer = SequenceNode(name="outer", children=(
            inner,
            AgentNode(name="b"),
        ))
        result = backend.compile(outer)

        plan = result.node_plan[0]
        assert plan["node_type"] == "SequenceNode"
        assert len(plan["children"]) == 2
        # First child is inner SequenceNode
        inner_plan = plan["children"][0]
        assert inner_plan["node_type"] == "SequenceNode"
        assert len(inner_plan["children"]) == 2

    def test_compile_preserves_ir(self):
        """Compiled result preserves original IR."""
        backend = TemporalBackend()
        node = AgentNode(name="test")
        result = backend.compile(node)
        assert result.ir is node


class TestTemporalRun:
    def test_run_without_client_raises(self):
        """run() without a client raises RuntimeError."""
        import asyncio

        backend = TemporalBackend()  # No client
        node = AgentNode(name="test")
        compiled = backend.compile(node)

        with pytest.raises(RuntimeError, match="requires a Temporal client"):
            asyncio.run(backend.run(compiled, "Hello"))


class TestTemporalRegistry:
    def test_registered(self):
        from adk_fluent.backends import available_backends

        assert "temporal" in available_backends()

    def test_get_backend(self):
        from adk_fluent.backends import get_backend

        backend = get_backend("temporal")
        assert backend.name == "temporal"


class TestTemporalCompileViaCentralCompile:
    def test_compile_function(self):
        """compile() with backend="temporal" works."""
        from adk_fluent.compile import compile

        ir = AgentNode(name="test", model="gemini-2.5-flash")
        result = compile(ir, backend="temporal")
        assert result.backend_name == "temporal"
        assert result.capabilities.durable is True
