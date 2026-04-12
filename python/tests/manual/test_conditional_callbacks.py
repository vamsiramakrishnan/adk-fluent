"""Tests for conditional _if callback methods."""

from adk_fluent.agent import Agent


class TestConditionalCallbacks:
    """Tests for _if conditional callback support."""

    def test_if_true_registers_callback(self):
        """_if(True, fn) registers the callback."""
        fn = lambda ctx: None
        builder = Agent("test").before_model_if(True, fn)
        assert builder._callbacks["before_model_callback"] == [fn]

    def test_if_false_skips_callback(self):
        """_if(False, fn) does not register the callback."""
        fn = lambda ctx: None
        builder = Agent("test").before_model_if(False, fn)
        assert builder._callbacks["before_model_callback"] == []

    def test_returns_self_regardless(self):
        """_if returns self regardless of condition."""
        fn = lambda ctx: None
        builder = Agent("test")
        result_true = builder.before_model_if(True, fn)
        assert result_true is builder
        result_false = builder.after_model_if(False, fn)
        assert result_false is builder

    def test_all_callback_aliases_have_if_variant(self):
        """All callback aliases produce _if methods."""
        fn = lambda ctx: None
        builder = Agent("test")

        # Test every callback alias has an _if variant
        builder.after_model_if(True, fn)
        assert len(builder._callbacks["after_model_callback"]) == 1

        builder.before_tool_if(True, fn)
        assert len(builder._callbacks["before_tool_callback"]) == 1

        builder.after_tool_if(True, fn)
        assert len(builder._callbacks["after_tool_callback"]) == 1

        builder.before_agent_if(True, fn)
        assert len(builder._callbacks["before_agent_callback"]) == 1

        builder.after_agent_if(True, fn)
        assert len(builder._callbacks["after_agent_callback"]) == 1
