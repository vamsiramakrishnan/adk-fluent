"""Tests for the complete expression language: Route, proceed_if, loop_until."""

import pytest

from adk_fluent import Agent, Pipeline
from adk_fluent._routing import Route, _make_checkpoint_agent, _make_route_agent
from adk_fluent.workflow import Loop

# ======================================================================
# Route -- Deterministic Branching
# ======================================================================


class TestRouteBuilder:
    """Tests for the Route fluent builder."""

    def test_route_eq_single_rule(self):
        """Route with a single eq rule."""
        a = Agent("handler_a").model("gemini-2.5-flash")
        route = Route("key").eq("x", a)
        assert len(route._rules) == 1
        assert route._default is None

    def test_route_eq_multiple_rules(self):
        """Route with multiple eq rules."""
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        route = Route("key").eq("x", a).eq("y", b)
        assert len(route._rules) == 2

    def test_route_contains(self):
        """Route with contains predicate."""
        a = Agent("handler").model("gemini-2.5-flash")
        route = Route("text").contains("urgent", a)
        assert len(route._rules) == 1
        # Verify the predicate works
        pred = route._rules[0][0]
        assert pred({"text": "this is urgent!"}) is True
        assert pred({"text": "no rush"}) is False

    def test_route_gt(self):
        """Route with gt predicate."""
        a = Agent("premium").model("gemini-2.5-flash")
        route = Route("score").gt(0.8, a)
        pred = route._rules[0][0]
        assert pred({"score": 0.9}) is True
        assert pred({"score": 0.5}) is False

    def test_route_lt(self):
        """Route with lt predicate."""
        a = Agent("basic").model("gemini-2.5-flash")
        route = Route("score").lt(0.3, a)
        pred = route._rules[0][0]
        assert pred({"score": 0.1}) is True
        assert pred({"score": 0.5}) is False

    def test_route_when_lambda(self):
        """Route with custom when predicate."""
        a = Agent("handler").model("gemini-2.5-flash")
        route = Route().when(lambda s: s.get("x") == "yes" and s.get("y", 0) > 5, a)
        assert len(route._rules) == 1
        pred = route._rules[0][0]
        assert pred({"x": "yes", "y": 10}) is True
        assert pred({"x": "yes", "y": 2}) is False
        assert pred({"x": "no", "y": 10}) is False

    def test_route_otherwise(self):
        """Route with otherwise default."""
        a = Agent("a").model("gemini-2.5-flash")
        default = Agent("default").model("gemini-2.5-flash")
        route = Route("key").eq("x", a).otherwise(default)
        assert route._default is default

    def test_route_chained(self):
        """Full Route chain with multiple predicates and otherwise."""
        premium = Agent("premium").model("gemini-2.5-flash")
        standard = Agent("standard").model("gemini-2.5-flash")
        basic = Agent("basic").model("gemini-2.5-flash")
        route = Route("score").gt(0.8, premium).gt(0.5, standard).otherwise(basic)
        assert len(route._rules) == 2
        assert route._default is basic

    def test_route_eq_requires_key(self):
        """Route().eq() without key raises ValueError."""
        with pytest.raises(ValueError, match="requires a key"):
            Route().eq("x", Agent("a"))

    def test_route_contains_requires_key(self):
        """Route().contains() without key raises ValueError."""
        with pytest.raises(ValueError, match="requires a key"):
            Route().contains("x", Agent("a"))

    def test_route_gt_requires_key(self):
        """Route().gt() without key raises ValueError."""
        with pytest.raises(ValueError, match="requires a key"):
            Route().gt(0.5, Agent("a"))

    def test_route_lt_requires_key(self):
        """Route().lt() without key raises ValueError."""
        with pytest.raises(ValueError, match="requires a key"):
            Route().lt(0.5, Agent("a"))

    def test_route_when_no_key_needed(self):
        """Route().when() does NOT require a key."""
        a = Agent("a").model("gemini-2.5-flash")
        route = Route().when(lambda s: True, a)  # No error
        assert len(route._rules) == 1


