"""Tests for G guard compilation into builder callbacks."""

from __future__ import annotations

from adk_fluent._guards import G
from adk_fluent.agent import Agent


class TestGuardCompile:
    def test_guard_g_composite_compiles_callbacks(self):
        builder = Agent("test").guard(G.json() | G.length(max=500))
        assert len(builder._callbacks.get("after_model_callback", [])) >= 2

    def test_guard_callable_single_phase_default(self):
        """A raw callable guard registers in exactly one phase (after_model by
        default), not both — the old dual registration double-fired it with
        two incompatible argument shapes."""
        fn = lambda ctx: None  # noqa: E731
        builder = Agent("test").guard(fn)
        assert fn in builder._callbacks.get("after_model_callback", [])
        assert fn not in builder._callbacks.get("before_model_callback", [])

    def test_guard_callable_before_model_when_request_param(self):
        """A callable that takes llm_request (and not llm_response) is a
        pre-model guard and registers only in before_model."""

        def pre_guard(callback_context, llm_request):  # noqa: ARG001
            return None

        builder = Agent("test").guard(pre_guard)
        assert pre_guard in builder._callbacks.get("before_model_callback", [])
        assert pre_guard not in builder._callbacks.get("after_model_callback", [])

    def test_guard_stores_specs(self):
        builder = Agent("test").guard(G.json())
        specs = builder._config.get("_guard_specs", ())
        assert len(specs) >= 1

    def test_guard_composable_with_other_callbacks(self):
        before_fn = lambda ctx, req: req
        builder = Agent("test").before_model(before_fn).guard(G.json())
        assert before_fn in builder._callbacks["before_model_callback"]
        assert len(builder._callbacks["after_model_callback"]) >= 1

    def test_guard_chain_multiple(self):
        builder = Agent("test").guard(G.json()).guard(G.length(max=100))
        assert len(builder._callbacks.get("after_model_callback", [])) >= 2
