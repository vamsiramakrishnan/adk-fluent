"""Tests for durable-backend code generation (Temporal / DBOS / Prefect).

These tests exercise the *generated source* — they never connect to a real
Temporal / DBOS / Prefect server. For each workflow pattern built via the
fluent API we:

1. compile the builder to IR,
2. run the backend codegen,
3. assert the generated source is valid Python (``ast.parse``),
4. assert it contains the expected control-flow constructs, and
5. assert ``annotate_checkpoints`` tags the expected I/O nodes.
"""

from __future__ import annotations

import ast

import pytest

from adk_fluent import Agent, FanOut, Loop, Pipeline, Route
from adk_fluent.backends.dbos_worker import generate_app_code
from adk_fluent.backends.prefect_worker import generate_flow_code
from adk_fluent.backends.temporal import TemporalBackend
from adk_fluent.backends.temporal_worker import generate_worker_code
from adk_fluent.compile.passes import CheckpointAnnotation, annotate_checkpoints

# ---------------------------------------------------------------------------
# Builders for each pattern (fluent API)
# ---------------------------------------------------------------------------


def _pipeline():
    return (
        Pipeline("flow")
        .step(Agent("first", "gemini-2.5-flash").instruct("Step 1.").writes("draft"))
        .step(Agent("second", "gemini-2.5-flash").instruct("Step 2 using {draft}."))
    )


def _fanout():
    return (
        FanOut("parallel")
        .branch(Agent("web", "gemini-2.5-flash").instruct("Search web."))
        .branch(Agent("papers", "gemini-2.5-flash").instruct("Search papers."))
    )


def _loop():
    return (
        Loop("refine")
        .step(Agent("writer", "gemini-2.5-flash").instruct("Write."))
        .step(Agent("critic", "gemini-2.5-flash").instruct("Critique."))
        .max_iterations(4)
    )


def _fallback():
    return Agent("fast", "gemini-2.5-flash") // Agent("strong", "gemini-2.5-pro")


def _route():
    return (
        Route("tier")
        .eq("VIP", Agent("vip", "gemini-2.5-flash").instruct("VIP handling."))
        .gt(100, Agent("big", "gemini-2.5-flash").instruct("Big handling."))
        .otherwise(Agent("standard", "gemini-2.5-flash").instruct("Standard."))
    )


def _temporal_source(builder) -> str:
    runnable = TemporalBackend().compile(builder.to_ir())
    return generate_worker_code(runnable)


# ---------------------------------------------------------------------------
# Generated source is valid Python for every pattern
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "factory",
    [_pipeline, _fanout, _loop, _fallback, _route],
    ids=["pipeline", "fanout", "loop", "fallback", "route"],
)
def test_temporal_source_parses(factory):
    src = _temporal_source(factory())
    ast.parse(src)  # raises SyntaxError on malformed output


# ---------------------------------------------------------------------------
# Each pattern emits the expected construct
# ---------------------------------------------------------------------------


def test_temporal_pipeline_is_sequential():
    src = _temporal_source(_pipeline())
    ast.parse(src)
    # Two sequential activity calls, in order.
    assert "execute_activity" in src
    assert src.index('"first"') < src.index('"second"')


def test_temporal_fanout_uses_gather():
    src = _temporal_source(_fanout())
    ast.parse(src)
    assert "await asyncio.gather(" in src
    # Both branches are started before the gather call.
    assert "web_handle = workflow.start_activity" in src
    assert "papers_handle = workflow.start_activity" in src
    assert src.index("web_handle = workflow.start_activity") < src.index("await asyncio.gather(")


def test_temporal_loop_is_bounded():
    src = _temporal_source(_loop())
    tree = ast.parse(src)
    assert "range(4)" in src
    # There must be a bounded ``for`` loop in the workflow body.
    for_loops = [n for n in ast.walk(tree) if isinstance(n, ast.For)]
    assert for_loops, "expected a bounded for-loop for the Loop node"


def test_temporal_fallback_is_try_except_cascade():
    src = _temporal_source(_fallback())
    tree = ast.parse(src)
    assert "try:" in src
    assert "except Exception:" in src
    # Nested cascade: a Try whose handler body itself contains a Try.
    nested = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if any(isinstance(s, ast.Try) for s in handler.body):
                    nested = True
    assert nested, "expected a nested try/except fallback cascade"


def test_temporal_route_branches_on_state_key():
    src = _temporal_source(_route())
    tree = ast.parse(src)
    # Branch on the route state key ("tier").
    assert "state.get('tier')" in src
    assert "_route_value_" in src
    assert "_route_match" in src
    assert "elif" in src
    assert "else:" in src
    # The if/elif/else cascade must be present.
    ifs = [n for n in ast.walk(tree) if isinstance(n, ast.If)]
    assert ifs, "expected an if/elif/else branch for the Route node"


# ---------------------------------------------------------------------------
# annotate_checkpoints tags I/O-bearing nodes
# ---------------------------------------------------------------------------


