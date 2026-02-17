"""Tests for variadic callback methods."""

from adk_fluent.agent import Agent


class TestVariadicCallbacks:
    """Tests for *fns variadic callback support."""

    def test_single_callback_still_works(self):
        """Passing a single callback to a variadic method works as before."""
        fn = lambda ctx: None
        builder = Agent("test").before_model(fn)
        assert builder._callbacks["before_model_callback"] == [fn]

    def test_multiple_callbacks_in_one_call(self):
        """.before_model(fn1, fn2, fn3) registers all three."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        fn3 = lambda ctx: None
        builder = Agent("test").before_model(fn1, fn2, fn3)
        assert builder._callbacks["before_model_callback"] == [fn1, fn2, fn3]

    def test_variadic_chaining(self):
        """Variadic calls chain with subsequent calls."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        fn3 = lambda ctx: None
        builder = (
            Agent("test")
            .before_model(fn1)
            .before_model(fn2, fn3)
        )
        assert builder._callbacks["before_model_callback"] == [fn1, fn2, fn3]

    def test_returns_self(self):
        """Variadic callback method returns builder for chaining."""
        fn = lambda ctx: None
        builder = Agent("test")
        result = builder.before_model(fn)
        assert result is builder
