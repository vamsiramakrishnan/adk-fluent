"""Tests for Phase 7 — wiring: .engine(), .compute(), configure(), top-level exports."""

import pytest

from adk_fluent import (
    Agent,
    CompilationResult,
    ComputeConfig,
    EngineCapabilities,
    configure,
    get_config,
    reset_config,
)
from adk_fluent import (
    compile as compile_ir,
)
from adk_fluent._ir_generated import AgentNode

# ======================================================================
# Global configure() / reset_config() / get_config()
# ======================================================================


class TestConfigure:
    def setup_method(self):
        reset_config()

    def teardown_method(self):
        reset_config()

    def test_configure_engine(self):
        configure(engine="asyncio")
        cfg = get_config()
        assert cfg["engine"] == "asyncio"

    def test_configure_engine_config(self):
        configure(engine="temporal", engine_config={"task_queue": "my-queue"})
        cfg = get_config()
        assert cfg["engine"] == "temporal"
        assert cfg["engine_config"]["task_queue"] == "my-queue"

    def test_configure_compute(self):
        cc = ComputeConfig(model_provider="gemini-2.5-flash")
        configure(compute=cc)
        cfg = get_config()
        assert cfg["compute"].model_provider == "gemini-2.5-flash"

    def test_reset_config(self):
        configure(engine="temporal")
        reset_config()
        assert get_config() == {}

    def test_configure_partial_update(self):
        configure(engine="asyncio")
        configure(compute=ComputeConfig())
        cfg = get_config()
        assert cfg["engine"] == "asyncio"
        assert "compute" in cfg

    def test_get_config_returns_copy(self):
        configure(engine="asyncio")
        cfg = get_config()
        cfg["engine"] = "modified"
        assert get_config()["engine"] == "asyncio"


# ======================================================================
# Builder .engine() and .compute()
# ======================================================================


class TestBuilderEngine:
    def test_engine_sets_config(self):
        agent = Agent("test", "gemini-2.5-flash").engine("asyncio")
        assert agent._config["_engine"] == "asyncio"

    def test_engine_with_kwargs(self):
        agent = Agent("test").engine("temporal", task_queue="my-queue")
        assert agent._config["_engine"] == "temporal"
        assert agent._config["_engine_kwargs"]["task_queue"] == "my-queue"

    def test_compute_sets_config(self):
        cc = ComputeConfig(model_provider="gemini-2.5-flash")
        agent = Agent("test").compute(cc)
        assert agent._config["_compute"] is cc

    def test_engine_chainable(self):
        agent = Agent("test", "gemini-2.5-flash").instruct("Hello").engine("asyncio").compute(ComputeConfig())
        assert agent._config["_engine"] == "asyncio"
        assert "_compute" in agent._config


# ======================================================================
# Top-level exports
# ======================================================================


class TestTopLevelExports:
    def test_compile_ir_export(self):
        """compile_ir is callable."""
        assert callable(compile_ir)

    def test_compilation_result_export(self):
        """CompilationResult is importable."""
        assert CompilationResult is not None

    def test_engine_capabilities_export(self):
        """EngineCapabilities is importable."""
        cap = EngineCapabilities()
        assert cap.durable is False

    def test_compute_config_export(self):
        """ComputeConfig is importable."""
        cc = ComputeConfig()
        assert cc.model_provider is None


# ======================================================================
# compile_ir() with backend selection
# ======================================================================


class TestCompileIR:
    def test_compile_to_asyncio(self):
        ir = AgentNode(name="test")
        result = compile_ir(ir, backend="asyncio")
        assert result.backend_name == "asyncio"
        assert result.capabilities.durable is False

    def test_compile_to_temporal(self):
        ir = AgentNode(name="test")
        result = compile_ir(ir, backend="temporal")
        assert result.backend_name == "temporal"
        assert result.capabilities.durable is True

    def test_compile_to_adk(self):
        ir = AgentNode(name="test", model="gemini-2.5-flash")
        result = compile_ir(ir, backend="adk")
        assert result.backend_name == "adk"

    def test_compile_unknown_backend_raises(self):
        ir = AgentNode(name="test")
        with pytest.raises(KeyError, match="No backend registered"):
            compile_ir(ir, backend="nonexistent")
