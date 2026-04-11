"""Tests for G guard compilation into builder callbacks."""

from __future__ import annotations

from adk_fluent._guards import G
from adk_fluent.agent import Agent


class TestGuardCompile:
    def test_guard_g_composite_compiles_callbacks(self):
        builder = Agent("test").guard(G.json() | G.length(max=500))
        assert len(builder._callbacks.get("after_model_callback", [])) >= 2

    def test_guard_callable_backwards_compatible(self):
        fn = lambda ctx: None
        builder = Agent("test").guard(fn)
        assert fn in builder._callbacks.get("before_model_callback", [])
        assert fn in builder._callbacks.get("after_model_callback", [])

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
