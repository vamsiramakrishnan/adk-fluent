"""Tests for .stream() -- builder mechanics only."""
from adk_fluent.agent import Agent


class TestStreamMechanics:
    def test_stream_exists_on_agent(self):
        """Agent builder has .stream() method."""
        builder = Agent("test").instruct("test")
        assert hasattr(builder, "stream")
        assert callable(builder.stream)
