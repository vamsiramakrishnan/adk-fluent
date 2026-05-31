"""Tests for the .guard() single-phase callable dispatch.

A raw callable guard runs in exactly ONE phase, inferred from its signature
(after_model by default). The old behavior registered it in BOTH phases,
double-firing it with two incompatible argument shapes.
"""

from adk_fluent.agent import Agent


class TestGuardrail:
    """Tests for single-phase guard dispatch."""

    def test_registers_after_model_by_default(self):
        """A callable with no request/response param defaults to after_model only."""
        fn = lambda ctx: None  # noqa: E731
        builder = Agent("test").guard(fn)
        assert builder._callbacks["after_model_callback"] == [fn]
        assert builder._callbacks.get("before_model_callback", []) == []

    def test_returns_self_for_chaining(self):
        """guard returns self for method chaining."""
        fn = lambda ctx: None  # noqa: E731
        builder = Agent("test")
        result = builder.guard(fn)
        assert result is builder

    def test_multiple_guardrails_accumulate(self):
        """Multiple guard calls accumulate in the single (after_model) list."""
        fn1 = lambda ctx: None  # noqa: E731
        fn2 = lambda ctx: None  # noqa: E731
        builder = Agent("test").guard(fn1).guard(fn2)
        assert builder._callbacks["after_model_callback"] == [fn1, fn2]
        assert builder._callbacks.get("before_model_callback", []) == []

    def test_works_alongside_explicit_callbacks(self):
        """guard works alongside explicit before/after callbacks."""
        guard_fn = lambda ctx: "guard"  # noqa: E731
        before_fn = lambda ctx: "before"  # noqa: E731
        after_fn = lambda ctx: "after"  # noqa: E731
        builder = Agent("test").before_model(before_fn).guard(guard_fn).after_model(after_fn)
        assert builder._callbacks["before_model_callback"] == [before_fn]
        assert builder._callbacks["after_model_callback"] == [guard_fn, after_fn]
