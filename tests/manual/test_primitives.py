"""Tests for new control loop primitives: tap, expect, mock, retry_if, map_over, timeout, gate, race."""

import pytest

from adk_fluent._base import (
    BuilderBase,
    _GateBuilder,
    _MapOverBuilder,
    _RaceBuilder,
    _TapBuilder,
    _TimeoutBuilder,
    expect,
    gate,
    map_over,
    race,
    tap,
)
from adk_fluent.agent import Agent
from adk_fluent.workflow import Loop, Pipeline

# ======================================================================
# Primitive 1: tap
# ======================================================================


class TestTap:
    def test_tap_creates_builder(self):
        result = tap(lambda s: None)
        assert isinstance(result, BuilderBase)
        assert isinstance(result, _TapBuilder)

    def test_tap_in_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        p = a >> tap(lambda s: print(s)) >> b
        assert isinstance(p, Pipeline)
        # 3 steps: a, tap, b
        assert len(p._lists["sub_agents"]) == 3

    def test_tap_name_from_function(self):
        def my_observer(s):
            pass

        t = tap(my_observer)
        assert t._config["name"] == "my_observer"

    def test_tap_name_sanitized(self):
        t = tap(lambda s: None)
        assert t._config["name"].isidentifier()
        assert t._config["name"].startswith("tap_")

    def test_tap_builds_base_agent(self):
        from google.adk.agents.base_agent import BaseAgent

        t = tap(lambda s: None)
        built = t.build()
        assert isinstance(built, BaseAgent)

    def test_tap_method_on_builder(self):
        """BuilderBase.tap() returns a Pipeline."""
        a = Agent("a").model("gemini-2.5-flash")
        result = a.tap(lambda s: None)
        assert isinstance(result, Pipeline)

    def test_tap_composable_with_operators(self):
        """tap works with >> operator on both sides."""
        t = tap(lambda s: None)
        a = Agent("a").model("gemini-2.5-flash")
        p1 = t >> a
        assert isinstance(p1, Pipeline)
        p2 = a >> t
        assert isinstance(p2, Pipeline)


# ======================================================================
# Primitive 2: expect
# ======================================================================


class TestExpect:
    def test_expect_creates_builder(self):
        result = expect(lambda s: "key" in s)
        assert isinstance(result, BuilderBase)

    def test_expect_in_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        p = a >> expect(lambda s: True) >> b
        assert isinstance(p, Pipeline)

    def test_expect_builds_base_agent(self):
        from google.adk.agents.base_agent import BaseAgent

        e = expect(lambda s: True, "msg")
        built = e.build()
        assert isinstance(built, BaseAgent)

    def test_expect_raises_on_failure(self):
        e = expect(lambda s: False, "Custom error message")
        # Access the internal function
        fn = e._fn
        with pytest.raises(ValueError, match="Custom error message"):
            fn({})

    def test_expect_passes_when_true(self):
        e = expect(lambda s: True)
        fn = e._fn
        result = fn({"anything": "value"})
        assert result == {}

    def test_expect_default_message(self):
        e = expect(lambda s: False)
        fn = e._fn
        with pytest.raises(ValueError, match="State assertion failed"):
            fn({})

    def test_expect_name_auto_generated(self):
        e = expect(lambda s: True)
        assert e._config["name"].startswith("expect_")
        assert e._config["name"].isidentifier()


# ======================================================================
# Primitive 3: mock
# ======================================================================


