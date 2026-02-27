"""Tests for the enhanced .explain() method (rich output + v0.9.1 diagnostics)."""

from __future__ import annotations

from unittest.mock import patch

from pydantic import BaseModel

from adk_fluent import Agent


class Intent(BaseModel):
    category: str
    confidence: float


class Resolution(BaseModel):
    ticket_id: str
    status: str


# --- Rich / plain dispatch tests (from master) ---


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


# --- Enhanced explain diagnostics tests (from v0.9.1 branch) ---


def test_explain_shows_model():
    result = Agent("a").model("gemini-2.0-flash").explain()
    assert "gemini-2.0-flash" in result


def test_explain_shows_instruction_preview():
    result = Agent("a").instruct("Classify the intent of the user message.").explain()
    assert "Classify the intent" in result


def test_explain_shows_template_vars():
    result = Agent("a").instruct("Review the {draft} carefully. Optional: {tone?}").explain()
    assert "Template vars" in result or "draft" in result


def test_explain_shows_produces_consumes():
    result = Agent("a").produces(Intent).consumes(Resolution).explain()
    assert "Intent" in result
    assert "Resolution" in result


def test_explain_shows_output_key():
    result = Agent("a").outputs("result").explain()
    assert "result" in result


def test_explain_shows_tools():
    def search_web(query: str) -> str:
        return "result"

    result = Agent("a").tool(search_web).explain()
    assert "search_web" in result


def test_explain_shows_context_strategy():
    from adk_fluent import C

    result = Agent("a").context(C.user_only()).explain()
    assert "user_only" in result


def test_explain_shows_context_window():
    from adk_fluent import C

    result = Agent("a").context(C.window(n=3)).explain()
    assert "window" in result
    assert "3" in result


def test_explain_shows_context_from_state():
    from adk_fluent import C

    result = Agent("a").context(C.from_state("topic", "style")).explain()
    assert "from_state" in result
    assert "topic" in result


def test_explain_shows_contract_issues_in_pipeline():
    pipeline = Agent("a").instruct("Write.") >> Agent("b").instruct("Review the {draft}.")
    result = pipeline.explain()
    # Should show template var error since 'draft' is never produced
    assert "draft" in result
    assert "Contract issues" in result


def test_explain_pipeline_clean():
    pipeline = Agent("a").instruct("Write.").outputs("draft") >> Agent("b").instruct("Review the {draft}.")
    result = pipeline.explain()
    # draft is produced, so no error about it
    assert "ERROR" not in result or "draft" not in result.split("ERROR")[1] if "ERROR" in result else True


def test_explain_no_data_flow():
    result = Agent("a").instruct("Hello").explain()
    assert "no explicit reads/writes declared" in result


def test_explain_structured_output():
    result = (Agent("a") @ Intent).explain()
    assert "Structured output" in result or "Intent" in result
