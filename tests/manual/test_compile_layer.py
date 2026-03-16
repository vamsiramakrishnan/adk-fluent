"""Tests for the compile layer (Phase 1 of five-layer decoupling)."""

import pytest

from adk_fluent._ir import TransformNode
from adk_fluent._ir_generated import AgentNode, SequenceNode
from adk_fluent.compile import CompilationResult, EngineCapabilities, compile
from adk_fluent.compile.passes import (
    annotate_checkpoints,
    fuse_transforms,
    run_passes,
    validate_contracts,
)

# ======================================================================
# EngineCapabilities
# ======================================================================


class TestEngineCapabilities:
    def test_defaults(self):
        cap = EngineCapabilities()
        assert cap.streaming is True
        assert cap.parallel is True
        assert cap.durable is False
        assert cap.replay is False
        assert cap.checkpointing is False
        assert cap.signals is False
        assert cap.dispatch_join is True
        assert cap.distributed is False

    def test_custom(self):
        cap = EngineCapabilities(durable=True, replay=True, distributed=True)
        assert cap.durable is True
        assert cap.replay is True
        assert cap.distributed is True
        assert cap.streaming is True  # default

    def test_frozen(self):
        cap = EngineCapabilities()
        with pytest.raises(AttributeError):
            cap.durable = True  # type: ignore[misc]


# ======================================================================
# CompilationResult
# ======================================================================


class TestCompilationResult:
    def test_basic_construction(self):
        ir = AgentNode(name="test")
        result = CompilationResult(
            ir=ir,
            runnable="fake_runnable",
            backend_name="test",
            capabilities=EngineCapabilities(),
        )
        assert result.ir is ir
        assert result.runnable == "fake_runnable"
        assert result.backend_name == "test"
        assert result.warnings == []
        assert result.metadata == {}

    def test_with_warnings(self):
        result = CompilationResult(
            ir=None,
            runnable=None,
            backend_name="test",
            capabilities=EngineCapabilities(),
            warnings=["unused variable"],
        )
        assert len(result.warnings) == 1


# ======================================================================
# Optimization passes
# ======================================================================


class TestFuseTransforms:
    def test_no_op_on_agent_node(self):
        """Agent nodes without children are returned unchanged."""
        node = AgentNode(name="test")
        assert fuse_transforms(node) is node

    def test_fuses_adjacent_transforms_in_sequence(self):
        """Two adjacent merge TransformNodes should fuse into one."""
        t1 = TransformNode(
            name="t1",
            fn=lambda s: {**s, "a": 1},
            semantics="merge",
            affected_keys=frozenset({"a"}),
        )
        t2 = TransformNode(
            name="t2",
            fn=lambda s: {**s, "b": 2},
            semantics="merge",
            affected_keys=frozenset({"b"}),
        )
        seq = SequenceNode(name="pipeline", children=(t1, t2))
        result = fuse_transforms(seq)

        assert len(result.children) == 1
        fused = result.children[0]
        assert isinstance(fused, TransformNode)
        assert fused.name == "_fused_t1_t2"
        assert fused.affected_keys == frozenset({"a", "b"})

        # Verify the composed function works
        out = fused.fn({})
        assert out == {"a": 1, "b": 2}

    def test_preserves_non_merge_transforms(self):
        """TransformNodes with non-merge semantics are not fused."""
        t1 = TransformNode(name="t1", fn=lambda s: s, semantics="merge")
        t2 = TransformNode(name="t2", fn=lambda s: s, semantics="replace_session")
        seq = SequenceNode(name="pipeline", children=(t1, t2))
        result = fuse_transforms(seq)

        # t2 breaks the chain because it has non-merge semantics
        assert len(result.children) == 2

    def test_preserves_interleaved_agents(self):
        """Non-transform nodes break the fusion chain."""
        t1 = TransformNode(name="t1", fn=lambda s: s, semantics="merge")
        agent = AgentNode(name="a")
        t2 = TransformNode(name="t2", fn=lambda s: s, semantics="merge")
        seq = SequenceNode(name="pipeline", children=(t1, agent, t2))
        result = fuse_transforms(seq)

        assert len(result.children) == 3

    def test_fuses_three_consecutive(self):
        """Three consecutive merge TransformNodes fuse into one."""
        t1 = TransformNode(name="t1", fn=lambda s: {**s, "a": 1}, semantics="merge")
        t2 = TransformNode(name="t2", fn=lambda s: {**s, "b": 2}, semantics="merge")
        t3 = TransformNode(name="t3", fn=lambda s: {**s, "c": 3}, semantics="merge")
        seq = SequenceNode(name="pipeline", children=(t1, t2, t3))
        result = fuse_transforms(seq)

        assert len(result.children) == 1
        out = result.children[0].fn({})
        assert out == {"a": 1, "b": 2, "c": 3}

    def test_single_transform_not_fused(self):
        """A single TransformNode is not fused (nothing to fuse with)."""
        t1 = TransformNode(name="t1", fn=lambda s: s, semantics="merge")
        seq = SequenceNode(name="pipeline", children=(t1,))
        result = fuse_transforms(seq)

        assert len(result.children) == 1
        assert result.children[0] is t1  # Unchanged