class TestMock:
    def test_mock_list_registers_callback(self):
        agent = Agent("test").model("gemini-2.5-flash")
        agent.mock(["response 1", "response 2"])
        assert len(agent._callbacks["before_model_callback"]) == 1

    def test_mock_callable_registers_callback(self):
        agent = Agent("test").model("gemini-2.5-flash")
        agent.mock(lambda req: "fixed")
        assert len(agent._callbacks["before_model_callback"]) == 1

    def test_mock_returns_self(self):
        agent = Agent("test").model("gemini-2.5-flash")
        result = agent.mock(["x"])
        assert result is agent

    def test_mock_chainable(self):
        agent = Agent("test").model("gemini-2.5-flash").mock(["x"]).instruct("Go")
        assert agent._config["instruction"] == "Go"
        assert len(agent._callbacks["before_model_callback"]) == 1

    def test_mock_callback_returns_llm_response(self):
        from google.adk.models.llm_response import LlmResponse

        agent = Agent("test").model("gemini-2.5-flash").mock(["hello"])
        cb = agent._callbacks["before_model_callback"][0]
        result = cb(callback_context=None, llm_request=None)
        assert isinstance(result, LlmResponse)
        assert result.content.parts[0].text == "hello"

    def test_mock_list_cycles(self):
        agent = Agent("test").model("gemini-2.5-flash").mock(["a", "b"])
        cb = agent._callbacks["before_model_callback"][0]
        r1 = cb(None, None)
        r2 = cb(None, None)
        r3 = cb(None, None)
        assert r1.content.parts[0].text == "a"
        assert r2.content.parts[0].text == "b"
        assert r3.content.parts[0].text == "a"  # cycles back

    def test_mock_callable_receives_request(self):
        received = []
        agent = Agent("test").model("gemini-2.5-flash").mock(lambda req: (received.append(req), "dynamic")[1])
        cb = agent._callbacks["before_model_callback"][0]
        sentinel = object()
        cb(None, sentinel)
        assert received[0] is sentinel


# ======================================================================
# Primitive 4: retry_if
# ======================================================================


class TestRetryIf:
    def test_retry_if_creates_loop(self):
        agent = Agent("writer").model("gemini-2.5-flash")
        result = agent.retry_if(lambda s: s.get("quality") != "good")
        assert isinstance(result, Loop)

    def test_retry_if_sets_max_iterations(self):
        agent = Agent("writer").model("gemini-2.5-flash")
        result = agent.retry_if(lambda s: True, max_retries=5)
        assert result._config["max_iterations"] == 5

    def test_retry_if_default_max_retries(self):
        agent = Agent("writer").model("gemini-2.5-flash")
        result = agent.retry_if(lambda s: True)
        assert result._config["max_iterations"] == 3

    def test_retry_if_inverts_predicate(self):
        """retry_if(p) should be equivalent to loop_until(not p)."""
        agent = Agent("writer").model("gemini-2.5-flash")
        result = agent.retry_if(lambda s: s.get("quality") != "good")
        until_pred = result._config["_until_predicate"]
        assert until_pred({"quality": "good"}) is True  # exit loop
        assert until_pred({"quality": "bad"}) is False  # keep retrying

    def test_retry_if_builds_with_checkpoint(self):
        agent = Agent("writer").model("gemini-2.5-flash").instruct("Write")
        result = agent.retry_if(lambda s: True, max_retries=3)
        built = result.build()
        # Should have the agent + checkpoint sub-agents
        assert len(built.sub_agents) >= 2

    def test_retry_if_on_pipeline(self):
        writer = Agent("writer").model("gemini-2.5-flash")
        reviewer = Agent("reviewer").model("gemini-2.5-flash")
        result = (writer >> reviewer).retry_if(lambda s: s.get("q") != "ok", max_retries=5)
        assert isinstance(result, Loop)


# ======================================================================
# Primitive 5: map_over
# ======================================================================


class TestMapOver:
    def test_map_over_creates_builder(self):
        agent = Agent("summarizer").model("gemini-2.5-flash")
        result = map_over("items", agent)
        assert isinstance(result, BuilderBase)
        assert isinstance(result, _MapOverBuilder)

    def test_map_over_in_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        m = map_over("items", Agent("b").model("gemini-2.5-flash"))
        p = a >> m
        assert isinstance(p, Pipeline)

    def test_map_over_builds_with_sub_agent(self):
        from google.adk.agents.base_agent import BaseAgent

        agent = Agent("summarizer").model("gemini-2.5-flash").instruct("Summarize")
        m = map_over("items", agent, output_key="summaries")
        built = m.build()
        assert isinstance(built, BaseAgent)
        assert len(built.sub_agents) == 1

    def test_map_over_stores_keys(self):
        m = map_over("items", Agent("s").model("gemini-2.5-flash"), item_key="_current", output_key="results")
        assert m._list_key == "items"
        assert m._item_key == "_current"
        assert m._output_key == "results"

    def test_map_over_default_keys(self):
        m = map_over("items", Agent("s").model("gemini-2.5-flash"))
        assert m._item_key == "_item"
        assert m._output_key == "summaries"

    def test_map_over_name_includes_key(self):
        m = map_over("documents", Agent("s").model("gemini-2.5-flash"))
        assert "documents" in m._config["name"]