class TestRouteBuild:
    """Tests for Route.build() producing a BaseAgent."""

    def test_route_build_returns_base_agent(self):
        """Route.build() returns a BaseAgent instance."""
        from google.adk.agents.base_agent import BaseAgent

        a = Agent("a").model("gemini-2.5-flash").instruct("A")
        b = Agent("b").model("gemini-2.5-flash").instruct("B")
        route = Route("key").eq("x", a).eq("y", b)
        result = route.build()
        assert isinstance(result, BaseAgent)

    def test_route_build_has_sub_agents(self):
        """Route.build() collects all branch agents as sub_agents."""
        a = Agent("a").model("gemini-2.5-flash").instruct("A")
        b = Agent("b").model("gemini-2.5-flash").instruct("B")
        route = Route("key").eq("x", a).eq("y", b)
        result = route.build()
        assert len(result.sub_agents) == 2

    def test_route_build_with_otherwise_has_all_sub_agents(self):
        """Route.build() includes otherwise agent in sub_agents."""
        a = Agent("a").model("gemini-2.5-flash").instruct("A")
        default = Agent("default").model("gemini-2.5-flash").instruct("D")
        route = Route("key").eq("x", a).otherwise(default)
        result = route.build()
        assert len(result.sub_agents) == 2

    def test_route_build_name(self):
        """Route.build() name includes the key."""
        a = Agent("a").model("gemini-2.5-flash").instruct("A")
        route = Route("intent").eq("x", a)
        result = route.build()
        assert "intent" in result.name

    def test_route_build_auto_builds_sub_builders(self):
        """Route.build() auto-builds sub-agent builders."""
        from google.adk.agents.llm_agent import LlmAgent

        a = Agent("a").model("gemini-2.5-flash").instruct("A")
        route = Route("key").eq("x", a)
        result = route.build()
        # Sub-agents should be built LlmAgent instances, not builders
        for sub in result.sub_agents:
            assert isinstance(sub, LlmAgent)


class TestRouteRepr:
    """Tests for Route.__repr__."""

    def test_route_repr_with_key(self):
        a = Agent("a").model("gemini-2.5-flash")
        route = Route("intent").eq("x", a)
        r = repr(route)
        assert "intent" in r
        assert "1 rules" in r

    def test_route_repr_without_key(self):
        a = Agent("a").model("gemini-2.5-flash")
        route = Route().when(lambda s: True, a)
        r = repr(route)
        assert "multi-key" in r

    def test_route_repr_with_otherwise(self):
        a = Agent("a").model("gemini-2.5-flash")
        route = Route("k").eq("x", a).otherwise(a)
        r = repr(route)
        assert "otherwise" in r


# ======================================================================
# Route >> Integration with Pipeline Operators
# ======================================================================


class TestRouteOperatorIntegration:
    """Tests for Route with >> operator."""

    def test_agent_rshift_route_creates_pipeline(self):
        """agent >> Route creates a Pipeline."""
        classifier = Agent("classify").model("gemini-2.5-flash").outputs("intent")
        a = Agent("a").model("gemini-2.5-flash").instruct("A")
        b = Agent("b").model("gemini-2.5-flash").instruct("B")
        route = Route("intent").eq("x", a).eq("y", b)

        result = classifier >> route
        assert isinstance(result, Pipeline)

    def test_agent_rshift_route_has_correct_sub_agents(self):
        """Pipeline from agent >> Route has classifier + route_agent."""
        classifier = Agent("classify").model("gemini-2.5-flash").outputs("intent")
        a = Agent("a").model("gemini-2.5-flash").instruct("A")
        route = Route("intent").eq("x", a)

        result = classifier >> route
        sub_agents = result._lists.get("sub_agents", [])
        assert len(sub_agents) == 2
        # First is the classifier builder
        assert sub_agents[0] is classifier
        # Second is the Route object (built lazily at .build() time)
        assert isinstance(sub_agents[1], Route)
        # When built, it becomes a proper BaseAgent
        from google.adk.agents.base_agent import BaseAgent

        built = result.build()
        assert isinstance(built.sub_agents[1], BaseAgent)

    def test_dict_rshift_uses_route(self):
        """agent >> dict creates deterministic Route (not LLM coordinator)."""
        from google.adk.agents.base_agent import BaseAgent

        classifier = Agent("classify").model("gemini-2.5-flash").outputs("intent")
        a = Agent("a").model("gemini-2.5-flash").instruct("A")
        b = Agent("b").model("gemini-2.5-flash").instruct("B")

        result = classifier >> {"opt_a": a, "opt_b": b}
        assert isinstance(result, Pipeline)
        sub_agents = result._lists.get("sub_agents", [])
        assert len(sub_agents) == 2
        # Second element is a Route object (built lazily at .build() time)
        assert isinstance(sub_agents[1], Route)
        # When built, route agent has correct sub-agents
        built = result.build()
        assert isinstance(built.sub_agents[1], BaseAgent)
        assert len(built.sub_agents[1].sub_agents) == 2

    def test_dict_rshift_requires_outputs(self):
        """agent >> dict raises ValueError without .outputs()."""
        classifier = Agent("classify").model("gemini-2.5-flash")
        with pytest.raises(ValueError, match="must have .outputs"):
            classifier >> {"a": Agent("x")}

    def test_route_followed_by_more_steps(self):
        """Route can be followed by more >> steps."""
        classifier = Agent("classify").model("gemini-2.5-flash").outputs("intent")
        a = Agent("a").model("gemini-2.5-flash").instruct("A")
        formatter = Agent("formatter").model("gemini-2.5-flash")

        result = (classifier >> Route("intent").eq("x", a)) >> formatter
        assert isinstance(result, Pipeline)
        assert len(result._lists.get("sub_agents", [])) == 3


