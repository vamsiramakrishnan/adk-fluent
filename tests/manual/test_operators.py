"""Tests for operator composition: >>, |, *."""
from adk_fluent.agent import Agent
from adk_fluent.workflow import Pipeline, FanOut, Loop


class TestRshift:
    def test_two_agents_creates_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        result = a >> b
        assert isinstance(result, Pipeline)

    def test_pipeline_has_both_steps(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        p = a >> b
        built = p.build()
        assert len(built.sub_agents) == 2

    def test_pipeline_name_derived(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        p = a >> b
        assert p._config["name"] == "a_then_b"

    def test_three_agents_gives_three_steps(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        p = a >> b >> c
        built = p.build()
        assert len(built.sub_agents) == 3

    def test_rshift_on_existing_pipeline_appends(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        p = Pipeline("pipe").step(a).step(b)
        p2 = p >> c
        assert isinstance(p2, Pipeline)
        built = p2.build()
        assert len(built.sub_agents) == 3


class TestOr:
    def test_two_agents_creates_fanout(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        result = a | b
        assert isinstance(result, FanOut)

    def test_fanout_has_both_branches(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        f = a | b
        built = f.build()
        assert len(built.sub_agents) == 2

    def test_fanout_name_derived(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        f = a | b
        assert f._config["name"] == "a_and_b"

    def test_three_branches(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        f = a | b | c
        built = f.build()
        assert len(built.sub_agents) == 3


class TestMul:
    def test_agent_mul_int_creates_loop(self):
        a = Agent("a").model("gemini-2.5-flash")
        result = a * 3
        assert isinstance(result, Loop)

    def test_loop_has_correct_max_iterations(self):
        a = Agent("a").model("gemini-2.5-flash")
        loop = a * 3
        assert loop._config["max_iterations"] == 3

    def test_loop_name_derived(self):
        a = Agent("a").model("gemini-2.5-flash")
        loop = a * 3
        assert loop._config["name"] == "a_x3"

    def test_rmul_int_times_agent(self):
        a = Agent("a").model("gemini-2.5-flash")
        loop = 3 * a
        assert isinstance(loop, Loop)
        assert loop._config["max_iterations"] == 3

    def test_pipeline_mul_creates_loop_with_steps(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        p = a >> b
        loop = p * 3
        assert isinstance(loop, Loop)
        built = loop.build()
        assert len(built.sub_agents) == 2
        assert loop._config["max_iterations"] == 3


class TestComplex:
    def test_fanout_then_pipeline(self):
        """(a | b) >> c works."""
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        result = (a | b) >> c
        assert isinstance(result, Pipeline)
        built = result.build()
        assert len(built.sub_agents) == 2

    def test_complex_chain(self):
        """a >> (b >> c) * 3 >> d works."""
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        d = Agent("d").model("gemini-2.5-flash")
        result = a >> (b >> c) * 3 >> d
        assert isinstance(result, Pipeline)
        built = result.build()
        assert len(built.sub_agents) == 3  # a, loop, d
