"""Issue #9 — BuilderError for clear validation failure messages."""

from __future__ import annotations

import pytest

from adk_fluent import Agent, BuilderError


class TestBuilderError:
    """BuilderError should provide clear, structured error messages."""

    def test_invalid_field_type_raises_builder_error(self):
        with pytest.raises(BuilderError) as exc_info:
            Agent("x").model(123).build()
        err = exc_info.value
        assert err.builder_name == "x"
        assert err.builder_type == "Agent"
        assert len(err.field_errors) > 0
        assert any("model" in e for e in err.field_errors)

    def test_builder_error_preserves_original(self):
        with pytest.raises(BuilderError) as exc_info:
            Agent("x").model(123).build()
        assert exc_info.value.__cause__ is not None

    def test_valid_builds_still_work(self):
        agent = Agent("x").model("gemini-2.0-flash").instruct("hi").build()
        assert agent.name == "x"

    def test_error_message_is_readable(self):
        with pytest.raises(BuilderError) as exc_info:
            Agent("x").model(123).build()
        msg = str(exc_info.value)
        assert "Failed to build" in msg
        assert "Agent" in msg

    def test_to_app_wraps_errors(self):
        """to_app() should also raise BuilderError on failure."""
        with pytest.raises(BuilderError):
            Agent("x").model(123).instruct("hi").to_app()
