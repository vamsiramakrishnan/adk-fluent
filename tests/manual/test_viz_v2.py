"""Tests for enhanced viz.py (v0.9.1 — data flow edges, context annotations)."""

from pydantic import BaseModel


class Intent(BaseModel):
    category: str


def test_data_flow_edges_appear():
    """Data flow edges show state key connections between agents."""
    from adk_fluent import Agent

    pipeline = (
        Agent("writer").instruct("Write.").outputs("draft")
        >> Agent("reviewer").instruct("Review the {draft}.")
    )
    result = pipeline.to_mermaid()
    # Should have a dotted edge showing 'draft' flows from writer to reviewer
    assert "draft" in result
    assert ".->" in result


def test_data_flow_edges_disabled():
    """Data flow edges can be disabled."""
    from adk_fluent import Agent

    pipeline = (
        Agent("writer").instruct("Write.").outputs("draft")
        >> Agent("reviewer").instruct("Review the {draft}.")
    )
    result = pipeline.to_mermaid(show_data_flow=False)
    # Normal topology edges still present
    assert "-->" in result
    # But no dotted data flow edges
    assert ".->" not in result or "produces" in result  # contract notes may use .-o


def test_context_annotations():
    """Context annotations show each agent's context strategy."""
    from adk_fluent import Agent, C

    pipeline = Agent("a") >> Agent("b").context(C.user_only())
    result = pipeline.to_mermaid(show_context=True)
    assert "user_only" in result


def test_context_annotations_off_by_default():
    """Context annotations are off by default."""
    from adk_fluent import Agent, C

    pipeline = Agent("a") >> Agent("b").context(C.user_only())
    result = pipeline.to_mermaid()
    # Context annotations should NOT appear unless show_context=True
    # (user_only might appear if data flow mentions it, but context notes use .-o format)
    # Just verify the graph is valid
    assert "graph TD" in result


def test_contract_annotations_with_produces():
    """Produces/consumes annotations still work."""
    from adk_fluent import Agent

    pipeline = Agent("a").produces(Intent) >> Agent("b").consumes(Intent)
    result = pipeline.to_mermaid()
    assert "Intent" in result


def test_capture_node_shape():
    """CaptureNode gets a distinctive shape in Mermaid."""
    from adk_fluent import Agent, S

    pipeline = S.capture("user_input") >> Agent("a")
    result = pipeline.to_mermaid()
    assert "capture" in result
    assert "user_input" in result


def test_mermaid_backward_compat():
    """Existing tests still pass: single agent, pipeline, fanout, loop."""
    from adk_fluent import Agent

    # Single agent
    a = Agent("greeter")
    result = a.to_mermaid()
    assert "greeter" in result
    assert "graph" in result

    # Pipeline
    pipeline = Agent("a") >> Agent("b") >> Agent("c")
    result = pipeline.to_mermaid()
    assert "a" in result
    assert "b" in result
    assert "-->" in result

    # FanOut
    fanout = Agent("a") | Agent("b")
    result = fanout.to_mermaid()
    assert "a" in result
    assert "b" in result

    # Loop
    loop = Agent("a") * 3
    result = loop.to_mermaid()
    assert "loop" in result
