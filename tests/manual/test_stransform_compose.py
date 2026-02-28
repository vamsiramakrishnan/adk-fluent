"""Tests for STransform composable state transforms.

Verifies:
- STransform is callable (backward compat)
- >> operator chains transforms sequentially
- + operator combines transforms in parallel
- Interop with Agent >> STransform >> Agent
- Contract metadata (_reads_keys, _writes_keys) preserved through composition
- S.identity() as neutral element
- S.when() conditional transforms
- S.branch() routing transforms
"""

from adk_fluent._transforms import S, STransform, StateDelta, StateReplacement


# ======================================================================
# Basic callable behavior (backward compat)
# ======================================================================


def test_stransform_is_callable():
    """S.xxx() returns STransform which is callable."""
    t = S.set(a=1)
    assert isinstance(t, STransform)
    result = t({})
    assert isinstance(result, StateDelta)
    assert result.updates == {"a": 1}


def test_stransform_has_metadata():
    """STransform carries _reads_keys and _writes_keys."""
    t = S.set(a=1, b=2)
    assert t._reads_keys == frozenset()
    assert t._writes_keys == frozenset({"a", "b"})


def test_stransform_has_name():
    """STransform has a __name__ for debugging."""
    t = S.pick("a", "b")
    assert "pick" in t.__name__


def test_pick_returns_stransform():
    t = S.pick("a", "b")
    assert isinstance(t, STransform)
    result = t({"a": 1, "b": 2, "c": 3})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"a": 1, "b": 2}


def test_rename_returns_stransform():
    t = S.rename(a="x")
    assert isinstance(t, STransform)
    result = t({"a": 1, "b": 2})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"x": 1, "b": 2}


def test_default_returns_stransform():
    t = S.default(a=99)
    assert isinstance(t, STransform)
    # Key missing -> fill default
    result = t({})
    assert result.updates == {"a": 99}
    # Key present -> no update
    result = t({"a": 1})
    assert result.updates == {}


def test_compute_returns_stransform():
    t = S.compute(doubled=lambda s: s.get("x", 0) * 2)
    assert isinstance(t, STransform)
    result = t({"x": 5})
    assert result.updates == {"doubled": 10}


def test_set_returns_stransform():
    t = S.set(stage="review", counter=0)
    assert isinstance(t, STransform)
    result = t({"existing": True})
    assert result.updates == {"stage": "review", "counter": 0}


def test_capture_returns_stransform():
    t = S.capture("user_input")
    assert isinstance(t, STransform)
    assert t._capture_key == "user_input"
    assert t._writes_keys == frozenset({"user_input"})


# ======================================================================
# Chain operator >> between STransforms
# ======================================================================


def test_chain_set_then_set():
    """>> chains two additive transforms."""
    combined = S.set(a=1) >> S.set(b=2)
    assert isinstance(combined, STransform)
    result = combined({})
    assert isinstance(result, StateDelta)
    assert result.updates == {"b": 2}  # second runs on updated state


def test_chain_pick_then_rename():
    """>> chains pick (replacement) then rename (replacement)."""
    combined = S.pick("a", "b") >> S.rename(a="x")
    assert isinstance(combined, STransform)
    result = combined({"a": 1, "b": 2, "c": 3})
    assert isinstance(result, StateReplacement)
    assert result.new_state == {"x": 1, "b": 2}


def test_chain_three_transforms():
    """>> chains three transforms."""
    combined = S.pick("a", "b") >> S.rename(a="x") >> S.default(y=99)
    assert isinstance(combined, STransform)
    result = combined({"a": 1, "b": 2, "c": 3})
    # pick: {a:1, b:2}, rename: {x:1, b:2}, default: {x:1, b:2, y:99}
    # The final result is a StateDelta with y=99 (default applied to renamed state)
    # Since rename returns StateReplacement and default returns StateDelta,
    # the default runs on {x:1, b:2} and adds y=99
    assert isinstance(result, StateDelta)
    assert result.updates == {"y": 99}


def test_chain_metadata_merges():
    """>> merges reads and writes metadata."""
    t1 = S.rename(a="x")  # reads={"a"}, writes={"x"}
    t2 = S.default(y=1)  # reads={"y"}, writes={"y"}
    combined = t1 >> t2
    # Both reads and writes should be merged
    assert combined._reads_keys is not None
    assert "a" in combined._reads_keys
    assert "y" in combined._reads_keys
    assert combined._writes_keys is not None
    assert "x" in combined._writes_keys
    assert "y" in combined._writes_keys


def test_chain_opaque_reads():
    """>> with opaque reads (None) stays opaque."""
    t1 = S.pick("a")  # reads=None (opaque)
    t2 = S.set(b=1)  # reads=set()
    combined = t1 >> t2
    assert combined._reads_keys is None  # opaque propagates


# ======================================================================
# Combine operator + between STransforms
# ======================================================================


def test_combine_two_deltas():
    """+ merges two StateDelta transforms."""
    combined = S.set(a=1) + S.set(b=2)
    assert isinstance(combined, STransform)
    result = combined({})
    assert isinstance(result, StateDelta)
    assert result.updates == {"a": 1, "b": 2}


def test_combine_delta_overlap():
    """+ with overlapping keys: second wins."""
    combined = S.set(a=1) + S.set(a=99, b=2)
    result = combined({})
    assert result.updates == {"a": 99, "b": 2}


def test_combine_defaults():
    """+ combines default transforms."""
    combined = S.default(a=1) + S.default(b=2)
    result = combined({})
    assert result.updates == {"a": 1, "b": 2}


