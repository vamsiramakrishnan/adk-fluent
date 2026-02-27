"""Tests for transform read/write tracing (v0.9.2 — Tier 1)."""

import pytest
from pydantic import BaseModel


def test_s_rename_produces_new_key():
    """S.rename(draft='input') should make {input} resolvable downstream."""
    from adk_fluent import Agent, S
    from adk_fluent.testing.contracts import check_contracts

    pipeline = (
        Agent("writer").instruct("Write.").outputs("draft")
        >> S.rename(draft="input")
        >> Agent("reviewer").instruct("Review the {input}.")
    )
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    # 'input' should be produced by S.rename, so no error about it
    template_errors = [
        i for i in issues
        if isinstance(i, dict) and i.get("level") == "error" and "input" in i.get("message", "")
        and "Template variable" in i.get("message", "")
    ]
    assert len(template_errors) == 0


def test_s_merge_produces_merged_key():
    """S.merge('a', 'b', into='combined') should make {combined} resolvable."""
    from adk_fluent import Agent, S
    from adk_fluent.testing.contracts import check_contracts

    pipeline = (
        Agent("a").instruct("Write part A.").outputs("part_a")
        >> Agent("b").instruct("Write part B.").outputs("part_b")
        >> S.merge("part_a", "part_b", into="combined")
        >> Agent("final").instruct("Review the {combined}.")
    )
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    template_errors = [
        i for i in issues
        if isinstance(i, dict) and i.get("level") == "error" and "combined" in i.get("message", "")
        and "Template variable" in i.get("message", "")
    ]
    assert len(template_errors) == 0


def test_s_set_produces_key():
    """S.set(stage='review') should make {stage} resolvable."""
    from adk_fluent import Agent, S
    from adk_fluent.testing.contracts import check_contracts

    pipeline = (
        S.set(stage="review")
        >> Agent("a").instruct("Current stage: {stage}")
    )
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    template_errors = [
        i for i in issues
        if isinstance(i, dict) and i.get("level") == "error" and "stage" in i.get("message", "")
        and "Template variable" in i.get("message", "")
    ]
    assert len(template_errors) == 0


def test_s_compute_produces_keys():
    """S.compute(summary=...) should make {summary} resolvable."""
    from adk_fluent import Agent, S
    from adk_fluent.testing.contracts import check_contracts

    pipeline = (
        Agent("a").instruct("Write.").outputs("text")
        >> S.compute(summary=lambda s: s.get("text", "")[:50])
        >> Agent("b").instruct("Summary: {summary}")
    )
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    template_errors = [
        i for i in issues
        if isinstance(i, dict) and i.get("level") == "error" and "summary" in i.get("message", "")
        and "Template variable" in i.get("message", "")
    ]
    assert len(template_errors) == 0


def test_s_transform_preserves_key():
    """S.transform('text', str.upper) reads and writes 'text'."""
    from adk_fluent import Agent, S
    from adk_fluent.testing.contracts import check_contracts

    pipeline = (
        Agent("a").instruct("Write.").outputs("text")
        >> S.transform("text", str.upper)
        >> Agent("b").instruct("Here: {text}")
    )
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    template_errors = [
        i for i in issues
        if isinstance(i, dict) and i.get("level") == "error" and "text" in i.get("message", "")
        and "Template variable" in i.get("message", "")
    ]
    assert len(template_errors) == 0


def test_transform_reads_validation():
    """Pass 10: S.rename reads 'draft' — if 'draft' isn't upstream, error."""
    from adk_fluent import Agent, S
    from adk_fluent.testing.contracts import check_contracts

    pipeline = (
        Agent("a").instruct("Write.")  # no .outputs("draft")!
        >> S.rename(draft="input")
        >> Agent("b").instruct("Review the {input}.")
    )
    ir = pipeline.to_ir()
    issues = check_contracts(ir)
    transform_errors = [
        i for i in issues
        if isinstance(i, dict) and i.get("level") == "error" and "draft" in i.get("message", "")
        and "Transform" in i.get("message", "")
    ]
    assert len(transform_errors) >= 1


def test_s_annotations_on_callable():
    """S.* factories attach _reads_keys and _writes_keys to callables."""
    from adk_fluent import S

    fn = S.rename(a="b")
    assert hasattr(fn, "_reads_keys")
    assert hasattr(fn, "_writes_keys")
    assert fn._reads_keys == frozenset({"a"})
    assert fn._writes_keys == frozenset({"b"})


def test_s_set_annotations():
    from adk_fluent import S

    fn = S.set(x=1, y=2)
    assert fn._reads_keys == frozenset()
    assert fn._writes_keys == frozenset({"x", "y"})


def test_s_merge_annotations():
    from adk_fluent import S

    fn = S.merge("a", "b", into="c")
    assert fn._reads_keys == frozenset({"a", "b"})
    assert fn._writes_keys == frozenset({"c"})


def test_s_guard_annotations():
    from adk_fluent import S

    fn = S.guard(lambda s: True)
    assert fn._reads_keys is None  # opaque
    assert fn._writes_keys == frozenset()  # writes nothing


def test_transform_node_carries_reads_keys():
    """TransformNode IR node carries reads_keys from S.* annotation."""
    from adk_fluent import Agent, S

    pipeline = Agent("a") >> S.rename(draft="input") >> Agent("b")
    ir = pipeline.to_ir()
    # Find the TransformNode
    transform = [c for c in ir.children if type(c).__name__ == "TransformNode"]
    assert len(transform) == 1
    assert transform[0].reads_keys == frozenset({"draft"})
    assert transform[0].affected_keys == frozenset({"input"})
