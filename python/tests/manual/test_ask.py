"""Tests for .ask() one-shot execution -- builder mechanics only."""

from adk_fluent.agent import Agent


class TestAskMechanics:
    def test_ask_exists_on_agent(self):
        """Agent builder has .ask() method."""
        builder = Agent("test").instruct("test")
        assert hasattr(builder, "ask")
        assert callable(builder.ask)

    def test_ask_async_exists_on_agent(self):
        """Agent builder has .ask_async() method."""
        builder = Agent("test").instruct("test")
        assert hasattr(builder, "ask_async")
        assert callable(builder.ask_async)
