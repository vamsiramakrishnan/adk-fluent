"""Tests for .run.test() -- builder mechanics only."""

import inspect

from adk_fluent.agent import Agent


class TestInlineTestMechanics:
    def test_method_exists(self):
        """Agent builder exposes .run.test()."""
        builder = Agent("test").instruct("test")
        assert callable(builder.run.test)

    def test_signature_has_prompt(self):
        """test() accepts prompt parameter."""
        builder = Agent("test").instruct("test")
        sig = inspect.signature(builder.run.test)
        assert "prompt" in sig.parameters
