"""Tests for .run.stream() -- builder mechanics only."""

from adk_fluent.agent import Agent


class TestStreamMechanics:
    def test_stream_exists_on_agent(self):
        """Agent builder exposes .run.stream()."""
        builder = Agent("test").instruct("test")
        assert callable(builder.run.stream)
