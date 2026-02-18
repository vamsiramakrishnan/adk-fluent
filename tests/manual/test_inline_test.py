"""Tests for .test() -- builder mechanics only."""

import inspect

from adk_fluent.agent import Agent


class TestInlineTestMechanics:
    def test_method_exists(self):
        """Agent builder has .test() method."""
        builder = Agent("test").instruct("test")
        assert hasattr(builder, "test")
        assert callable(builder.test)

    def test_signature_has_prompt(self):
        """test() accepts prompt parameter."""
        builder = Agent("test").instruct("test")
        sig = inspect.signature(builder.test)
        assert "prompt" in sig.parameters