# ======================================================================
# proceed_if -- Conditional Gating
# ======================================================================


class TestProceedIf:
    """Tests for proceed_if conditional gating."""

    def test_proceed_if_registers_callback(self):
        """proceed_if() registers a before_agent_callback."""
        agent = Agent("a").model("gemini-2.5-flash")
        agent.proceed_if(lambda s: s.get("valid") == "yes")
        assert len(agent._callbacks["before_agent_callback"]) == 1

    def test_proceed_if_returns_self(self):
        """proceed_if() returns self for chaining."""
        agent = Agent("a").model("gemini-2.5-flash")
        result = agent.proceed_if(lambda s: True)
        assert result is agent

    def test_proceed_if_in_chain(self):
        """proceed_if() works in a fluent chain."""
        agent = (
            Agent("enricher")
            .model("gemini-2.5-flash")
            .instruct("Enrich the input.")
            .proceed_if(lambda s: s.get("valid") == "yes")
        )
        assert agent._config["instruction"] == "Enrich the input."
        assert len(agent._callbacks["before_agent_callback"]) == 1

    def test_proceed_if_callback_skips_when_false(self):
        """The gate callback returns Content (skip signal) when predicate is False."""
        agent = Agent("a").model("gemini-2.5-flash")
        agent.proceed_if(lambda s: s.get("valid") == "yes")

        cb = agent._callbacks["before_agent_callback"][0]

        # Simulate callback_context with state where valid != "yes"
        class FakeContext:
            class state:
                @staticmethod
                def get(key, default=None):
                    return {"valid": "no"}.get(key, default)

        result = cb(callback_context=FakeContext())
        assert result is not None  # Returns Content -- agent should be skipped

    def test_proceed_if_callback_proceeds_when_true(self):
        """The gate callback returns None (proceed signal) when predicate is True."""
        agent = Agent("a").model("gemini-2.5-flash")
        agent.proceed_if(lambda s: s.get("valid") == "yes")

        cb = agent._callbacks["before_agent_callback"][0]

        class FakeContext:
            class state:
                @staticmethod
                def get(key, default=None):
                    return {"valid": "yes"}.get(key, default)

        result = cb(callback_context=FakeContext())
        assert result is None  # Returns None -- agent should proceed

    def test_proceed_if_multiple_gates(self):
        """Multiple proceed_if() calls accumulate callbacks."""
        agent = Agent("a").model("gemini-2.5-flash").proceed_if(lambda s: s.get("x")).proceed_if(lambda s: s.get("y"))
        assert len(agent._callbacks["before_agent_callback"]) == 2

    def test_proceed_if_in_pipeline(self):
        """proceed_if works with >> pipeline composition."""
        validator = Agent("validate").model("gemini-2.5-flash").outputs("valid")
        enricher = Agent("enrich").model("gemini-2.5-flash").proceed_if(lambda s: s.get("valid") == "yes")
        formatter = Agent("format").model("gemini-2.5-flash")

        flow = validator >> enricher >> formatter
        assert isinstance(flow, Pipeline)
        assert len(flow._lists.get("sub_agents", [])) == 3

    def test_proceed_if_callback_handles_exception(self):
        """The gate callback handles predicate exceptions by skipping."""
        agent = Agent("a").model("gemini-2.5-flash")
        agent.proceed_if(lambda s: s["nonexistent_key"] > 5)  # Will raise KeyError

        cb = agent._callbacks["before_agent_callback"][0]

        class FakeContext:
            class state:
                @staticmethod
                def get(key, default=None):
                    return {}.get(key, default)

                def __getitem__(self, key):
                    raise KeyError(key)

        result = cb(callback_context=FakeContext())
        assert result is not None  # Should skip on exception


