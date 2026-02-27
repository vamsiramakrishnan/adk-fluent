"""Issue #11 — Rich .explain() output tests."""

from __future__ import annotations

from unittest.mock import patch

from adk_fluent import Agent


class TestExplain:
    """explain() should return string in both rich and plain modes."""

    def test_explain_returns_string(self):
        result = Agent("x").model("gemini-2.0-flash").instruct("hi").explain()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_explain_contains_builder_info(self):
        result = Agent("x").model("gemini-2.0-flash").instruct("hi").explain()
        assert "Agent" in result
        assert "x" in result

    def test_plain_fallback_when_rich_unavailable(self):
        with patch.dict("sys.modules", {"rich": None, "rich.console": None, "rich.tree": None}):
            result = Agent("x").model("gemini-2.0-flash")._explain_plain()
            assert isinstance(result, str)
            assert "Agent" in result


class TestInspect:
    """inspect() should show full config values."""

    def test_inspect_returns_string(self):
        result = Agent("x").model("gemini-2.0-flash").instruct("hi").inspect()
        assert isinstance(result, str)

    def test_inspect_shows_actual_values(self):
        result = Agent("x").model("gemini-2.0-flash").instruct("hi").inspect()
        assert "gemini-2.0-flash" in result
        assert "hi" in result

    def test_inspect_shows_field_names(self):
        result = Agent("x").model("gemini-2.0-flash").instruct("hi").inspect()
        # Should show the fluent alias name (via _reverse_alias)
        assert "model" in result or "instruct" in result