# ======================================================================
# Primitive 6: timeout
# ======================================================================


class TestTimeout:
    def test_timeout_creates_builder(self):
        agent = Agent("a").model("gemini-2.5-flash")
        result = agent.timeout(30)
        assert isinstance(result, BuilderBase)
        assert isinstance(result, _TimeoutBuilder)

    def test_timeout_stores_seconds(self):
        agent = Agent("a").model("gemini-2.5-flash")
        result = agent.timeout(30)
        assert result._seconds == 30

    def test_timeout_in_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        p = a.timeout(30) >> b
        assert isinstance(p, Pipeline)

    def test_timeout_builds_with_sub_agent(self):
        from google.adk.agents.base_agent import BaseAgent

        agent = Agent("a").model("gemini-2.5-flash").instruct("Hi")
        result = agent.timeout(30)
        built = result.build()
        assert isinstance(built, BaseAgent)
        assert len(built.sub_agents) == 1

    def test_timeout_name_includes_original(self):
        agent = Agent("my_agent").model("gemini-2.5-flash")
        result = agent.timeout(30)
        assert "my_agent" in result._config["name"]

    def test_timeout_composable(self):
        """Timeout builder supports all operators."""
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        # timeout >> agent
        p = a.timeout(10) >> b
        assert isinstance(p, Pipeline)
        # timeout | agent (parallel)
        from adk_fluent.workflow import FanOut

        f = a.timeout(10) | b
        assert isinstance(f, FanOut)


# ======================================================================
# Primitive 7: gate
# ======================================================================


class TestGate:
    def test_gate_creates_builder(self):
        result = gate(lambda s: True, message="Approve?")
        assert isinstance(result, BuilderBase)
        assert isinstance(result, _GateBuilder)

    def test_gate_in_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        p = a >> gate(lambda s: s.get("risk") == "high") >> b
        assert isinstance(p, Pipeline)

    def test_gate_builds_base_agent(self):
        from google.adk.agents.base_agent import BaseAgent

        g = gate(lambda s: True, message="Approve?")
        built = g.build()
        assert isinstance(built, BaseAgent)

    def test_gate_stores_predicate_and_message(self):
        pred = lambda s: True
        g = gate(pred, message="Custom msg")
        assert g._predicate is pred
        assert g._message == "Custom msg"

    def test_gate_default_message(self):
        g = gate(lambda s: True)
        assert g._message == "Approval required"

    def test_gate_custom_gate_key(self):
        g = gate(lambda s: True, gate_key="_my_gate")
        assert g._gate_key == "_my_gate"

    def test_gate_auto_gate_key(self):
        g = gate(lambda s: True)
        assert g._gate_key.startswith("_gate_")


# ======================================================================
# Primitive 8: race
# ======================================================================


class TestRace:
    def test_race_creates_builder(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        result = race(a, b)
        assert isinstance(result, BuilderBase)
        assert isinstance(result, _RaceBuilder)

    def test_race_in_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        p = c >> race(a, b)
        assert isinstance(p, Pipeline)

    def test_race_builds_with_sub_agents(self):
        from google.adk.agents.base_agent import BaseAgent

        a = Agent("a").model("gemini-2.5-flash").instruct("A")
        b = Agent("b").model("gemini-2.5-flash").instruct("B")
        r = race(a, b)
        built = r.build()
        assert isinstance(built, BaseAgent)
        assert len(built.sub_agents) == 2

    def test_race_three_agents(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        r = race(a, b, c)
        built = r.build()
        assert len(built.sub_agents) == 3

    def test_race_name_includes_agents(self):
        a = Agent("fast").model("gemini-2.5-flash")
        b = Agent("slow").model("gemini-2.5-flash")
        r = race(a, b)
        assert "fast" in r._config["name"]
        assert "slow" in r._config["name"]

    def test_race_composable(self):
        """Race builder supports operators."""
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        p = race(a, b) >> c
        assert isinstance(p, Pipeline)