class TestAnnotateCheckpoints:
    def test_returns_unchanged(self):
        """Placeholder pass returns IR unchanged."""
        node = AgentNode(name="test")
        assert annotate_checkpoints(node) is node


class TestValidateContracts:
    def test_returns_list(self):
        """Contract validation returns a list (possibly empty)."""
        node = AgentNode(name="test")
        result = validate_contracts(node)
        assert isinstance(result, list)


class TestRunPasses:
    def test_applies_all_passes(self):
        """run_passes applies fuse_transforms and annotate_checkpoints."""
        t1 = TransformNode(name="t1", fn=lambda s: {**s, "a": 1}, semantics="merge")
        t2 = TransformNode(name="t2", fn=lambda s: {**s, "b": 2}, semantics="merge")
        seq = SequenceNode(name="pipeline", children=(t1, t2))
        result = run_passes(seq)

        # Verify transforms were fused
        assert len(result.children) == 1


# ======================================================================
# compile() entry point
# ======================================================================


class TestCompile:
    def test_compile_with_adk_backend(self):
        """compile() with the default ADK backend produces a CompilationResult."""
        ir = AgentNode(name="test", model="gemini-2.5-flash")
        result = compile(ir, backend="adk")

        assert isinstance(result, CompilationResult)
        assert result.backend_name == "adk"
        assert result.capabilities.streaming is True
        assert result.capabilities.durable is False
        assert result.ir is not None
        assert result.runnable is not None  # ADK App object

    def test_compile_preserves_ir(self):
        """The original IR (post-optimization) is stored in the result."""
        ir = AgentNode(name="test", model="gemini-2.5-flash")
        result = compile(ir, backend="adk")

        # IR should be preserved (or optimized version)
        assert result.ir is not None
        assert result.ir.name == "test"

    def test_compile_without_optimization(self):
        """compile(optimize=False) skips passes."""
        ir = AgentNode(name="test", model="gemini-2.5-flash")
        result = compile(ir, backend="adk", optimize=False)

        assert isinstance(result, CompilationResult)
        assert result.ir is ir  # No optimization, same object

    def test_compile_unknown_backend_raises(self):
        """compile() with unknown backend raises KeyError."""
        ir = AgentNode(name="test")
        with pytest.raises(KeyError, match="nonexistent"):
            compile(ir, backend="nonexistent")


# ======================================================================
# Backend registry
# ======================================================================


class TestBackendRegistry:
    def test_adk_registered_by_default(self):
        from adk_fluent.backends import available_backends

        assert "adk" in available_backends()

    def test_get_adk_backend(self):
        from adk_fluent.backends import get_backend

        backend = get_backend("adk")
        assert backend.name == "adk"

    def test_get_unknown_raises(self):
        from adk_fluent.backends import get_backend

        with pytest.raises(KeyError, match="No backend registered"):
            get_backend("nonexistent")

    def test_register_custom_backend(self):
        from adk_fluent.backends import (
            _REGISTRY,
            available_backends,
            get_backend,
            register_backend,
        )

        class DummyBackend:
            name = "dummy"

            @property
            def capabilities(self):
                return EngineCapabilities()

            def compile(self, node, config=None):
                return "dummy_compiled"

        register_backend("dummy", lambda **kw: DummyBackend())
        try:
            assert "dummy" in available_backends()
            b = get_backend("dummy")
            assert b.name == "dummy"
            assert b.compile(None) == "dummy_compiled"
        finally:
            _REGISTRY.pop("dummy", None)

    def test_adk_backend_capabilities(self):
        from adk_fluent.backends import get_backend

        backend = get_backend("adk")
        cap = backend.capabilities
        assert cap.streaming is True
        assert cap.durable is False
        assert cap.replay is False
