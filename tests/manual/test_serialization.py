"""Tests for serialization: to_dict, to_yaml (inspection-only, no round-trip)."""
from adk_fluent.agent import Agent
from adk_fluent.workflow import Pipeline
import pytest


def _my_callback(ctx):
    pass


class TestToDict:
    def test_returns_dict(self):
        agent = Agent("math").model("gemini-2.5-flash")
        result = agent.to_dict()
        assert isinstance(result, dict)

    def test_includes_type(self):
        agent = Agent("math").model("gemini-2.5-flash")
        result = agent.to_dict()
        assert result["_type"] == "Agent"

    def test_includes_config_fields(self):
        agent = Agent("math").model("gemini-2.5-flash").instruct("Do math.")
        result = agent.to_dict()
        assert result["config"]["model"] == "gemini-2.5-flash"
        assert result["config"]["instruction"] == "Do math."
        assert result["config"]["name"] == "math"

    def test_includes_callback_qualnames(self):
        agent = Agent("math").model("gemini-2.5-flash").before_model(_my_callback)
        result = agent.to_dict()
        assert "before_model_callback" in result["callbacks"]
        assert "_my_callback" in result["callbacks"]["before_model_callback"][0]

    def test_excludes_internal_fields(self):
        agent = Agent("math").model("gemini-2.5-flash")
        agent._config["_internal"] = "secret"
        result = agent.to_dict()
        assert "_internal" not in result["config"]

    def test_pipeline_to_dict(self):
        p = Pipeline("pipe")
        result = p.to_dict()
        assert result["_type"] == "Pipeline"
        assert result["config"]["name"] == "pipe"


class TestFromDictRemoved:
    """from_dict and from_yaml were removed: they can't round-trip callables."""

    def test_from_dict_not_available(self):
        assert not hasattr(Agent, "from_dict")

    def test_from_yaml_not_available(self):
        assert not hasattr(Agent, "from_yaml")


class TestYaml:
    def test_to_yaml_returns_string(self):
        agent = Agent("math").model("gemini-2.5-flash")
        result = agent.to_yaml()
        assert isinstance(result, str)
        assert "math" in result

    def test_to_yaml_includes_config(self):
        agent = Agent("math").model("gemini-2.5-flash").instruct("Do math.")
        result = agent.to_yaml()
        assert "gemini-2.5-flash" in result
        assert "Do math." in result
