"""Tests for .session() -- builder mechanics only."""
from adk_fluent.agent import Agent


class TestSessionMechanics:
    def test_session_exists_on_agent(self):
        """Agent builder has .session() method."""
        builder = Agent("test").instruct("test")
        assert hasattr(builder, "session")
        assert callable(builder.session)
