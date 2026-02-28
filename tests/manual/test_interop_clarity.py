"""Tests for output method interop clarity.

Verifies:
- DataFlow snapshot accurately reflects all 4 concerns
- .data_flow() method works on all builder types
- Build-time confusion detection catches common patterns
- Interplay guide is accessible and correct
"""

from pydantic import BaseModel

from adk_fluent.agent import Agent
from adk_fluent._context import C
from adk_fluent._interop import DataFlow, _extract_data_flow, check_output_interop, INTERPLAY_GUIDE


class FindingsModel(BaseModel):
    findings: str
    sources: list[str]


class WriterInput(BaseModel):
    topic: str
    tone: str


# ======================================================================
# DataFlow snapshot accuracy
# ======================================================================


def test_data_flow_defaults():
    """DataFlow shows correct defaults when nothing is set."""
    agent = Agent("test", "gemini-2.0-flash")
    df = _extract_data_flow(agent)
    assert isinstance(df, DataFlow)
    assert "full conversation history" in df.sees
    assert df.stores is None
    assert "plain text" in df.format
    assert df.contract_produces is None
    assert df.contract_consumes is None


def test_data_flow_with_reads():
    """DataFlow shows context concern correctly."""
    agent = Agent("test", "gemini-2.0-flash").reads("topic", "tone")
    df = _extract_data_flow(agent)
    assert "topic" in df.sees
    assert "tone" in df.sees


def test_data_flow_with_writes():
    """DataFlow shows storage concern correctly."""
    agent = Agent("test", "gemini-2.0-flash").writes("findings")
    df = _extract_data_flow(agent)
    assert df.stores == "state['findings']"


def test_data_flow_with_output():
    """DataFlow shows format concern correctly."""
    agent = Agent("test", "gemini-2.0-flash").output(FindingsModel)
    df = _extract_data_flow(agent)
    assert "FindingsModel" in df.format
    assert "structured JSON" in df.format


def test_data_flow_with_produces():
    """DataFlow shows contract concern correctly."""
    agent = Agent("test", "gemini-2.0-flash").produces(FindingsModel)
    df = _extract_data_flow(agent)
    assert "FindingsModel" in df.contract_produces
    assert "findings" in df.contract_produces
    assert "sources" in df.contract_produces


def test_data_flow_with_consumes():
    """DataFlow shows consumes contract correctly."""
    agent = Agent("test", "gemini-2.0-flash").consumes(WriterInput)
    df = _extract_data_flow(agent)
    assert "WriterInput" in df.contract_consumes
    assert "topic" in df.contract_consumes


def test_data_flow_all_four_concerns():
    """DataFlow shows all four concerns when all are set."""
    agent = (
        Agent("test", "gemini-2.0-flash")
        .reads("topic")
        .writes("findings")
        .output(FindingsModel)
        .produces(FindingsModel)
        .consumes(WriterInput)
    )
    df = _extract_data_flow(agent)
    assert "topic" in df.sees
    assert df.stores == "state['findings']"
    assert "FindingsModel" in df.format
    assert "FindingsModel" in df.contract_produces
    assert "WriterInput" in df.contract_consumes


# ======================================================================
# .data_flow() method on BuilderBase
# ======================================================================


def test_data_flow_method_exists():
    """Agent has .data_flow() method."""
    agent = Agent("test", "gemini-2.0-flash").writes("out")
    df = agent.data_flow()
    assert isinstance(df, DataFlow)
    assert df.stores == "state['out']"


def test_data_flow_str():
    """DataFlow __str__ produces readable output."""
    agent = Agent("test", "gemini-2.0-flash").reads("topic").writes("findings")
    df = agent.data_flow()
    text = str(df)
    assert "Data Flow:" in text
    assert "Sees" in text
    assert "Stores" in text
    assert "Format" in text
    assert "topic" in text
    assert "findings" in text


