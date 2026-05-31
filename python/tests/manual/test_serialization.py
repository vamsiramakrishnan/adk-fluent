"""Tests for serialization: to_dict, to_yaml (inspection-only, no round-trip)."""

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

    def test_pipeline_to_dict(self):
        p = Pipeline("pipe")
        result = p.to_dict()
        assert result["_type"] == "Pipeline"
        assert result["config"]["name"] == "pipe"


class TestFromDictStructural:
    """from_dict/from_yaml do a STRUCTURAL round-trip.

    Type, config scalars, and nested builder topology round-trip. Callables
    (callbacks, guards, tool functions) are serialized as name strings and
    are intentionally NOT restored — the result is a structural skeleton.
    """

    def test_from_dict_available(self):
        assert hasattr(Agent, "from_dict")
        assert hasattr(Agent, "from_yaml")

    def test_agent_round_trip_preserves_config(self):
        agent = Agent("math").model("gemini-2.5-flash").instruct("Do math.").describe("a calculator")
        rebuilt = Agent.from_dict(agent.to_dict())
        assert type(rebuilt).__name__ == "Agent"
        assert rebuilt._config["name"] == "math"
        assert rebuilt._config["model"] == "gemini-2.5-flash"
        assert rebuilt._config["instruction"] == "Do math."
        assert rebuilt._config["description"] == "a calculator"

    def test_pipeline_round_trip_preserves_topology(self):
        pipe = Agent("a", "gemini-2.5-flash") >> Agent("b", "gemini-2.5-flash")
        rebuilt = Pipeline.from_dict(pipe.to_dict())
        assert type(rebuilt).__name__ == "Pipeline"
        sub_names = [s._config.get("name") for s in rebuilt._lists.get("sub_agents", [])]
        assert sub_names == ["a", "b"]

    def test_callables_not_restored(self):
        """Documented limitation: callbacks/tools are name-only, not restored."""
        agent = Agent("a", "gemini-2.5-flash").before_agent(lambda ctx: None)
        rebuilt = Agent.from_dict(agent.to_dict())
        assert not rebuilt._callbacks.get("before_agent_callback")

    def test_yaml_round_trip(self):
        agent = Agent("math", "gemini-2.5-flash").instruct("Do math.")
        rebuilt = Agent.from_yaml(agent.to_yaml())
        assert rebuilt._config["name"] == "math"
        assert rebuilt._config["instruction"] == "Do math."

    def test_round_trip_is_stable(self):
        """to_dict(from_dict(to_dict(x))) must equal to_dict(x) for structure."""
        from adk_fluent import FanOut

        original = (
            FanOut("fan")
            .branch(Agent("web", "gemini-2.5-flash").instruct("Search web."))
            .branch(Agent("papers", "gemini-2.5-flash").instruct("Search papers."))
        )
        d1 = original.to_dict()
        d2 = FanOut.from_dict(d1).to_dict()
        assert d1 == d2

    def test_all_workflow_types_round_trip(self):
        from adk_fluent import FanOut, Loop, Pipeline

        for ctor, payload in (
            (Pipeline, Pipeline("p").step(Agent("a", "gemini-2.5-flash"))),
            (FanOut, FanOut("f").branch(Agent("a", "gemini-2.5-flash"))),
            (Loop, Loop("l").step(Agent("a", "gemini-2.5-flash")).max_iterations(3)),
        ):
            rebuilt = ctor.from_dict(payload.to_dict())
            assert type(rebuilt).__name__ == ctor.__name__
            assert rebuilt._config["name"] == payload._config["name"]


class TestFromNative:
    """from_native() adopts a native ADK object as a fluent builder (inverse of build())."""

    def test_llm_agent_round_trip(self):
        built = Agent("math", "gemini-2.5-flash").instruct("Do math.").describe("calc").build()
        rebuilt = Agent.from_native(built)
        assert type(rebuilt).__name__ == "Agent"
        assert rebuilt._config["name"] == "math"
        assert rebuilt._config["model"] == "gemini-2.5-flash"
        assert rebuilt._config["instruction"] == "Do math."
        assert rebuilt._config["description"] == "calc"

    def test_pipeline_topology_recovered(self):
        from adk_fluent import Pipeline

        built = (
            Pipeline("flow")
            .step(Agent("a", "gemini-2.5-flash").instruct("A"))
            .step(Agent("b", "gemini-2.5-flash").instruct("B"))
            .build()
        )
        rebuilt = Pipeline.from_native(built)
        assert type(rebuilt).__name__ == "Pipeline"
        names = [s._config.get("name") for s in rebuilt._lists.get("sub_agents", [])]
        assert names == ["a", "b"]

    def test_unsupported_type_raises(self):
        import pytest

        with pytest.raises(TypeError):
            Agent.from_native(object())


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
