"""Tests for .run.session() -- builder mechanics only."""

from adk_fluent.agent import Agent


class TestSessionMechanics:
    def test_session_exists_on_agent(self):
        """Agent builder exposes .run.session()."""
        builder = Agent("test").instruct("test")
        assert callable(builder.run.session)
