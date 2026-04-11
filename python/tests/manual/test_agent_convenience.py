"""Tests for Agent convenience methods: .reads(), .writes().

Verifies:
- .reads() sets _context_spec via C.from_state()
- .reads() composes with existing .context() spec
- .writes() sets output_key
- .reads() and .writes() chain naturally
- Copy-on-write semantics preserved
"""

from adk_fluent._context import C, CComposite, CFromState, CTransform, CWindow
from adk_fluent.agent import Agent

# ======================================================================
# .reads() — shorthand for .context(C.none() + C.from_state(...))
# ======================================================================


def test_reads_sets_context_spec():
    """Agent.reads() sets _context_spec to CComposite(C.none() + C.from_state(...))."""
    a = Agent("writer", "gemini-2.0-flash").reads("topic", "tone")
    spec = a._config.get("_context_spec")
    assert spec is not None
    # .reads() wraps C.none() + C.from_state(...) → CComposite
    assert isinstance(spec, CComposite)
    blocks = spec.blocks
    assert len(blocks) == 2
    assert isinstance(blocks[0], CTransform)  # C.none()
    assert blocks[0].include_contents == "none"
    assert isinstance(blocks[1], CFromState)
    assert set(blocks[1].keys) == {"topic", "tone"}


def test_reads_composes_with_context():
    """Agent.reads() after .context() unions the specs."""
    a = Agent("writer", "gemini-2.0-flash").context(C.window(n=3)).reads("topic")
    spec = a._config.get("_context_spec")
    assert spec is not None
    # Should be CComposite (union of CWindow + C.none() + CFromState)
    assert isinstance(spec, CComposite)
    blocks = spec.blocks
    assert len(blocks) == 3
    assert isinstance(blocks[0], CWindow)
    assert isinstance(blocks[1], CTransform)  # C.none()
    assert isinstance(blocks[2], CFromState)


def test_reads_multiple_calls_compose():
    """Multiple .reads() calls compose additively."""
    a = Agent("writer", "gemini-2.0-flash").reads("topic").reads("tone")
    spec = a._config.get("_context_spec")
    assert spec is not None
    # Should be CComposite (union of two CFromState)
    assert isinstance(spec, CComposite)


# ======================================================================
# .writes() — shorthand for .writes()
# ======================================================================


def test_writes_sets_output_key():
    """Agent.writes() sets the output_key config."""
    a = Agent("researcher", "gemini-2.0-flash").writes("findings")
    assert a._config["output_key"] == "findings"


def test_writes_equivalent_to_save_as():
    """Agent.writes() is equivalent to .writes()."""
    a1 = Agent("a", "gemini-2.0-flash").writes("out")
    a2 = Agent("a", "gemini-2.0-flash").writes("out")
    assert a1._config["output_key"] == a2._config["output_key"]


# ======================================================================
# Chaining .reads() and .writes()
# ======================================================================


def test_reads_writes_chain():
    """Agent.reads().writes() chains naturally."""
    a = Agent("writer", "gemini-2.0-flash").reads("topic", "tone").writes("draft")
    assert a._config["output_key"] == "draft"
    spec = a._config.get("_context_spec")
    # .reads() produces CComposite(C.none() + C.from_state(...))
    assert isinstance(spec, CComposite)
    from_state_block = spec.blocks[1]
    assert isinstance(from_state_block, CFromState)
    assert set(from_state_block.keys) == {"topic", "tone"}


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
    _pipeline = base >> Agent("other", "gemini-2.0-flash")  # noqa: F841 — triggers freeze
    # Mutation on frozen builder should fork
    variant = base.reads("topic")
    assert variant is not base
    assert variant._config.get("_context_spec") is not None
    # Original should not be affected
    assert base._config.get("_context_spec") is None


# ======================================================================
# Composability: .reads() + .context() orthogonality
# ======================================================================


def test_reads_suppresses_history_by_default():
    """.reads() suppresses history (the common pipeline case)."""
    a = Agent("writer", "gemini-2.0-flash").reads("findings")
    built = a.build()
    assert built.include_contents == "none"


def test_reads_keep_history():
    """.reads(keep_history=True) injects state without suppressing history."""
    a = Agent("writer", "gemini-2.0-flash").reads("findings", keep_history=True)
    built = a.build()
    assert built.include_contents == "default"


def test_from_state_alone_keeps_history():
    """C.from_state() is neutral — does not suppress history."""
    a = Agent("writer", "gemini-2.0-flash").context(C.from_state("findings"))
    built = a.build()
    assert built.include_contents == "default"


def test_from_state_composes_with_window():
    """C.window() + C.from_state() suppresses (window's opinion wins)."""
    a = Agent("writer", "gemini-2.0-flash").context(C.window(n=3) + C.from_state("findings"))
    built = a.build()
    assert built.include_contents == "none"


def test_from_state_composes_with_none():
    """C.none() + C.from_state() suppresses (none's opinion wins)."""
    a = Agent("writer", "gemini-2.0-flash").context(C.none() + C.from_state("findings"))
    built = a.build()
    assert built.include_contents == "none"


def test_two_neutral_transforms_keep_history():
    """Two neutral transforms composed keep history."""
    a = Agent("writer", "gemini-2.0-flash").context(C.from_state("x") + C.template("Hello {x}"))
    built = a.build()
    assert built.include_contents == "default"


def test_writes_preserves_cow():
    """Agent.writes() respects copy-on-write when frozen."""
    base = Agent("writer", "gemini-2.0-flash")
    _pipeline = base >> Agent("other", "gemini-2.0-flash")  # noqa: F841 — triggers freeze
    variant = base.writes("draft")
    assert variant is not base
    assert variant._config.get("output_key") == "draft"
    assert base._config.get("output_key") is None
