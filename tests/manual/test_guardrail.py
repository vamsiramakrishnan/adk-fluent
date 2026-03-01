"""Tests for .guard() dual-callback method."""

from adk_fluent.agent import Agent


class TestGuardrail:
    """Tests for the guard dual-callback behavior."""

    def test_registers_both_before_and_after_model(self):
        """guard registers fn as both before_model_callback and after_model_callback."""
        fn = lambda ctx: None
        builder = Agent("test").guard(fn)
        assert builder._callbacks["before_model_callback"] == [fn]
        assert builder._callbacks["after_model_callback"] == [fn]

    def test_returns_self_for_chaining(self):
        """guard returns self for method chaining."""
        fn = lambda ctx: None
        builder = Agent("test")
        result = builder.guard(fn)
        assert result is builder

    def test_multiple_guardrails_accumulate(self):
        """Multiple guard calls accumulate in both callback lists."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        builder = Agent("test").guard(fn1).guard(fn2)
        assert builder._callbacks["before_model_callback"] == [fn1, fn2]
        assert builder._callbacks["after_model_callback"] == [fn1, fn2]

    def test_works_alongside_explicit_callbacks(self):
        """guard works alongside explicit before/after callbacks."""
        guard_fn = lambda ctx: "guard"
        before_fn = lambda ctx: "before"
        after_fn = lambda ctx: "after"
        builder = Agent("test").before_model(before_fn).guard(guard_fn).after_model(after_fn)
        assert builder._callbacks["before_model_callback"] == [before_fn, guard_fn]
        assert builder._callbacks["after_model_callback"] == [guard_fn, after_fn]
