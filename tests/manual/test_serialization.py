"""Tests for serialization: to_dict, from_dict, to_yaml, from_yaml."""
from adk_fluent.agent import Agent
from adk_fluent.workflow import Pipeline


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


class TestFromDict:
    def test_roundtrip_config(self):
        agent = Agent("math").model("gemini-2.5-flash").instruct("Do math.")
        data = agent.to_dict()
        restored = Agent.from_dict(data)
        assert restored._config["name"] == "math"
        assert restored._config["model"] == "gemini-2.5-flash"
        assert restored._config["instruction"] == "Do math."

    def test_type_matches(self):
        agent = Agent("math").model("gemini-2.5-flash")
        data = agent.to_dict()
        restored = Agent.from_dict(data)
        assert isinstance(restored, Agent)

    def test_pipeline_roundtrip(self):
        p = Pipeline("pipe")
        data = p.to_dict()
        restored = Pipeline.from_dict(data)
        assert isinstance(restored, Pipeline)
        assert restored._config["name"] == "pipe"


class TestYaml:
    def test_to_yaml_returns_string(self):
        agent = Agent("math").model("gemini-2.5-flash")
        result = agent.to_yaml()
        assert isinstance(result, str)
        assert "math" in result

    def test_yaml_roundtrip(self):
        agent = Agent("math").model("gemini-2.5-flash").instruct("Do math.")
        yaml_str = agent.to_yaml()
        restored = Agent.from_yaml(yaml_str)
        assert restored._config["name"] == "math"
        assert restored._config["model"] == "gemini-2.5-flash"
        assert restored._config["instruction"] == "Do math."
