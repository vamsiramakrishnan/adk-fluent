"""Cross-namespace operator algebra (Capability #10).

Namespace values (S/C/A transforms) and Agents compose in ONE ``>>`` chain
with a single consistent meaning:

    flow = S.set(stage="a") >> Agent("x") >> C.window(n=5) >> A.publish("out.md") >> Agent("y")

Semantics added (all strictly additive — same-namespace operators unchanged):

* ``S >> Agent`` / ``Agent >> S``   — S transform becomes a zero-cost FnStep node
                                      (already supported via STransform; covered here
                                      as a regression guard).
* ``A >> Agent`` / ``Agent >> A``   — A op becomes an ArtifactAgent step node
                                      (already supported via _artifact_op; guarded here).
* ``C >> Agent`` / ``Agent >> C``   — C transform binds to the *adjacent* Agent's
                                      ``.context()`` (NEW). A context transform has no
                                      standalone state effect, so it configures the agent
                                      it sits next to rather than becoming a step.
* ``Pipeline >> C``                 — binds to the pipeline's last Agent step.
"""

from __future__ import annotations

import pytest

from adk_fluent import A, Agent, C, S
from adk_fluent.workflow import FanOut, Pipeline

# ---------------------------------------------------------------------------
# S (state) mixing — already supported; guard against regression
# ---------------------------------------------------------------------------


def test_s_then_agent_is_pipeline():
    flow = S.set(stage="x") >> Agent("a", "gemini-2.5-flash").mock(["hi"])
    assert isinstance(flow, Pipeline)
    steps = flow._lists["sub_agents"]
    assert len(steps) == 2
    # First step is the state transform (FnStep), second is the agent.
    assert type(steps[0]).__name__ == "_FnStepBuilder"
    assert isinstance(steps[1], Agent)
    # The state transform actually applies the delta.
    assert steps[0]._fn({}).updates == {"stage": "x"}


def test_s_then_agent_executes():
    flow = S.set(stage="ready") >> Agent("a", "gemini-2.5-flash").mock(["done"])
    assert flow.ask("go") == "done"


def test_agent_then_s_is_pipeline():
    flow = Agent("a", "gemini-2.5-flash") >> S.pick("out")
    assert isinstance(flow, Pipeline)
    steps = flow._lists["sub_agents"]
    assert isinstance(steps[0], Agent)
    assert type(steps[1]).__name__ == "_FnStepBuilder"


# ---------------------------------------------------------------------------
# A (artifact) mixing — already supported; guard against regression
# ---------------------------------------------------------------------------


def test_agent_then_artifact_wraps_op():
    flow = Agent("a", "gemini-2.5-flash").writes("out") >> A.publish("out.md", from_key="out")
    assert isinstance(flow, Pipeline)
    steps = flow._lists["sub_agents"]
    assert isinstance(steps[0], Agent)
    assert type(steps[1]).__name__ == "_ArtifactBuilder"
    assert steps[1]._atransform._op == "publish"


def test_artifact_then_agent_is_pipeline():
    flow = A.publish("out.md", from_key="out") >> Agent("b", "gemini-2.5-flash")
    assert isinstance(flow, Pipeline)
    steps = flow._lists["sub_agents"]
    assert type(steps[0]).__name__ == "_ArtifactBuilder"
    assert isinstance(steps[1], Agent)


# ---------------------------------------------------------------------------
# C (context) mixing — NEW: binds to the adjacent Agent's context
# ---------------------------------------------------------------------------


def test_c_then_agent_binds_context():
    ctx = C.window(n=5)
    agent = C.window(n=5) >> Agent("y", "gemini-2.5-flash")
    # Result is the agent itself, configured with the context.
    assert isinstance(agent, Agent)
    assert "_context_spec" in agent._config
    assert agent._config["_context_spec"].include_contents == ctx.include_contents


def test_agent_then_c_binds_context():
    agent = Agent("x", "gemini-2.5-flash") >> C.window(n=5)
    assert isinstance(agent, Agent)
    assert "_context_spec" in agent._config


def test_pipeline_then_c_binds_to_last_agent():
    # (S >> Agent("x")) >> C  -> C binds to Agent("x"), the last/adjacent agent.
    flow = S.set(stage="a") >> Agent("x", "gemini-2.5-flash") >> C.window(n=5)
    assert isinstance(flow, Pipeline)
    steps = flow._lists["sub_agents"]
    assert len(steps) == 2  # C does NOT add a step; it reconfigures the agent.
    assert "_context_spec" in steps[1]._config


