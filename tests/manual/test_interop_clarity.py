"""Tests for output method interop clarity.

Verifies:
- DataFlow snapshot accurately reflects all 5 concerns
- .data_flow() method works on all builder types
- .accepts() and .returns() set correct config keys
- .llm_anatomy() produces readable output
- Build-time confusion detection catches common patterns
- Interplay guide and LLM call anatomy are accessible and correct
"""

from pydantic import BaseModel

from adk_fluent._context import C
from adk_fluent._interop import (
    INTERPLAY_GUIDE,
    LLM_CALL_ANATOMY,
    DataFlow,
    _extract_data_flow,
    check_output_interop,
)
from adk_fluent.agent import Agent


class FindingsModel(BaseModel):
    findings: str
    sources: list[str]


class WriterInput(BaseModel):
    topic: str
    tone: str


class SearchQuery(BaseModel):
    query: str
    max_results: int = 10


# ======================================================================
# DataFlow snapshot accuracy (five concerns)
# ======================================================================


def test_data_flow_defaults():
    """DataFlow shows correct defaults when nothing is set."""
    agent = Agent("test", "gemini-2.0-flash")
    df = _extract_data_flow(agent)
    assert isinstance(df, DataFlow)
    assert "full conversation history" in df.sees
    assert df.accepts is None
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


def test_data_flow_with_accepts():
    """DataFlow shows input concern correctly."""
    agent = Agent("test", "gemini-2.0-flash").accepts(SearchQuery)
    df = _extract_data_flow(agent)
    assert df.accepts is not None
    assert "SearchQuery" in df.accepts
    assert "query" in df.accepts


def test_data_flow_with_writes():
    """DataFlow shows storage concern correctly."""
    agent = Agent("test", "gemini-2.0-flash").writes("findings")
    df = _extract_data_flow(agent)
    assert df.stores == "state['findings']"


def test_data_flow_with_output():
    """DataFlow shows format concern correctly via .output()."""
    agent = Agent("test", "gemini-2.0-flash").output(FindingsModel)
    df = _extract_data_flow(agent)
    assert "FindingsModel" in df.format
    assert "structured JSON" in df.format


def test_data_flow_with_returns():
    """DataFlow shows format concern correctly via .returns()."""
    agent = Agent("test", "gemini-2.0-flash").returns(FindingsModel)
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


def test_data_flow_all_five_concerns():
    """DataFlow shows all five concerns when all are set."""
    agent = (
        Agent("test", "gemini-2.0-flash")
        .reads("topic")
        .accepts(WriterInput)
        .returns(FindingsModel)
        .writes("findings")
        .produces(FindingsModel)
        .consumes(WriterInput)
    )
    df = _extract_data_flow(agent)
    assert "topic" in df.sees
    assert "WriterInput" in df.accepts
    assert df.stores == "state['findings']"
    assert "FindingsModel" in df.format
    assert "FindingsModel" in df.contract_produces
    assert "WriterInput" in df.contract_consumes


# ======================================================================
# .accepts() and .returns() methods
# ======================================================================


def test_accepts_sets_input_schema():
    """.accepts() sets input_schema in config."""
    agent = Agent("test", "gemini-2.0-flash").accepts(SearchQuery)
    assert agent._config["input_schema"] is SearchQuery


def test_returns_sets_output_schema():
    """.returns() sets _output_schema in config."""
    agent = Agent("test", "gemini-2.0-flash").returns(FindingsModel)
    assert agent._config["_output_schema"] is FindingsModel


def test_returns_same_as_output():
    """.returns() and .output() set the same config key."""
    a1 = Agent("test1", "gemini-2.0-flash").returns(FindingsModel)
    a2 = Agent("test2", "gemini-2.0-flash").output(FindingsModel)
    assert a1._config["_output_schema"] is a2._config["_output_schema"]


def test_builder_chain_reads_accepts_returns_writes():
    """Full builder chain with all five concerns reads naturally."""
    agent = (
        Agent("classifier", "gemini-2.0-flash")
        .instruct("Classify the user query: {query}")
        .reads("query")
        .accepts(SearchQuery)
        .returns(FindingsModel)
        .writes("result")
    )
    assert agent._config.get("_context_spec") is not None
    assert agent._config["input_schema"] is SearchQuery
    assert agent._config["_output_schema"] is FindingsModel
    assert agent._config["output_key"] == "result"


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
    """DataFlow __str__ produces readable five-concern output."""
    agent = Agent("test", "gemini-2.0-flash").reads("topic").writes("findings")
    df = agent.data_flow()
    text = str(df)
    assert "Data Flow:" in text
    assert "reads:" in text
    assert "accepts:" in text
    assert "returns:" in text
    assert "writes:" in text
    assert "contract:" in text
    assert "topic" in text
    assert "findings" in text


def test_data_flow_repr():
    """DataFlow __repr__ is informative."""
    agent = Agent("test", "gemini-2.0-flash")
    df = agent.data_flow()
    r = repr(df)
    assert "DataFlow" in r
    assert "accepts=" in r


# ======================================================================
# .llm_anatomy() method
# ======================================================================


def test_llm_anatomy_basic():
    """Agent has .llm_anatomy() method returning formatted string."""
    agent = Agent("test", "gemini-2.0-flash").instruct("Hello")
    anatomy = agent.llm_anatomy()
    assert "LLM Call Anatomy: test" in anatomy
    assert "1. System:" in anatomy
    assert "2. History:" in anatomy
    assert "3. Context:" in anatomy
    assert "4. Tools:" in anatomy
    assert "5. Constraint:" in anatomy
    assert "6. After:" in anatomy