def test_combine_metadata_merges():
    """+ merges reads and writes metadata."""
    t1 = S.set(a=1)  # reads={}, writes={"a"}
    t2 = S.set(b=2)  # reads={}, writes={"b"}
    combined = t1 + t2
    assert combined._writes_keys == frozenset({"a", "b"})


# ======================================================================
# S.identity() — neutral element
# ======================================================================


def test_identity_noop():
    """S.identity() produces no updates."""
    t = S.identity()
    result = t({"a": 1})
    assert isinstance(result, StateDelta)
    assert result.updates == {}


def test_identity_chain_left():
    """S.identity() >> transform == transform."""
    t = S.identity() >> S.set(a=1)
    result = t({})
    assert result.updates == {"a": 1}


def test_identity_chain_right():
    """transform >> S.identity() preserves transform behavior."""
    t = S.set(a=1) >> S.identity()
    result = t({})
    assert isinstance(result, StateDelta)
    assert result.updates == {}  # identity runs on {a:1} and produces {}


def test_identity_combine():
    """S.identity() + transform == transform behavior."""
    t = S.identity() + S.set(a=1)
    result = t({})
    assert result.updates == {"a": 1}


# ======================================================================
# S.when() — conditional transforms
# ======================================================================


def test_when_true():
    """S.when() applies transform when predicate is True."""
    t = S.when(lambda s: s.get("verbose"), S.set(debug=True))
    result = t({"verbose": True})
    assert result.updates == {"debug": True}


def test_when_false():
    """S.when() skips transform when predicate is False."""
    t = S.when(lambda s: s.get("verbose"), S.set(debug=True))
    result = t({"verbose": False})
    assert isinstance(result, StateDelta)
    assert result.updates == {}


def test_when_exception_safe():
    """S.when() catches predicate exceptions and returns no-op."""
    t = S.when(lambda s: s["missing_key"], S.set(x=1))
    result = t({})
    assert result.updates == {}


# ======================================================================
# S.branch() — routing transforms
# ======================================================================


def test_branch_matches():
    """S.branch() routes to correct transform."""
    t = S.branch(
        "intent",
        booking=S.set(route="book"),
        info=S.set(route="faq"),
    )
    result = t({"intent": "booking"})
    assert result.updates == {"route": "book"}


def test_branch_no_match():
    """S.branch() returns no-op when no match."""
    t = S.branch("intent", booking=S.set(route="book"))
    result = t({"intent": "other"})
    assert isinstance(result, StateDelta)
    assert result.updates == {}


def test_branch_missing_key():
    """S.branch() returns no-op when key missing."""
    t = S.branch("intent", booking=S.set(route="book"))
    result = t({})
    assert result.updates == {}


# ======================================================================
# STransform repr
# ======================================================================


def test_repr():
    """STransform has informative repr."""
    t = S.set(a=1)
    r = repr(t)
    assert "STransform" in r
    assert "set" in r


def test_chain_repr():
    """Chained STransform has descriptive name."""
    t = S.pick("a") >> S.rename(a="x")
    assert "then" in t.__name__


def test_combine_repr():
    """Combined STransform has descriptive name."""
    t = S.set(a=1) + S.set(b=2)
    assert "and" in t.__name__


# ======================================================================
# Interop with Agent >> STransform via BuilderBase
# ======================================================================


def test_agent_rshift_stransform():
    """Agent >> STransform creates a Pipeline."""
    from adk_fluent.agent import Agent

    a = Agent("test_agent", "gemini-2.0-flash").instruct("Hi")
    pipeline = a >> S.pick("result")
    # Should create a Pipeline builder
    assert pipeline is not None
    assert hasattr(pipeline, "_lists")
    assert len(pipeline._lists.get("sub_agents", [])) == 2


def test_stransform_rshift_agent():
    """STransform >> Agent creates a Pipeline."""
    from adk_fluent.agent import Agent

    a = Agent("test_agent", "gemini-2.0-flash").instruct("Hi")
    pipeline = S.set(topic="AI") >> a
    assert pipeline is not None
    assert hasattr(pipeline, "_lists")
    # Should have 2 steps: FnStep(set) and Agent
    assert len(pipeline._lists.get("sub_agents", [])) == 2


def test_stransform_in_pipeline():
    """STransform works in full pipeline: Agent >> S >> Agent."""
    from adk_fluent.agent import Agent

    a1 = Agent("writer", "gemini-2.0-flash").instruct("Write").writes("draft")
    a2 = Agent("editor", "gemini-2.0-flash").instruct("Edit: {input}")
    pipeline = a1 >> S.rename(draft="input") >> a2
    assert pipeline is not None
    # Should have 3 steps
    assert len(pipeline._lists.get("sub_agents", [])) == 3


def test_composed_stransform_in_pipeline():
    """Composed STransform (via >>) works in pipeline."""
    from adk_fluent.agent import Agent

    cleanup = S.pick("draft") >> S.rename(draft="input") >> S.default(tone="formal")
    a1 = Agent("writer", "gemini-2.0-flash").instruct("Write").writes("draft")
    a2 = Agent("editor", "gemini-2.0-flash").instruct("Edit: {input}")
    pipeline = a1 >> cleanup >> a2
    assert pipeline is not None


def test_combined_stransform_in_pipeline():
    """Combined STransform (via +) works in pipeline."""
    from adk_fluent.agent import Agent

    defaults = S.default(language="en") + S.default(tone="formal")
    a1 = Agent("writer", "gemini-2.0-flash")
    pipeline = a1 >> defaults
    assert pipeline is not None
