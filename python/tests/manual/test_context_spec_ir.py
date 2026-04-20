"""Tests for context_spec preservation in IR (v0.9.1)."""


def test_context_spec_preserved_in_agent_node():
    """context_spec survives builder -> IR conversion."""
    from adk_fluent import Agent, C

    a = Agent("a").context(C.user_only())
    ir = a.to_ir()
    assert ir.context_spec is not None
    assert ir.context_spec._kind == "user_only"


def test_context_spec_none_by_default():
    """AgentNode has None context_spec when no .context() was called."""
    from adk_fluent import Agent

    ir = Agent("a").to_ir()
    assert ir.context_spec is None


def test_context_spec_window_preserved():
    from adk_fluent import Agent, C

    ir = Agent("a").context(C.window(n=3)).to_ir()
    assert ir.context_spec is not None
    assert ir.context_spec._kind == "window"
    assert ir.context_spec.n == 3


def test_context_spec_from_state_preserved():
    from adk_fluent import Agent, C

    ir = Agent("a").context(C.from_state("topic", "style")).to_ir()
    assert ir.context_spec is not None
    assert ir.context_spec._kind == "from_state"
    assert ir.context_spec.keys == ("topic", "style")


def test_context_spec_from_agents_preserved():
    from adk_fluent import Agent, C

    ir = Agent("a").context(C.from_agents("writer", "editor")).to_ir()
    assert ir.context_spec is not None
    assert ir.context_spec._kind == "from_agents"
    assert ir.context_spec.agents == ("writer", "editor")


def test_context_spec_composite_preserved():
    from adk_fluent import Agent, C

    ir = Agent("a").context(C.window(n=3) | C.from_state("topic")).to_ir()
    assert ir.context_spec is not None
    # Composite wraps multiple blocks
    assert type(ir.context_spec).__name__ == "CComposite"


def test_context_spec_in_pipeline_children():
    """context_spec preserved on children within a pipeline."""
    from adk_fluent import Agent, C

    pipeline = Agent("a").writes("x") >> Agent("b").context(C.user_only())
    ir = pipeline.to_ir()
    child_b = ir.children[1]
    assert child_b.context_spec is not None
    assert child_b.context_spec._kind == "user_only"


def test_context_spec_include_contents_matches():
    """context_spec's include_contents matches the IR node's include_contents."""
    from adk_fluent import Agent, C

    ir = Agent("a").context(C.from_state("x")).to_ir()
    # CFromState is a pure data-injection transform — neutral on history
    assert ir.context_spec.include_contents == "default"
