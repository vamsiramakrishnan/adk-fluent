"""Tests for with_() immutable variants."""
from adk_fluent.agent import Agent


class TestWith:
    def test_returns_new_builder(self):
        agent = Agent("math").model("gemini-2.5-flash")
        new_agent = agent.with_(model="gemini-2.5-pro")
        assert new_agent is not agent

    def test_overrides_field(self):
        agent = Agent("math").model("gemini-2.5-flash")
        new_agent = agent.with_(model="gemini-2.5-pro")
        assert new_agent._config["model"] == "gemini-2.5-pro"

    def test_original_unchanged(self):
        agent = Agent("math").model("gemini-2.5-flash")
        agent.with_(model="gemini-2.5-pro")
        assert agent._config["model"] == "gemini-2.5-flash"

    def test_name_override(self):
        agent = Agent("math").model("gemini-2.5-flash")
        new_agent = agent.with_(name="science")
        assert new_agent._config["name"] == "science"
        assert agent._config["name"] == "math"

    def test_preserves_existing_config(self):
        agent = Agent("math").model("gemini-2.5-flash").instruct("Do math.")
        new_agent = agent.with_(model="gemini-2.5-pro")
        assert new_agent._config["instruction"] == "Do math."
        assert new_agent._config["model"] == "gemini-2.5-pro"

    def test_resolves_aliases(self):
        """with_(instruct=...) should set instruction."""
        agent = Agent("math").model("gemini-2.5-flash")
        new_agent = agent.with_(instruct="Do science.")
        assert new_agent._config["instruction"] == "Do science."