# ======================================================================
# loop_until -- Conditional Loop Exit
# ======================================================================


class TestLoopUntil:
    """Tests for loop_until conditional loop exit."""

    def test_loop_until_creates_loop(self):
        """loop_until() creates a Loop builder."""
        agent = Agent("writer").model("gemini-2.5-flash")
        result = agent.loop_until(lambda s: s.get("done"))
        assert isinstance(result, Loop)

    def test_loop_until_sets_max_iterations(self):
        """loop_until() sets max_iterations."""
        agent = Agent("writer").model("gemini-2.5-flash")
        result = agent.loop_until(lambda s: True, max_iterations=5)
        assert result._config["max_iterations"] == 5

    def test_loop_until_stores_predicate(self):
        """loop_until() stores the until predicate."""
        pred = lambda s: s.get("done")
        agent = Agent("writer").model("gemini-2.5-flash")
        result = agent.loop_until(pred, max_iterations=3)
        assert result._config["_until_predicate"] is pred

    def test_loop_until_default_max_iterations(self):
        """loop_until() defaults to max_iterations=10."""
        agent = Agent("writer").model("gemini-2.5-flash")
        result = agent.loop_until(lambda s: True)
        assert result._config["max_iterations"] == 10

    def test_loop_until_on_pipeline(self):
        """loop_until() works on a pipeline (a >> b).loop_until(...)."""
        writer = Agent("writer").model("gemini-2.5-flash")
        reviewer = Agent("reviewer").model("gemini-2.5-flash")
        result = (writer >> reviewer).loop_until(lambda s: s.get("good"), max_iterations=5)
        assert isinstance(result, Loop)
        assert result._config["max_iterations"] == 5

    def test_loop_until_build_injects_checkpoint(self):
        """Building a loop_until Loop injects a checkpoint agent."""
        writer = Agent("writer").model("gemini-2.5-flash").instruct("Write")
        result = writer.loop_until(lambda s: s.get("done"), max_iterations=3)
        built = result.build()
        # Should have writer + checkpoint = 2 sub-agents
        assert len(built.sub_agents) >= 2
        # Last sub-agent should be the checkpoint
        assert "_until_check" in built.sub_agents[-1].name

    def test_loop_until_pipeline_build_injects_checkpoint(self):
        """Building a pipeline loop_until injects checkpoint after all steps."""
        writer = Agent("writer").model("gemini-2.5-flash").instruct("Write")
        reviewer = Agent("reviewer").model("gemini-2.5-flash").instruct("Review")
        result = (writer >> reviewer).loop_until(lambda s: s.get("good"), max_iterations=3)
        built = result.build()
        # Should have writer + reviewer + checkpoint = 3 sub-agents
        assert len(built.sub_agents) >= 3
        assert "_until_check" in built.sub_agents[-1].name


