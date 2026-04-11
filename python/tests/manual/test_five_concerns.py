"""Integration tests for the five-concern data flow model.

Verifies:
- Complete pipeline with all five concerns works end-to-end
- DataFlow comparison between old API (.output) and new API (.returns)
- LLM anatomy builds correctly for complex agents
- .explain() JSON format includes all five concerns
- Pipeline composition preserves data flow information
"""

from pydantic import BaseModel

from adk_fluent._context import C
from adk_fluent._interop import DataFlow, _build_llm_anatomy, _extract_data_flow
from adk_fluent.agent import Agent


class Intent(BaseModel):
    category: str
    confidence: float


class SearchQuery(BaseModel):
    query: str
    max_results: int = 10


class ResearchOutput(BaseModel):
    findings: str
    sources: list[str]


# ======================================================================
# Complete five-concern agent
# ======================================================================


def test_five_concern_agent():
    """Agent with all five concerns configured correctly."""
    agent = (
        Agent("classifier", "gemini-2.0-flash")
        .instruct("Classify the user query: {query}")
        .reads("query")
        .accepts(SearchQuery)
        .returns(Intent)
        .writes("intent")
        .produces(Intent)
        .consumes(SearchQuery)
    )

    df = agent.data_flow()
    assert isinstance(df, DataFlow)
    assert "query" in df.sees
    assert "SearchQuery" in df.accepts
    assert "Intent" in df.format
    assert df.stores == "state['intent']"
    assert "Intent" in df.contract_produces
    assert "SearchQuery" in df.contract_consumes


def test_five_concern_str_readable():
    """Five-concern DataFlow __str__ is human-readable."""
    agent = Agent("classifier", "gemini-2.0-flash").reads("query").accepts(SearchQuery).returns(Intent).writes("intent")
    text = str(agent.data_flow())

    # Each line should be clear
    assert "reads:" in text
    assert "accepts:" in text
    assert "returns:" in text
    assert "writes:" in text
    assert "contract:" in text


# ======================================================================
# Old API vs New API equivalence
# ======================================================================


def test_output_vs_returns_equivalence():
    """.output(Model) and .returns(Model) produce identical DataFlow."""
    a1 = Agent("test1", "gemini-2.0-flash").output(Intent)
    a2 = Agent("test2", "gemini-2.0-flash").returns(Intent)

    df1 = _extract_data_flow(a1)
    df2 = _extract_data_flow(a2)

    assert df1.format == df2.format
    assert "Intent" in df1.format
    assert "Intent" in df2.format


def test_matmul_vs_returns_equivalence():
    """@ operator and .returns() produce identical DataFlow."""
    a1 = Agent("test1", "gemini-2.0-flash") @ Intent
    a2 = Agent("test2", "gemini-2.0-flash").returns(Intent)

    df1 = _extract_data_flow(a1)
    df2 = _extract_data_flow(a2)

    assert df1.format == df2.format


def test_save_as_vs_writes_equivalence():
    """.writes(key) and .writes(key) produce identical DataFlow."""
    a1 = Agent("test1", "gemini-2.0-flash").writes("out")
    a2 = Agent("test2", "gemini-2.0-flash").writes("out")

    df1 = _extract_data_flow(a1)
    df2 = _extract_data_flow(a2)

    assert df1.stores == df2.stores == "state['out']"


# ======================================================================
# LLM anatomy for complex agents
# ======================================================================


def test_llm_anatomy_full_agent():
    """LLM anatomy shows all components for a fully configured agent."""
    agent = (
        Agent("researcher", "gemini-2.0-flash")
        .instruct("Research the topic: {topic}")
        .reads("topic")
        .returns(ResearchOutput)
        .writes("research")
    )
    anatomy = _build_llm_anatomy(agent)

    assert "LLM Call Anatomy: researcher" in anatomy
    assert "Research the topic: {topic}" in anatomy
    assert "{topic}" in anatomy
    assert "SUPPRESSED" in anatomy  # history suppressed by .reads()
    assert "DISABLED" in anatomy  # tools disabled by .returns()
    assert "ResearchOutput" in anatomy
    assert 'state["research"]' in anatomy


