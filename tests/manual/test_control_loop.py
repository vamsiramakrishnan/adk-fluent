"""Tests for control loop DevEx improvements: aliases, delegate, dict >> routing."""
import pytest
from adk_fluent import Agent, Pipeline


class TestOutputsAlias:
    """Tests for .outputs() alias for output_key."""

    def test_outputs_sets_output_key(self):
        """outputs() is an alias for output_key."""
        agent = Agent("step1").model("gemini-2.5-flash").outputs("result")
        assert agent._config["output_key"] == "result"

    def test_outputs_returns_self(self):
        """outputs() returns self for chaining."""
        agent = Agent("step1")
        result = agent.outputs("x")
        assert result is agent

    def test_outputs_in_chain(self):
        """outputs() works in a fluent chain."""
        agent = (
            Agent("step1")
            .model("gemini-2.5-flash")
            .instruct("Classify the input.")
            .outputs("classification")
        )
        assert agent._config["output_key"] == "classification"
        assert agent._config["instruction"] == "Classify the input."


class TestHistoryAlias:
    """Tests for .history() alias for include_contents."""

    def test_history_sets_include_contents(self):
        """history() is an alias for include_contents."""
        agent = Agent("a").history("none")
        assert agent._config["include_contents"] == "none"

    def test_history_returns_self(self):
        """history() returns self for chaining."""
        agent = Agent("a")
        result = agent.history("none")
        assert result is agent


class TestDelegateMethod:
    """Tests for .delegate() method."""

    def test_delegate_adds_to_tools_list(self):
        """delegate() adds the agent to the tools list."""
        specialist = Agent("specialist").model("gemini-2.5-flash").instruct("You help.")
        coordinator = Agent("coordinator").model("gemini-2.5-flash").delegate(specialist)
        # delegate adds to _lists["tools"]
        assert len(coordinator._lists.get("tools", [])) == 1

    def test_delegate_returns_self(self):
        """delegate() returns self for chaining."""
        specialist = Agent("spec").model("gemini-2.5-flash")
        coordinator = Agent("coord").model("gemini-2.5-flash")
        result = coordinator.delegate(specialist)
        assert result is coordinator

    def test_multiple_delegates(self):
        """Multiple delegate() calls accumulate."""
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        coordinator = (
            Agent("router")
            .model("gemini-2.5-flash")
            .delegate(a)
            .delegate(b)
        )
        assert len(coordinator._lists.get("tools", [])) == 2


class TestDictRouting:
    """Tests for dict >> conditional routing syntax (deterministic Route)."""

    def test_dict_creates_pipeline(self):
        """agent >> dict creates a Pipeline."""
        classifier = Agent("classify").model("gemini-2.5-flash").outputs("intent")
        booker = Agent("booker").model("gemini-2.5-flash")
        info = Agent("info").model("gemini-2.5-flash")

        result = classifier >> {"booking": booker, "info": info}
        assert isinstance(result, Pipeline)

    def test_dict_requires_outputs(self):
        """dict >> raises ValueError if left side has no output_key."""
        classifier = Agent("classify").model("gemini-2.5-flash")  # No .outputs()
        with pytest.raises(ValueError, match="must have .outputs"):
            classifier >> {"a": Agent("x")}

    def test_dict_pipeline_has_two_steps(self):
        """The resulting Pipeline has classifier + route_agent as sub_agents."""
        classifier = Agent("classify").model("gemini-2.5-flash").outputs("intent")
        result = classifier >> {"a": Agent("x").model("gemini-2.5-flash").instruct("X"), "b": Agent("y").model("gemini-2.5-flash").instruct("Y")}
        # Pipeline has 2 items in sub_agents list (classifier builder + built route agent)
        assert len(result._lists.get("sub_agents", [])) == 2

    def test_dict_route_agent_has_sub_agents(self):
        """The route agent has the dict values as sub_agents."""
        from google.adk.agents.base_agent import BaseAgent
        classifier = Agent("classify").model("gemini-2.5-flash").outputs("intent")
        a = Agent("handler_a").model("gemini-2.5-flash").instruct("A")
        b = Agent("handler_b").model("gemini-2.5-flash").instruct("B")

        pipeline = classifier >> {"opt_a": a, "opt_b": b}
        # The second step is the built route agent (BaseAgent, not builder)
        route_agent = pipeline._lists["sub_agents"][1]
        assert isinstance(route_agent, BaseAgent)
        assert len(route_agent.sub_agents) == 2

    def test_dict_route_is_deterministic(self):
        """The route agent is a deterministic BaseAgent, NOT an LLM-based coordinator."""
        from google.adk.agents.llm_agent import LlmAgent
        classifier = Agent("classify").model("gemini-2.5-flash").outputs("intent")
        pipeline = classifier >> {"booking": Agent("booker").model("gemini-2.5-flash").instruct("B"), "info": Agent("info_agent").model("gemini-2.5-flash").instruct("I")}
        route_agent = pipeline._lists["sub_agents"][1]
        # Should NOT be an LlmAgent (deterministic routing, no LLM)
        assert not isinstance(route_agent, LlmAgent)

    def test_dict_followed_by_more_steps(self):
        """dict routing can be followed by more >> steps."""
        classifier = Agent("classify").model("gemini-2.5-flash").outputs("intent")
        formatter = Agent("formatter").model("gemini-2.5-flash")

        result = (classifier >> {"a": Agent("x").model("gemini-2.5-flash").instruct("X"), "b": Agent("y").model("gemini-2.5-flash").instruct("Y")}) >> formatter
        # Should be a Pipeline with 3 steps
        assert isinstance(result, Pipeline)
        assert len(result._lists.get("sub_agents", [])) == 3
