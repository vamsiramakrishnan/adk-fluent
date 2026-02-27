"""Tests for ParallelNode and LoopNode contract checking (v0.9.2 — Tier 1)."""

import pytest
from pydantic import BaseModel


def test_parallel_output_key_collision():
    """Two parallel branches writing to same output_key triggers error."""
    from adk_fluent import Agent
    from adk_fluent.testing.contracts import check_contracts

    fanout = Agent("a").outputs("result") | Agent("b").outputs("result")
    ir = fanout.to_ir()
    issues = check_contracts(ir)
    collision_errors = [
        i for i in issues
        if isinstance(i, dict) and i.get("level") == "error" and "race condition" in i.get("message", "")
    ]
    assert len(collision_errors) >= 1
    assert "result" in collision_errors[0]["message"]


def test_parallel_no_collision_different_keys():
    """Parallel branches with different output_keys are fine."""
    from adk_fluent import Agent
    from adk_fluent.testing.contracts import check_contracts

    fanout = Agent("a").outputs("result_a") | Agent("b").outputs("result_b")
    ir = fanout.to_ir()
    issues = check_contracts(ir)
    collision_errors = [
        i for i in issues
        if isinstance(i, dict) and i.get("level") == "error" and "race condition" in i.get("message", "")
    ]
    assert len(collision_errors) == 0


def test_parallel_writes_keys_collision():
    """Parallel branches with overlapping writes_keys triggers info."""

    class Score(BaseModel):
        score: float

    from adk_fluent import Agent
    from adk_fluent.testing.contracts import check_contracts

    fanout = Agent("a").produces(Score) | Agent("b").produces(Score)
    ir = fanout.to_ir()
    issues = check_contracts(ir)
    collision_info = [
        i for i in issues
        if isinstance(i, dict) and "race condition" in i.get("message", "")
    ]
    assert len(collision_info) >= 1


def test_parallel_empty_no_issues():
    """Empty parallel returns no issues."""
    from adk_fluent._ir_generated import ParallelNode
    from adk_fluent.testing.contracts import check_contracts

    ir = ParallelNode(name="empty")
    assert check_contracts(ir) == []


def test_loop_body_sequence_checked():
    """Loop body children get sequence contract checking."""
    from adk_fluent import Agent
    from adk_fluent.testing.contracts import check_contracts

    loop = (Agent("a").instruct("Write.") >> Agent("b").instruct("Review {draft}.")) * 3
    ir = loop.to_ir()
    issues = check_contracts(ir)
    # {draft} is unresolved in the loop body
    template_errors = [
        i for i in issues
        if isinstance(i, dict) and i.get("level") == "error" and "draft" in i.get("message", "")
    ]
    assert len(template_errors) >= 1


def test_loop_body_valid_no_errors():
    """Loop body with resolved variables produces no template errors."""
    from adk_fluent import Agent
    from adk_fluent.testing.contracts import check_contracts

    loop = (Agent("a").instruct("Write.").outputs("draft") >> Agent("b").instruct("Review {draft}.")) * 3
    ir = loop.to_ir()
    issues = check_contracts(ir)
    template_errors = [
        i for i in issues
        if isinstance(i, dict) and i.get("level") == "error" and "Template variable" in i.get("message", "")
    ]
    assert len(template_errors) == 0


def test_check_contracts_dispatches_parallel():
    """check_contracts() handles ParallelNode directly."""
    from adk_fluent import Agent
    from adk_fluent.testing.contracts import check_contracts

    fanout = Agent("a").outputs("x") | Agent("b").outputs("x")
    ir = fanout.to_ir()
    # Should not crash — should dispatch to parallel checker
    issues = check_contracts(ir)
    assert isinstance(issues, list)


def test_check_contracts_dispatches_loop():
    """check_contracts() handles LoopNode directly."""
    from adk_fluent import Agent
    from adk_fluent.testing.contracts import check_contracts

    loop = Agent("a") * 3
    ir = loop.to_ir()
    issues = check_contracts(ir)
    assert isinstance(issues, list)
