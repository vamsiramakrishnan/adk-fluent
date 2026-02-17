"""Tests for validate() and explain()."""
import pytest
from adk_fluent.agent import Agent
from adk_fluent.workflow import Pipeline


def _dummy_cb(ctx):
    pass


class TestValidate:
    def test_validate_returns_self_on_valid(self):
        agent = Agent("math").model("gemini-2.5-flash")
        result = agent.validate()
        assert result is agent

    def test_validate_raises_on_invalid(self):
        """Agent with an invalid config field should fail validation."""
        agent = Agent("bad")
        agent._config["totally_invalid_field"] = "oops"
        with pytest.raises(ValueError):
            agent.validate()

    def test_validate_is_chainable(self):
        agent = Agent("math").model("gemini-2.5-flash")
        result = agent.validate().instruct("Do math.")
        assert result._config["instruction"] == "Do math."


class TestExplain:
    def test_explain_returns_string(self):
        agent = Agent("math").model("gemini-2.5-flash")
        result = agent.explain()
        assert isinstance(result, str)

    def test_explain_shows_name(self):
        agent = Agent("math").model("gemini-2.5-flash")
        result = agent.explain()
        assert "math" in result

    def test_explain_shows_fields(self):
        agent = Agent("math").model("gemini-2.5-flash").instruct("Do math.")
        result = agent.explain()
        assert "model" in result
        assert "instruction" in result

    def test_explain_shows_callback_count(self):
        agent = Agent("math").model("gemini-2.5-flash").before_model(_dummy_cb)
        result = agent.explain()
        assert "callback" in result.lower()
        assert "1" in result

    def test_explain_shows_list_count(self):
        agent = Agent("math").model("gemini-2.5-flash").tool(lambda: None)
        result = agent.explain()
        assert "tools" in result
        assert "1" in result