def test_c_binding_equivalent_to_dot_context():
    via_operator = C.user_only() >> Agent("y", "gemini-2.5-flash")
    via_method = Agent("y", "gemini-2.5-flash").context(C.user_only())
    assert via_operator._config["_context_spec"].include_contents == (
        via_method._config["_context_spec"].include_contents
    )


def test_fanout_then_c_raises_clear_error():
    # A workflow builder with no single Agent to receive the context.
    with pytest.raises(TypeError, match="context transform"):
        (Agent("a", "gemini-2.5-flash") | Agent("b", "gemini-2.5-flash")) >> C.window(n=5)


# ---------------------------------------------------------------------------
# Full mixed chain — the headline capability
# ---------------------------------------------------------------------------


def test_four_stage_mixed_chain_preserves_order():
    flow = (
        S.set(stage="a")
        >> Agent("x", "gemini-2.5-flash").writes("out")
        >> C.window(n=5)
        >> A.publish("out.md", from_key="out")
        >> Agent("y", "gemini-2.5-flash")
    )
    assert isinstance(flow, Pipeline)
    steps = flow._lists["sub_agents"]
    # C reconfigures Agent("x") in place rather than adding a node, so the
    # chain has exactly 4 steps in order: S, Agent(x), A, Agent(y).
    kinds = [type(s).__name__ for s in steps]
    assert kinds == ["_FnStepBuilder", "Agent", "_ArtifactBuilder", "Agent"]
    # C bound to Agent("x").
    assert "_context_spec" in steps[1]._config
    assert "_context_spec" not in steps[3]._config
    # First/last names preserved.
    assert steps[1]._config["name"] == "x"
    assert steps[3]._config["name"] == "y"


def test_mixed_chain_builds_to_native_adk_object():
    flow = (
        S.set(stage="a")
        >> Agent("x", "gemini-2.5-flash").writes("out")
        >> A.publish("out.md", from_key="out")
        >> Agent("y", "gemini-2.5-flash")
    )
    built = flow.build()
    # Native ADK SequentialAgent with all four steps.
    assert type(built).__name__ == "SequentialAgent"
    assert len(built.sub_agents) == 4


def test_chain_starting_with_s_runs_end_to_end():
    flow = S.set(greeting="hello") >> Agent("a", "gemini-2.5-flash").mock(["world"])
    assert flow.ask("go") == "world"


# ---------------------------------------------------------------------------
# Regression: same-namespace operators are completely unchanged
# ---------------------------------------------------------------------------


def test_agent_then_agent_still_pipeline():
    flow = Agent("a", "gemini-2.5-flash") >> Agent("b", "gemini-2.5-flash")
    assert isinstance(flow, Pipeline)
    assert len(flow._lists["sub_agents"]) == 2


def test_s_then_s_still_stransform_chain():
    from adk_fluent._transforms import STransform

    chained = S.set(a=1) >> S.set(b=2)
    assert isinstance(chained, STransform)
    # Chained STransforms apply sequentially (unchanged behavior); the
    # standalone call returns the final step's delta.
    result = chained({})
    assert result.updates == {"b": 2}
    # Combine (+) is the operator that merges both deltas — also unchanged.
    combined = (S.set(a=1) + S.set(b=2))({})
    assert combined.updates == {"a": 1, "b": 2}


def test_c_then_c_still_cpipe():
    chained = C.window(n=5) >> C.user_only()
    assert type(chained).__name__ == "CPipe"


def test_a_then_a_still_pipeline():
    flow = A.publish("x.md", from_key="k") >> A.publish("y.md", from_key="k2")
    assert isinstance(flow, Pipeline)
    assert len(flow._lists["sub_agents"]) == 2


def test_agent_then_callable_still_fn_step():
    flow = Agent("a", "gemini-2.5-flash") >> (lambda s: {"x": 1})
    assert isinstance(flow, Pipeline)
    assert type(flow._lists["sub_agents"][1]).__name__ == "_FnStepBuilder"


def test_fanout_and_loop_operators_unchanged():
    fanout = Agent("a", "gemini-2.5-flash") | Agent("b", "gemini-2.5-flash")
    assert isinstance(fanout, FanOut)
    loop = (Agent("a", "gemini-2.5-flash") >> Agent("b", "gemini-2.5-flash")) * 3
    assert type(loop).__name__ == "Loop"