def test_llm_anatomy_with_reads():
    """LLM anatomy shows history suppression when .reads() is used."""
    agent = Agent("test", "gemini-2.0-flash").reads("topic")
    anatomy = agent.llm_anatomy()
    assert "SUPPRESSED" in anatomy


def test_llm_anatomy_with_returns():
    """LLM anatomy shows output constraint when .returns() is used."""
    agent = Agent("test", "gemini-2.0-flash").returns(FindingsModel)
    anatomy = agent.llm_anatomy()
    assert "FindingsModel" in anatomy
    assert "DISABLED" in anatomy  # tools disabled


def test_llm_anatomy_with_writes():
    """LLM anatomy shows state storage after response."""
    agent = Agent("test", "gemini-2.0-flash").writes("result")
    anatomy = agent.llm_anatomy()
    assert 'state["result"]' in anatomy


def test_llm_anatomy_default():
    """LLM anatomy shows defaults for bare agent."""
    agent = Agent("test", "gemini-2.0-flash")
    anatomy = agent.llm_anatomy()
    assert "FULL conversation history" in anatomy
    assert "none — free-form text" in anatomy


def test_llm_anatomy_with_template_vars():
    """LLM anatomy shows template variables in instruction."""
    agent = Agent("test", "gemini-2.0-flash").instruct("Classify: {query}")
    anatomy = agent.llm_anatomy()
    assert "{query}" in anatomy
    assert "templated from state" in anatomy


# ======================================================================
# .explain() shows five concerns
# ======================================================================


def test_explain_shows_five_concerns():
    """.explain() shows all five data flow concerns."""
    agent = (
        Agent("test", "gemini-2.0-flash")
        .reads("topic")
        .accepts(WriterInput)
        .returns(FindingsModel)
        .writes("out")
        .produces(FindingsModel)
    )
    text = agent.explain()
    assert "reads:" in text
    assert "accepts:" in text
    assert "returns:" in text
    assert "writes:" in text
    assert "contract:" in text or "produces" in text


def test_explain_shows_defaults():
    """.explain() shows defaults for bare agent."""
    agent = Agent("test", "gemini-2.0-flash")
    text = agent.explain()
    assert "reads:" in text
    assert "full conversation history" in text or "default" in text


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
    """Detects .returns() without .writes() — structured but not stored."""
    config = {"name": "test", "_output_schema": FindingsModel}
    issues = check_output_interop(config)
    assert len(issues) >= 1
    assert any("structured" in i["message"].lower() or "returns" in i["message"].lower() for i in issues)


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
    """Detects different schemas for .output_schema() and .returns()."""

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
# Interplay guide and LLM call anatomy
# ======================================================================


def test_interplay_guide_exists():
    """INTERPLAY_GUIDE is a non-empty string."""
    assert isinstance(INTERPLAY_GUIDE, str)
    assert len(INTERPLAY_GUIDE) > 100


def test_interplay_guide_covers_all_concerns():
    """INTERPLAY_GUIDE mentions all five concerns."""
    assert "Context" in INTERPLAY_GUIDE or "context" in INTERPLAY_GUIDE
    assert "Input" in INTERPLAY_GUIDE or "input" in INTERPLAY_GUIDE
    assert "Output" in INTERPLAY_GUIDE or "output" in INTERPLAY_GUIDE
    assert "Storage" in INTERPLAY_GUIDE or "storage" in INTERPLAY_GUIDE
    assert "Contract" in INTERPLAY_GUIDE or "contract" in INTERPLAY_GUIDE


def test_interplay_guide_covers_methods():
    """INTERPLAY_GUIDE mentions key methods."""
    assert ".reads()" in INTERPLAY_GUIDE
    assert ".accepts()" in INTERPLAY_GUIDE
    assert ".returns()" in INTERPLAY_GUIDE
    assert ".writes()" in INTERPLAY_GUIDE
    assert ".produces()" in INTERPLAY_GUIDE
    assert ".consumes()" in INTERPLAY_GUIDE


def test_interplay_guide_covers_defaults():
    """INTERPLAY_GUIDE documents default behavior."""
    assert "default" in INTERPLAY_GUIDE.lower()
    assert "full conversation" in INTERPLAY_GUIDE.lower() or "full history" in INTERPLAY_GUIDE.lower()


def test_llm_call_anatomy_exists():
    """LLM_CALL_ANATOMY is a non-empty string."""
    assert isinstance(LLM_CALL_ANATOMY, str)
    assert len(LLM_CALL_ANATOMY) > 200


def test_llm_call_anatomy_covers_order():
    """LLM_CALL_ANATOMY documents what gets sent in order."""
    assert "SYSTEM MESSAGE" in LLM_CALL_ANATOMY
    assert "CONVERSATION HISTORY" in LLM_CALL_ANATOMY
    assert "CONTEXT INJECTION" in LLM_CALL_ANATOMY
    assert "USER MESSAGE" in LLM_CALL_ANATOMY
    assert "TOOLS" in LLM_CALL_ANATOMY
    assert "OUTPUT CONSTRAINT" in LLM_CALL_ANATOMY


def test_llm_call_anatomy_covers_exclusions():
    """LLM_CALL_ANATOMY documents what does NOT get sent."""
    assert "WHAT DOES NOT GET SENT" in LLM_CALL_ANATOMY
    assert ".produces()" in LLM_CALL_ANATOMY
    assert ".consumes()" in LLM_CALL_ANATOMY
    assert ".accepts()" in LLM_CALL_ANATOMY


def test_llm_call_anatomy_covers_after():
    """LLM_CALL_ANATOMY documents what happens after LLM responds."""
    assert "AFTER THE LLM RESPONDS" in LLM_CALL_ANATOMY
    assert "output_key" in LLM_CALL_ANATOMY
    assert "output_schema" in LLM_CALL_ANATOMY
