"""Tests for Agent convenience methods: .reads(), .writes().

Verifies:
- .reads() sets _context_spec via C.from_state()
- .reads() composes with existing .context() spec
- .writes() sets output_key
- .reads() and .writes() chain naturally
- Copy-on-write semantics preserved
"""

from adk_fluent.agent import Agent
from adk_fluent._context import C, CComposite, CFromState, CWindow


# ======================================================================
# .reads() — shorthand for .context(C.from_state(...))
# ======================================================================


def test_reads_sets_context_spec():
    """Agent.reads() sets _context_spec to CFromState."""
    a = Agent("writer", "gemini-2.0-flash").reads("topic", "tone")
    spec = a._config.get("_context_spec")
    assert spec is not None
    assert isinstance(spec, CFromState)
    assert set(spec.keys) == {"topic", "tone"}


def test_reads_composes_with_context():
    """Agent.reads() after .context() unions the specs."""
    a = Agent("writer", "gemini-2.0-flash").context(C.window(n=3)).reads("topic")
    spec = a._config.get("_context_spec")
    assert spec is not None
    # Should be CComposite (union of CWindow + CFromState)
    assert isinstance(spec, CComposite)
    blocks = spec.blocks
    assert len(blocks) == 2
    assert isinstance(blocks[0], CWindow)
    assert isinstance(blocks[1], CFromState)


def test_reads_multiple_calls_compose():
    """Multiple .reads() calls compose additively."""
    a = Agent("writer", "gemini-2.0-flash").reads("topic").reads("tone")
    spec = a._config.get("_context_spec")
    assert spec is not None
    # Should be CComposite (union of two CFromState)
    assert isinstance(spec, CComposite)


# ======================================================================
# .writes() — shorthand for .save_as()
# ======================================================================


def test_writes_sets_output_key():
    """Agent.writes() sets the output_key config."""
    a = Agent("researcher", "gemini-2.0-flash").writes("findings")
    assert a._config["output_key"] == "findings"


def test_writes_equivalent_to_save_as():
    """Agent.writes() is equivalent to .save_as()."""
    a1 = Agent("a", "gemini-2.0-flash").writes("out")
    a2 = Agent("a", "gemini-2.0-flash").save_as("out")
    assert a1._config["output_key"] == a2._config["output_key"]


# ======================================================================
# Chaining .reads() and .writes()
# ======================================================================


def test_reads_writes_chain():
    """Agent.reads().writes() chains naturally."""
    a = Agent("writer", "gemini-2.0-flash").reads("topic", "tone").writes("draft")
    assert a._config["output_key"] == "draft"
    spec = a._config.get("_context_spec")
    assert isinstance(spec, CFromState)
    assert set(spec.keys) == {"topic", "tone"}


def test_pipeline_with_reads_writes():
    """Full pipeline with .reads() and .writes() builds correctly."""
    researcher = Agent("researcher", "gemini-2.0-flash").instruct("Research").writes("findings")
    writer = Agent("writer", "gemini-2.0-flash").reads("findings").instruct("Write").writes("draft")
    reviewer = Agent("reviewer", "gemini-2.0-flash").reads("draft").instruct("Review")
    pipeline = researcher >> writer >> reviewer
    assert pipeline is not None
    # Verify sub-agents
    assert len(pipeline._lists.get("sub_agents", [])) == 3


# ======================================================================
# Copy-on-write semantics
# ======================================================================


def test_reads_preserves_cow():
    """Agent.reads() respects copy-on-write when frozen."""
    base = Agent("writer", "gemini-2.0-flash").instruct("Write")
    # Freeze via operator
    pipeline = base >> Agent("other", "gemini-2.0-flash")
    # Mutation on frozen builder should fork
    variant = base.reads("topic")
    assert variant is not base
    assert variant._config.get("_context_spec") is not None
    # Original should not be affected
    assert base._config.get("_context_spec") is None


def test_writes_preserves_cow():
    """Agent.writes() respects copy-on-write when frozen."""
    base = Agent("writer", "gemini-2.0-flash")
    pipeline = base >> Agent("other", "gemini-2.0-flash")
    variant = base.writes("draft")
    assert variant is not base
    assert variant._config.get("output_key") == "draft"
    assert base._config.get("output_key") is None
