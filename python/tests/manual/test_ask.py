"""Tests for .run.ask() one-shot execution -- builder mechanics only."""

from adk_fluent.agent import Agent


class TestAskMechanics:
    def test_ask_exists_on_agent(self):
        """Agent builder exposes .run.ask()."""
        builder = Agent("test").instruct("test")
        assert callable(builder.run.ask)

    def test_ask_async_exists_on_agent(self):
        """Agent builder exposes .run.ask_async()."""
        builder = Agent("test").instruct("test")
        assert callable(builder.run.ask_async)