def test_annotate_checkpoints_tags_agents_only():
    ann = annotate_checkpoints(_pipeline().to_ir())
    assert isinstance(ann, CheckpointAnnotation)
    # The two agents are checkpoint boundaries; the SequenceNode is not.
    assert ann.boundary_names == frozenset({"first", "second"})
    root_desc = ann.checkpoints[()]
    assert root_desc["node_type"] == "SequenceNode"
    assert root_desc["checkpoint"] is False


def test_annotate_checkpoints_fanout():
    ann = annotate_checkpoints(_fanout().to_ir())
    assert ann.boundary_names == frozenset({"web", "papers"})
    # ParallelNode itself is deterministic orchestration.
    assert ann.checkpoints[()]["checkpoint"] is False


def test_annotate_checkpoints_loop():
    ann = annotate_checkpoints(_loop().to_ir())
    assert ann.boundary_names == frozenset({"writer", "critic"})
    assert ann.checkpoints[()]["node_type"] == "LoopNode"
    assert ann.checkpoints[()]["checkpoint"] is False


def test_annotate_checkpoints_route_covers_branches_and_default():
    ann = annotate_checkpoints(_route().to_ir())
    # Every agent reachable through a rule or the default is a boundary.
    assert ann.boundary_names == frozenset({"vip", "big", "standard"})
    assert ann.checkpoints[()]["node_type"] == "RouteNode"
    assert ann.checkpoints[()]["checkpoint"] is False


def test_annotate_checkpoints_idempotent_on_annotation():
    ir = _pipeline().to_ir()
    once = annotate_checkpoints(ir)
    twice = annotate_checkpoints(once)  # accepts a prior annotation
    assert twice.boundary_names == once.boundary_names
    assert twice.ir is ir


def test_checkpoint_annotation_drives_temporal_activity_boundaries():
    # The Temporal plan promotes annotated I/O nodes to activities.
    runnable = TemporalBackend().compile(_pipeline().to_ir())
    seq = runnable.node_plan[0]
    assert seq["node_type"] == "SequenceNode"
    assert seq["checkpoint"] is False
    for child in seq["children"]:
        assert child["temporal_type"] == "activity"
        assert child["checkpoint"] is True


# ---------------------------------------------------------------------------
# DBOS / Prefect remain at least as capable (parallel + loop + fallback)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "factory",
    [_pipeline, _fanout, _loop, _fallback, _route],
    ids=["pipeline", "fanout", "loop", "fallback", "route"],
)
def test_dbos_source_parses(factory):
    from adk_fluent.backends.dbos_backend import DBOSBackend

    runnable = DBOSBackend().compile(factory().to_ir())
    src = generate_app_code(runnable)
    ast.parse(src)


@pytest.mark.parametrize(
    "factory",
    [_pipeline, _fanout, _loop, _fallback, _route],
    ids=["pipeline", "fanout", "loop", "fallback", "route"],
)
def test_prefect_source_parses(factory):
    from adk_fluent.backends.prefect_backend import PrefectBackend

    runnable = PrefectBackend().compile(factory().to_ir())
    src = generate_flow_code(runnable)
    ast.parse(src)


def test_dbos_fanout_uses_gather():
    from adk_fluent.backends.dbos_backend import DBOSBackend

    runnable = DBOSBackend().compile(_fanout().to_ir())
    src = generate_app_code(runnable)
    ast.parse(src)
    assert "asyncio.gather" in src


def test_prefect_fanout_uses_submit():
    from adk_fluent.backends.prefect_backend import PrefectBackend

    runnable = PrefectBackend().compile(_fanout().to_ir())
    src = generate_flow_code(runnable)
    ast.parse(src)
    assert ".submit(" in src


def test_dbos_fallback_is_nested_cascade():
    from adk_fluent.backends.dbos_backend import DBOSBackend

    # Three alternatives — exercises a genuine nested cascade.
    builder = Agent("a", "m") // Agent("b", "m") // Agent("c", "m")
    runnable = DBOSBackend().compile(builder.to_ir())
    tree = ast.parse(generate_app_code(runnable))
    nested = any(
        isinstance(s, ast.Try)
        for tr in ast.walk(tree)
        if isinstance(tr, ast.Try)
        for h in tr.handlers
        for s in h.body
    )
    assert nested, "expected a nested try/except cascade in DBOS output"


def test_dbos_route_emits_branch():
    from adk_fluent.backends.dbos_backend import DBOSBackend

    runnable = DBOSBackend().compile(_route().to_ir())
    src = generate_app_code(runnable)
    ast.parse(src)
    assert "state.get('tier')" in src
    # Branch bodies invoke the per-rule steps.
    assert src.count("vip_step") >= 2


def test_prefect_route_emits_branch():
    from adk_fluent.backends.prefect_backend import PrefectBackend

    runnable = PrefectBackend().compile(_route().to_ir())
    src = generate_flow_code(runnable)
    ast.parse(src)
    assert "state.get('tier')" in src