def test_llm_anatomy_bare_agent():
    """LLM anatomy shows defaults for bare agent."""
    agent = Agent("basic", "gemini-2.0-flash")
    anatomy = _build_llm_anatomy(agent)

    assert "FULL conversation history" in anatomy
    assert "no context spec" in anatomy
    assert "none — free-form text" in anatomy
    assert "conversation history only" in anatomy


def test_llm_anatomy_with_instruction_template():
    """LLM anatomy highlights template variables."""
    agent = Agent("test", "gemini-2.0-flash").instruct("Hello {name}, process {data}")
    anatomy = _build_llm_anatomy(agent)

    assert "{name, data}" in anatomy
    assert "templated from state" in anatomy


# ======================================================================
# .explain() JSON format includes five concerns
# ======================================================================


def test_explain_json_includes_data_flow():
    """.explain(format='json') includes five-concern data_flow."""
    agent = (
        Agent("test", "gemini-2.0-flash")
        .reads("topic")
        .accepts(SearchQuery)
        .returns(Intent)
        .writes("out")
        .produces(Intent)
    )
    result = agent.explain(format="json")

    assert "data_flow" in result
    df = result["data_flow"]
    assert "reads" in df
    assert "accepts" in df
    assert "returns" in df
    assert "writes" in df
    assert "produces" in df


def test_explain_json_data_flow_schemas():
    """.explain(format='json') data_flow includes schema details."""
    agent = Agent("test", "gemini-2.0-flash").accepts(SearchQuery).returns(Intent)
    result = agent.explain(format="json")

    df = result.get("data_flow", {})
    assert df.get("accepts", {}).get("schema") == "SearchQuery"
    assert df.get("returns", {}).get("schema") == "Intent"
    assert "category" in df.get("returns", {}).get("fields", [])


# ======================================================================
# Pipeline data flow composition
# ======================================================================


def test_pipeline_data_flow():
    """Pipeline agents preserve data flow when composed with >>."""
    classifier = Agent("classifier", "gemini-2.0-flash").reads("query").returns(Intent).writes("intent")
    handler = Agent("handler", "gemini-2.0-flash").reads("intent").writes("response")
    _pipeline = classifier >> handler  # noqa: F841 — verifies composition works

    # Each agent in the pipeline retains its own data flow
    df1 = classifier.data_flow()
    df2 = handler.data_flow()

    assert "query" in df1.sees
    assert "Intent" in df1.format
    assert df1.stores == "state['intent']"

    assert "intent" in df2.sees
    assert df2.stores == "state['response']"


def test_pipeline_llm_anatomy_per_agent():
    """Each agent in a pipeline has its own LLM anatomy."""
    a1 = Agent("writer", "gemini-2.0-flash").instruct("Write").writes("draft")
    a2 = Agent("editor", "gemini-2.0-flash").reads("draft").writes("final")

    anatomy1 = a1.llm_anatomy()
    anatomy2 = a2.llm_anatomy()

    assert "writer" in anatomy1
    assert "FULL conversation history" in anatomy1

    assert "editor" in anatomy2
    assert "SUPPRESSED" in anatomy2  # .reads() suppresses history


# ======================================================================
# Data flow with context composition
# ======================================================================


def test_reads_plus_context_composition():
    """.context() + .reads() compose additively."""
    agent = Agent("test", "gemini-2.0-flash").context(C.window(n=3)).reads("topic")
    df = agent.data_flow()
    # Should show both window and state keys
    assert "topic" in df.sees


def test_data_flow_defaults_explicit():
    """DataFlow defaults are informative, not empty."""
    agent = Agent("bare", "gemini-2.0-flash")
    df = agent.data_flow()

    text = str(df)
    # Every line should have content, not just empty
    assert "full conversation history" in text
    assert "not set" in text
    assert "plain text" in text