class TestUntilOnLoop:
    """Tests for .until() on Loop builder."""

    def test_until_on_loop_sets_predicate(self):
        """until() on a Loop sets the _until_predicate."""
        pred = lambda s: s.get("done")
        loop = Loop("refine")
        loop.until(pred)
        assert loop._config["_until_predicate"] is pred

    def test_until_on_loop_returns_self(self):
        """until() on a Loop returns self."""
        loop = Loop("refine")
        result = loop.until(lambda s: True)
        assert result is loop

    def test_until_full_loop_builder_chain(self):
        """Full Loop builder chain with until and max_iterations."""
        writer = Agent("writer").model("gemini-2.5-flash").instruct("Write")
        reviewer = Agent("reviewer").model("gemini-2.5-flash").instruct("Review")

        loop = Loop("refine").step(writer).step(reviewer).until(lambda s: s.get("quality") == "good").max_iterations(5)
        assert isinstance(loop, Loop)
        assert loop._config["max_iterations"] == 5
        assert "_until_predicate" in loop._config

    def test_until_on_non_loop_creates_loop(self):
        """until() on a non-Loop wraps in a Loop."""
        agent = Agent("writer").model("gemini-2.5-flash")
        result = agent.until(lambda s: s.get("done"))
        assert isinstance(result, Loop)


# ======================================================================
# _make_checkpoint_agent -- Internal
# ======================================================================


class TestCheckpointAgent:
    """Tests for the internal checkpoint agent."""

    def test_checkpoint_agent_is_base_agent(self):
        """Checkpoint agent is a BaseAgent instance."""
        from google.adk.agents.base_agent import BaseAgent

        agent = _make_checkpoint_agent("check", lambda s: True)
        assert isinstance(agent, BaseAgent)

    def test_checkpoint_agent_name(self):
        """Checkpoint agent has the given name."""
        agent = _make_checkpoint_agent("my_check", lambda s: True)
        assert agent.name == "my_check"


# ======================================================================
# _make_route_agent -- Internal
# ======================================================================


class TestRouteAgent:
    """Tests for the internal route agent."""

    def test_route_agent_is_base_agent(self):
        """Route agent is a BaseAgent instance."""
        from google.adk.agents.base_agent import BaseAgent
        from google.adk.agents.llm_agent import LlmAgent

        sub = LlmAgent(name="a", model="gemini-2.5-flash")
        agent = _make_route_agent("route_key", [(lambda s: True, sub)], None, [sub])
        assert isinstance(agent, BaseAgent)

    def test_route_agent_has_sub_agents(self):
        """Route agent registers all sub-agents."""
        from google.adk.agents.llm_agent import LlmAgent

        a = LlmAgent(name="a", model="gemini-2.5-flash")
        b = LlmAgent(name="b", model="gemini-2.5-flash")
        agent = _make_route_agent("route_key", [(lambda s: True, a)], b, [a, b])
        assert len(agent.sub_agents) == 2


# ======================================================================
# Full Expression Language Composition
# ======================================================================


class TestFullComposition:
    """Tests for composing all five control flow primitives."""

    def test_parallel_then_route(self):
        """(a | b) >> Route works."""
        a = Agent("a").model("gemini-2.5-flash").outputs("score_a")
        b = Agent("b").model("gemini-2.5-flash").outputs("score_b")
        handler = Agent("handler").model("gemini-2.5-flash").instruct("Handle")

        result = (a | b) >> Route().when(lambda s: True, handler)
        assert isinstance(result, Pipeline)

    def test_route_then_more_steps(self):
        """Route >> agent works for post-routing steps."""
        classifier = Agent("classify").model("gemini-2.5-flash").outputs("intent")
        a = Agent("a").model("gemini-2.5-flash").instruct("A")
        formatter = Agent("format").model("gemini-2.5-flash")

        result = (classifier >> Route("intent").eq("x", a)) >> formatter
        assert isinstance(result, Pipeline)

    def test_pipeline_with_gate_and_loop(self):
        """Pipeline with proceed_if and loop_until."""
        validator = Agent("validate").model("gemini-2.5-flash").outputs("valid")
        enricher = Agent("enrich").model("gemini-2.5-flash").proceed_if(lambda s: s.get("valid") == "yes")

        flow = validator >> enricher
        assert isinstance(flow, Pipeline)

    def test_loop_until_with_pipeline(self):
        """(a >> b).loop_until() works."""
        writer = Agent("writer").model("gemini-2.5-flash").instruct("Write")
        reviewer = Agent("reviewer").model("gemini-2.5-flash").instruct("Review").outputs("quality")

        result = (writer >> reviewer).loop_until(lambda s: s.get("quality") == "good", max_iterations=5)
        assert isinstance(result, Loop)
        assert result._config["max_iterations"] == 5
