"""Tests for graph visualization."""


def test_single_agent_mermaid():
    """Single agent produces minimal mermaid graph."""
    from adk_fluent import Agent

    a = Agent("greeter")
    result = a.to_mermaid()
    assert "greeter" in result
    assert "graph" in result


def test_pipeline_mermaid():
    """Pipeline shows sequential edges."""
    from adk_fluent import Agent

    pipeline = Agent("a") >> Agent("b") >> Agent("c")
    result = pipeline.to_mermaid()
    assert "a" in result
    assert "b" in result
    assert "c" in result
    assert "-->" in result


def test_fanout_mermaid():
    """FanOut shows parallel branches."""
    from adk_fluent import Agent

    fanout = Agent("a") | Agent("b")
    result = fanout.to_mermaid()
    assert "a" in result
    assert "b" in result


def test_loop_mermaid():
    """Loop shows iteration marker."""
    from adk_fluent import Agent

    loop = Agent("a") * 3
    result = loop.to_mermaid()
    assert "a" in result
    assert "loop" in result


def test_contract_edges_in_mermaid():
    """Mermaid includes data-flow annotations for produces/consumes."""
    from pydantic import BaseModel

    from adk_fluent import Agent

    class Intent(BaseModel):
        category: str

    pipeline = Agent("a").produces(Intent) >> Agent("b").consumes(Intent)
    result = pipeline.to_mermaid()
    assert "Intent" in result


def test_to_mermaid_on_builder():
    """to_mermaid() is available on BuilderBase."""
    from adk_fluent import Agent

    a = Agent("test")
    assert hasattr(a, "to_mermaid")


def test_exports_phase4():
    """Phase 4 exports are available from top-level."""
    from adk_fluent.di import inject_resources
    from adk_fluent.testing import check_contracts, mock_backend

    assert callable(check_contracts)
    assert callable(mock_backend)
    assert callable(inject_resources)