def test_data_flow_repr():
    """DataFlow __repr__ is informative."""
    agent = Agent("test", "gemini-2.0-flash")
    df = agent.data_flow()
    r = repr(df)
    assert "DataFlow" in r


# ======================================================================
# Build-time confusion detection
# ======================================================================


def test_detect_produces_without_writes():
    """Detects .produces() without .writes() — contract but no storage."""
    config = {"name": "test", "_produces": FindingsModel}
    issues = check_output_interop(config)
    assert len(issues) >= 1
    assert any("produces" in i["message"] and "writes" in i["message"] for i in issues)


def test_detect_output_without_writes():
    """Detects .output() without .writes() — structured but not stored."""
    config = {"name": "test", "_output_schema": FindingsModel}
    issues = check_output_interop(config)
    assert len(issues) >= 1
    assert any("structured" in i["message"].lower() or "output" in i["message"].lower() for i in issues)


def test_detect_consumes_without_reads():
    """Detects .consumes() without .reads() — contract but no context."""
    config = {"name": "test", "_consumes": WriterInput}
    issues = check_output_interop(config)
    assert len(issues) >= 1
    assert any("consumes" in i["message"] for i in issues)


def test_no_issues_when_clean():
    """No issues when config is well-formed."""
    config = {"name": "test", "output_key": "findings"}
    issues = check_output_interop(config)
    assert len(issues) == 0


def test_no_issues_for_minimal_agent():
    """No issues for a bare agent."""
    config = {"name": "test"}
    issues = check_output_interop(config)
    assert len(issues) == 0


def test_no_issues_reads_writes_output():
    """No issues when all concerns are properly set."""
    config = {
        "name": "test",
        "_context_spec": C.from_state("topic"),
        "output_key": "findings",
        "_output_schema": FindingsModel,
        "_produces": FindingsModel,
        "_consumes": WriterInput,
    }
    issues = check_output_interop(config)
    # produces with writes → no issue, consumes with context → no issue
    assert not any(i["level"] == "error" for i in issues)


def test_detect_conflicting_schemas():
    """Detects different schemas for .output_schema() and .output()."""

    class OtherModel(BaseModel):
        other: str

    config = {
        "name": "test",
        "output_schema": FindingsModel,
        "_output_schema": OtherModel,
    }
    issues = check_output_interop(config)
    assert len(issues) >= 1
    assert any(i["level"] == "warning" for i in issues)


# ======================================================================
# Interplay guide
# ======================================================================


def test_interplay_guide_exists():
    """INTERPLAY_GUIDE is a non-empty string."""
    assert isinstance(INTERPLAY_GUIDE, str)
    assert len(INTERPLAY_GUIDE) > 100


def test_interplay_guide_covers_all_concerns():
    """INTERPLAY_GUIDE mentions all four concerns."""
    assert "Context" in INTERPLAY_GUIDE or "context" in INTERPLAY_GUIDE
    assert "Storage" in INTERPLAY_GUIDE or "storage" in INTERPLAY_GUIDE
    assert "Format" in INTERPLAY_GUIDE or "format" in INTERPLAY_GUIDE
    assert "Contract" in INTERPLAY_GUIDE or "contract" in INTERPLAY_GUIDE


def test_interplay_guide_covers_methods():
    """INTERPLAY_GUIDE mentions key methods."""
    assert ".reads()" in INTERPLAY_GUIDE
    assert ".writes()" in INTERPLAY_GUIDE
    assert ".output()" in INTERPLAY_GUIDE
    assert ".produces()" in INTERPLAY_GUIDE
    assert ".consumes()" in INTERPLAY_GUIDE


def test_interplay_guide_covers_defaults():
    """INTERPLAY_GUIDE documents default behavior."""
    assert "default" in INTERPLAY_GUIDE.lower()
    assert "full conversation" in INTERPLAY_GUIDE.lower() or "full history" in INTERPLAY_GUIDE.lower()
