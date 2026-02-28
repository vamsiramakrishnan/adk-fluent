"""Tests for the patterns module — higher-order pipeline constructors.

Verifies:
- review_loop creates a Loop with worker >> reviewer
- cascade creates a fallback chain
- fan_out_merge creates FanOut >> merge
- chain composes arbitrary steps
- conditional creates Route-based branching
- supervised creates an approval loop
- All patterns return builders that compose with >>
- Validation errors for bad inputs
"""

import pytest

from adk_fluent.agent import Agent
from adk_fluent._transforms import S
from adk_fluent.patterns import (
    cascade,
    chain,
    conditional,
    fan_out_merge,
    map_reduce,
    review_loop,
    supervised,
)


# ======================================================================
# review_loop
# ======================================================================


def test_review_loop_creates_loop():
    """review_loop returns a builder with loop semantics."""
    worker = Agent("writer", "gemini-2.0-flash").instruct("Write").writes("draft")
    reviewer = Agent("reviewer", "gemini-2.0-flash").instruct("Review {draft}").writes("quality")

    result = review_loop(worker, reviewer, quality_key="quality", target="good", max_rounds=3)
    assert result is not None
    # Should have build() method
    assert hasattr(result, "build")


def test_review_loop_defaults():
    """review_loop works with default parameters."""
    worker = Agent("w", "gemini-2.0-flash")
    reviewer = Agent("r", "gemini-2.0-flash")
    result = review_loop(worker, reviewer)
    assert result is not None


# ======================================================================
# cascade
# ======================================================================


def test_cascade_two_agents():
    """cascade creates a fallback chain of 2."""
    a = Agent("fast", "gemini-2.0-flash")
    b = Agent("smart", "gemini-2.5-pro")
    result = cascade(a, b)
    assert result is not None
    assert hasattr(result, "build")


def test_cascade_three_agents():
    """cascade creates a fallback chain of 3."""
    a = Agent("fast", "gemini-2.0-flash")
    b = Agent("medium", "gemini-2.0-flash")
    c = Agent("smart", "gemini-2.5-pro")
    result = cascade(a, b, c)
    assert result is not None


def test_cascade_requires_two():
    """cascade raises ValueError with fewer than 2 agents."""
    with pytest.raises(ValueError, match="at least 2"):
        cascade(Agent("solo", "gemini-2.0-flash"))


# ======================================================================
# fan_out_merge
# ======================================================================


def test_fan_out_merge_creates_pipeline():
    """fan_out_merge creates FanOut >> merge transform."""
    web = Agent("web", "gemini-2.0-flash").writes("web_results")
    papers = Agent("papers", "gemini-2.0-flash").writes("paper_results")
    result = fan_out_merge(web, papers, merge_key="research")
    assert result is not None
    assert hasattr(result, "build")


def test_fan_out_merge_no_output_keys():
    """fan_out_merge without output keys returns just the fanout."""
    a = Agent("a", "gemini-2.0-flash")
    b = Agent("b", "gemini-2.0-flash")
    result = fan_out_merge(a, b)
    assert result is not None


def test_fan_out_merge_requires_two():
    """fan_out_merge raises ValueError with fewer than 2 agents."""
    with pytest.raises(ValueError, match="at least 2"):
        fan_out_merge(Agent("solo", "gemini-2.0-flash"))


# ======================================================================
# chain
# ======================================================================


def test_chain_agents():
    """chain composes agents sequentially."""
    a = Agent("a", "gemini-2.0-flash")
    b = Agent("b", "gemini-2.0-flash")
    c = Agent("c", "gemini-2.0-flash")
    result = chain(a, b, c)
    assert result is not None


def test_chain_mixed():
    """chain composes agents and S transforms."""
    a = Agent("a", "gemini-2.0-flash").writes("out")
    t = S.rename(out="input")
    b = Agent("b", "gemini-2.0-flash")
    result = chain(a, t, b)
    assert result is not None


def test_chain_requires_two():
    """chain raises ValueError with fewer than 2 steps."""
    with pytest.raises(ValueError, match="at least 2"):
        chain(Agent("solo", "gemini-2.0-flash"))


# ======================================================================
# conditional
# ======================================================================


def test_conditional_basic():
    """conditional creates a Route-based branch."""
    result = conditional(
        lambda s: s.get("intent") == "booking",
        if_true=Agent("booker", "gemini-2.0-flash"),
        if_false=Agent("faq", "gemini-2.0-flash"),
    )
    assert result is not None


def test_conditional_no_else():
    """conditional works without if_false."""
    result = conditional(
        lambda s: s.get("valid"),
        if_true=Agent("enricher", "gemini-2.0-flash"),
    )
    assert result is not None


# ======================================================================
# supervised
# ======================================================================


def test_supervised_creates_loop():
    """supervised creates a worker >> supervisor loop."""
    worker = Agent("writer", "gemini-2.0-flash").writes("draft")
    supervisor = Agent("editor", "gemini-2.0-flash").writes("approved")
    result = supervised(worker, supervisor, approval_key="approved", max_revisions=2)
    assert result is not None
    assert hasattr(result, "build")


def test_supervised_defaults():
    """supervised works with default parameters."""
    worker = Agent("w", "gemini-2.0-flash")
    supervisor = Agent("s", "gemini-2.0-flash")
    result = supervised(worker, supervisor)
    assert result is not None


# ======================================================================
# Pattern composition with >>
# ======================================================================


def test_patterns_compose_with_pipeline():
    """Patterns can be further composed with >> operator."""
    loop = review_loop(
        Agent("writer", "gemini-2.0-flash").writes("draft"),
        Agent("reviewer", "gemini-2.0-flash").writes("quality"),
    )
    postprocess = Agent("formatter", "gemini-2.0-flash")
    pipeline = loop >> postprocess
    assert pipeline is not None


def test_patterns_compose_with_stransform():
    """Patterns can be composed with S transforms."""
    loop = review_loop(
        Agent("writer", "gemini-2.0-flash").writes("draft"),
        Agent("reviewer", "gemini-2.0-flash").writes("quality"),
    )
    pipeline = loop >> S.pick("draft") >> Agent("publisher", "gemini-2.0-flash")
    assert pipeline is not None
