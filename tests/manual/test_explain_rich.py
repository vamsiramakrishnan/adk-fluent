"""Tests for the enhanced .explain() method (v0.9.1 diagnostics)."""

import re

import pytest
from pydantic import BaseModel


class Intent(BaseModel):
    category: str
    confidence: float


class Resolution(BaseModel):
    ticket_id: str
    status: str


def test_explain_shows_model():
    from adk_fluent import Agent

    result = Agent("a").model("gemini-2.0-flash").explain()
    assert "gemini-2.0-flash" in result


def test_explain_shows_instruction_preview():
    from adk_fluent import Agent

    result = Agent("a").instruct("Classify the intent of the user message.").explain()
    assert "Classify the intent" in result


def test_explain_shows_template_vars():
    from adk_fluent import Agent

    result = Agent("a").instruct("Review the {draft} carefully. Optional: {tone?}").explain()
    assert "Template vars" in result
    assert "draft" in result
    assert "tone" in result


def test_explain_shows_produces_consumes():
    from adk_fluent import Agent

    result = Agent("a").produces(Intent).consumes(Resolution).explain()
    assert "Intent" in result
    assert "Resolution" in result
    assert "category" in result
    assert "ticket_id" in result


def test_explain_shows_output_key():
    from adk_fluent import Agent

    result = Agent("a").outputs("result").explain()
    assert "output_key='result'" in result


def test_explain_shows_tools():
    from adk_fluent import Agent

    def search_web(query: str) -> str:
        return "result"

    result = Agent("a").tool(search_web).explain()
    assert "search_web" in result
    assert "Tools" in result


def test_explain_shows_context_strategy():
    from adk_fluent import Agent, C

    result = Agent("a").context(C.user_only()).explain()
    assert "user_only" in result


def test_explain_shows_context_window():
    from adk_fluent import Agent, C

    result = Agent("a").context(C.window(n=3)).explain()
    assert "window" in result
    assert "3" in result


def test_explain_shows_context_from_state():
    from adk_fluent import Agent, C

    result = Agent("a").context(C.from_state("topic", "style")).explain()
    assert "from_state" in result
    assert "topic" in result


def test_explain_shows_contract_issues_in_pipeline():
    from adk_fluent import Agent

    pipeline = Agent("a").instruct("Write.") >> Agent("b").instruct("Review the {draft}.")
    result = pipeline.explain()
    # Should show template var error since 'draft' is never produced
    assert "draft" in result
    assert "Contract issues" in result


def test_explain_pipeline_clean():
    from adk_fluent import Agent

    pipeline = Agent("a").instruct("Write.").outputs("draft") >> Agent("b").instruct("Review the {draft}.")
    result = pipeline.explain()
    # draft is produced, so no error about it
    assert "ERROR" not in result or "draft" not in result.split("ERROR")[1] if "ERROR" in result else True


def test_explain_no_data_flow():
    from adk_fluent import Agent

    result = Agent("a").instruct("Hello").explain()
    assert "no explicit reads/writes declared" in result


def test_explain_structured_output():
    from adk_fluent import Agent

    result = (Agent("a") @ Intent).explain()
    assert "Structured output" in result
    assert "Intent" in result
