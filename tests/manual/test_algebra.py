"""Tests for the completed expression algebra: immutable operators, >> fn, * until, @, //."""

import pytest
from pydantic import BaseModel

from adk_fluent._base import BuilderBase, _FallbackBuilder, _UntilSpec, until
from adk_fluent.agent import Agent
from adk_fluent.workflow import FanOut, Loop, Pipeline

# ======================================================================
# Immutable Operators — >> and | must not mutate left operand
# ======================================================================


class TestImmutableRshift:
    """>> must return a new Pipeline, not mutate the left operand."""

    def test_rshift_on_pipeline_returns_new_object(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        p = a >> b
        p2 = p >> c
        assert p is not p2  # Different objects

    def test_rshift_original_pipeline_unchanged(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        p = a >> b
        original_len = len(p._lists.get("sub_agents", []))
        _ = p >> c
        assert len(p._lists.get("sub_agents", [])) == original_len

    def test_sub_expression_reuse(self):
        """Core test: reusing a sub-expression produces independent pipelines."""
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        d = Agent("d").model("gemini-2.5-flash")

        review = a >> b
        pipeline_1 = review >> c
        pipeline_2 = review >> d

        built_1 = pipeline_1.build()
        built_2 = pipeline_2.build()
        assert len(built_1.sub_agents) == 3
        assert len(built_2.sub_agents) == 3
        assert built_1.sub_agents[-1].name != built_2.sub_agents[-1].name

    def test_three_way_chain_still_works(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        p = a >> b >> c
        built = p.build()
        assert len(built.sub_agents) == 3


class TestImmutableOr:
    """| must return a new FanOut, not mutate the left operand."""

    def test_or_on_fanout_returns_new_object(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        f = a | b
        f2 = f | c
        assert f is not f2

    def test_or_original_fanout_unchanged(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        f = a | b
        original_len = len(f._lists.get("sub_agents", []))
        _ = f | c
        assert len(f._lists.get("sub_agents", [])) == original_len

    def test_three_way_or_still_works(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        f = a | b | c
        built = f.build()
        assert len(built.sub_agents) == 3


# ======================================================================
# >> accepts callables — functions as workflow nodes
# ======================================================================


class TestRshiftCallable:
    """>> must accept callable (function) operands."""

    def test_agent_rshift_function_creates_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        fn = lambda s: {"x": 1}
        result = a >> fn
        assert isinstance(result, Pipeline)

    def test_function_rshift_agent_creates_pipeline(self):
        """fn >> agent works via __rrshift__."""
        fn = lambda s: {"x": 1}
        b = Agent("b").model("gemini-2.5-flash")
        result = fn >> b
        assert isinstance(result, Pipeline)

    def test_function_in_middle_of_pipeline(self):
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        fn = lambda s: {"summary": s.get("data", "")[:100]}
        result = a >> fn >> b
        assert isinstance(result, Pipeline)
        built = result.build()
        assert len(built.sub_agents) == 3

    def test_named_function_uses_name(self):
        def my_transform(state):
            return {"x": 1}

        a = Agent("a").model("gemini-2.5-flash")
        result = a >> my_transform
        # The function step should use the function name
        built = result.build()
        assert built.sub_agents[1].name == "my_transform"

    def test_lambda_gets_sanitized_name(self):
        a = Agent("a").model("gemini-2.5-flash")
        result = a >> (lambda s: {"x": 1})
        built = result.build()
        # Lambda names are sanitized to valid identifiers (fn_step_N)
        assert built.sub_agents[1].name.startswith("fn_step_")

    def test_fn_step_builds_to_base_agent(self):
        from google.adk.agents.base_agent import BaseAgent

        from adk_fluent._base import _fn_step

        step = _fn_step(lambda s: {"x": 1})
        built = step.build()
        assert isinstance(built, BaseAgent)

    def test_fn_step_is_builder_base(self):
        from adk_fluent._base import _fn_step

        step = _fn_step(lambda s: {})
        assert isinstance(step, BuilderBase)

    def test_callable_class_not_wrapped(self):
        """A type (class) should NOT be treated as a callable step."""
        a = Agent("a").model("gemini-2.5-flash")
        # Types like int are rejected — returns NotImplemented → TypeError
        with pytest.raises(TypeError):
            a >> int

    def test_function_composable_with_all_operators(self):
        """Functions compose with |, *, >> like agents."""
        fn = lambda s: {"x": 1}
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")

        # >> fn
        p1 = a >> fn >> b
        assert isinstance(p1, Pipeline)

        # fn in parallel context via pipeline
        p2 = (a >> fn) | b
        assert isinstance(p2, FanOut)


# ======================================================================
# * until(pred) — conditional loops in the algebra
# ======================================================================


class TestMulUntil:
    """* must accept until() specs in addition to integers."""

    def test_until_creates_spec(self):
        pred = lambda s: s.get("done")
        spec = until(pred, max=5)
        assert isinstance(spec, _UntilSpec)
        assert spec.predicate is pred
        assert spec.max == 5

    def test_until_default_max(self):
        spec = until(lambda s: True)
        assert spec.max == 10

    def test_agent_mul_until_creates_loop(self):
        a = Agent("a").model("gemini-2.5-flash")
        spec = until(lambda s: s.get("done"), max=3)
        result = a * spec
        assert isinstance(result, Loop)

    def test_mul_until_sets_max_iterations(self):
        a = Agent("a").model("gemini-2.5-flash")
        result = a * until(lambda s: True, max=7)
        assert result._config["max_iterations"] == 7

    def test_mul_until_stores_predicate(self):
        pred = lambda s: s.get("quality") == "good"
        a = Agent("a").model("gemini-2.5-flash")
        result = a * until(pred, max=5)
        assert result._config["_until_predicate"] is pred

    def test_pipeline_mul_until(self):
        """(a >> b) * until(pred) works."""
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        quality_ok = until(lambda s: s.get("quality") == "good", max=5)
        result = (a >> b) * quality_ok
        assert isinstance(result, Loop)
        assert result._config["max_iterations"] == 5
        assert "_until_predicate" in result._config

    def test_mul_until_builds_with_checkpoint(self):
        """Building a * until() Loop injects checkpoint agent."""
        a = Agent("a").model("gemini-2.5-flash").instruct("Test")
        result = a * until(lambda s: s.get("done"), max=3)
        built = result.build()
        assert len(built.sub_agents) >= 2
        assert "_until_check" in built.sub_agents[-1].name

    def test_mul_until_in_larger_expression(self):
        """a >> (b >> c) * until(pred) >> d works."""
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        d = Agent("d").model("gemini-2.5-flash")
        pred = until(lambda s: True, max=3)

        result = a >> (b >> c) * pred >> d
        assert isinstance(result, Pipeline)
        built = result.build()
        assert len(built.sub_agents) == 3  # a, loop, d

    def test_int_mul_still_works(self):
        """Existing int * agent syntax still works."""
        a = Agent("a").model("gemini-2.5-flash")
        result = a * 3
        assert isinstance(result, Loop)
        assert result._config["max_iterations"] == 3

    def test_rmul_still_works(self):
        """Existing int * agent syntax still works."""
        a = Agent("a").model("gemini-2.5-flash")
        result = 3 * a
        assert isinstance(result, Loop)
        assert result._config["max_iterations"] == 3

    def test_until_repr(self):
        spec = until(lambda s: True, max=5)
        r = repr(spec)
        assert "until" in r
        assert "max=5" in r


# ======================================================================
# @ — typed output contracts via __matmul__
# ======================================================================


class TestMatmul:
    """@ must bind a Pydantic model as the output schema."""

    def test_matmul_returns_new_builder(self):
        class MySchema(BaseModel):
            x: int

        a = Agent("a").model("gemini-2.5-flash")
        result = a @ MySchema
        assert result is not a  # New object (clone)
        assert isinstance(result, type(a))

    def test_matmul_sets_output_schema(self):
        class MySchema(BaseModel):
            x: int

        a = Agent("a").model("gemini-2.5-flash")
        result = a @ MySchema
        assert result._config["_output_schema"] is MySchema

    def test_matmul_original_unchanged(self):
        class MySchema(BaseModel):
            x: int

        a = Agent("a").model("gemini-2.5-flash")
        _ = a @ MySchema
        assert "_output_schema" not in a._config

    def test_matmul_wires_into_build(self):
        """@ sets output_schema on the built LlmAgent."""

        class MySchema(BaseModel):
            value: str

        a = Agent("a").model("gemini-2.5-flash").instruct("Test") @ MySchema
        built = a.build()
        assert built.output_schema is MySchema

    def test_matmul_composes_with_rshift(self):
        """a @ Schema >> b works correctly."""

        class MySchema(BaseModel):
            x: int

        a = Agent("a").model("gemini-2.5-flash") @ MySchema
        b = Agent("b").model("gemini-2.5-flash")
        result = a >> b
        assert isinstance(result, Pipeline)

    def test_matmul_preserves_config(self):
        class MySchema(BaseModel):
            x: int

        a = Agent("a").model("gemini-2.5-flash").instruct("Test instruction")
        result = a @ MySchema
        assert result._config["instruction"] == "Test instruction"
        assert result._config["model"] == "gemini-2.5-flash"

    def test_matmul_on_pipeline(self):
        """Pipeline @ Schema works (sets schema on the pipeline builder)."""

        class MySchema(BaseModel):
            x: int

        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        p = (a >> b) @ MySchema
        assert p._config.get("_output_schema") is MySchema


# ======================================================================
# // — fallback operator via __floordiv__
# ======================================================================


class TestFloordiv:
    """// must create a fallback chain."""

    def test_two_agents_creates_fallback(self):
        a = Agent("fast").model("gemini-2.0-flash")
        b = Agent("slow").model("gemini-2.5-pro")
        result = a // b
        assert isinstance(result, _FallbackBuilder)

    def test_fallback_has_children(self):
        a = Agent("fast").model("gemini-2.0-flash")
        b = Agent("slow").model("gemini-2.5-pro")
        result = a // b
        assert len(result._children) == 2

    def test_fallback_name_derived(self):
        a = Agent("fast").model("gemini-2.0-flash")
        b = Agent("slow").model("gemini-2.5-pro")
        result = a // b
        assert "fast" in result._config["name"]
        assert "slow" in result._config["name"]

    def test_three_way_fallback(self):
        a = Agent("a").model("gemini-2.0-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-pro")
        result = a // b // c
        assert isinstance(result, _FallbackBuilder)
        assert len(result._children) == 3

    def test_fallback_builds_to_base_agent(self):
        from google.adk.agents.base_agent import BaseAgent

        a = Agent("fast").model("gemini-2.0-flash").instruct("Fast")
        b = Agent("slow").model("gemini-2.5-pro").instruct("Slow")
        result = a // b
        built = result.build()
        assert isinstance(built, BaseAgent)

    def test_fallback_has_sub_agents(self):
        a = Agent("fast").model("gemini-2.0-flash").instruct("Fast")
        b = Agent("slow").model("gemini-2.5-pro").instruct("Slow")
        result = a // b
        built = result.build()
        assert len(built.sub_agents) == 2

    def test_fallback_composes_with_rshift(self):
        """a >> (b // c) >> d works."""
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.0-flash")
        c = Agent("c").model("gemini-2.5-pro")
        d = Agent("d").model("gemini-2.5-flash")

        result = a >> (b // c) >> d
        assert isinstance(result, Pipeline)
        built = result.build()
        assert len(built.sub_agents) == 3

    def test_fallback_composes_with_or(self):
        """(a // b) | (c // d) works."""
        a = Agent("a").model("gemini-2.0-flash")
        b = Agent("b").model("gemini-2.5-pro")
        c = Agent("c").model("gemini-2.0-flash")
        d = Agent("d").model("gemini-2.5-pro")

        result = (a // b) | (c // d)
        assert isinstance(result, FanOut)

    def test_fallback_with_fn(self):
        """a // fn works."""
        a = Agent("a").model("gemini-2.5-flash")
        fn = lambda s: {"fallback": True}
        result = a // fn
        assert isinstance(result, _FallbackBuilder)
        assert len(result._children) == 2


# ======================================================================
# Full Composition — all operators together
# ======================================================================


class TestFullAlgebra:
    """Tests combining all five mechanisms in complex expressions."""

    def test_fn_and_until_in_pipeline(self):
        """a >> fn >> (b >> c) * until(pred) works."""
        a = Agent("a").model("gemini-2.5-flash")
        b = Agent("b").model("gemini-2.5-flash")
        c = Agent("c").model("gemini-2.5-flash")
        fn = lambda s: {"x": 1}
        quality_ok = until(lambda s: s.get("quality") == "good", max=5)

        result = a >> fn >> (b >> c) * quality_ok
        assert isinstance(result, Pipeline)
        built = result.build()
        assert len(built.sub_agents) == 3  # a, fn, loop

    def test_matmul_and_fallback_in_pipeline(self):
        """a @ Schema // b @ Schema >> c works."""

        class Out(BaseModel):
            x: int

        a = Agent("a").model("gemini-2.0-flash").instruct("A") @ Out
        b = Agent("b").model("gemini-2.5-pro").instruct("B") @ Out
        c = Agent("c").model("gemini-2.5-flash")

        result = (a // b) >> c
        assert isinstance(result, Pipeline)

    def test_full_complex_expression(self):
        """The complete proof expression from the design."""

        class Report(BaseModel):
            title: str
            body: str
            confidence: float

        confident = until(lambda s: s.get("confidence", 0) >= 0.85, max=4)

        def merge_research(state):
            return {"research": state.get("web", "") + "\n" + state.get("papers", "")}

        pipeline = (
            (
                Agent("web").model("gemini-2.5-flash").instruct("Search web.")
                | Agent("scholar").model("gemini-2.5-flash").instruct("Search papers.")
            )
            >> merge_research
            >> Agent("writer").model("gemini-2.5-flash").instruct("Write.")
            @ Report
            // Agent("writer_b").model("gemini-2.5-pro").instruct("Write.")
            @ Report
            >> (
                Agent("critic").model("gemini-2.5-flash").instruct("Score.").outputs("confidence")
                >> Agent("reviser").model("gemini-2.5-flash").instruct("Improve.")
            )
            * confident
        )

        assert isinstance(pipeline, Pipeline)
        built = pipeline.build()
        # FanOut, merge_fn, fallback, loop = 4 sub-agents
        assert len(built.sub_agents) == 4

    def test_sub_expression_reuse_with_all_operators(self):
        """Sub-expressions with all operators can be safely reused."""
        review = Agent("reviewer").model("gemini-2.5-flash")
        quality_ok = until(lambda s: True, max=3)

        loop_a = (Agent("writer_a").model("gemini-2.5-flash") >> review) * quality_ok
        loop_b = (Agent("writer_b").model("gemini-2.5-flash") >> review) * quality_ok

        pipeline_a = Agent("intro_a").model("gemini-2.5-flash") >> loop_a
        pipeline_b = Agent("intro_b").model("gemini-2.5-flash") >> loop_b

        built_a = pipeline_a.build()
        built_b = pipeline_b.build()
        # Both should build independently
        assert len(built_a.sub_agents) == 2
        assert len(built_b.sub_agents) == 2
