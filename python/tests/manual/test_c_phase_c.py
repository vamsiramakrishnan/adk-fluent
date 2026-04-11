"""Tests for Phase C — LLM-powered C Atoms (summarize, relevant, extract, distill, validate).

All LLM calls are mocked via _call_llm patching. No real API calls are made.
"""

import asyncio
import json
import time
import unittest.mock

import pytest

from adk_fluent._context import (
    C,
    CComposite,
    CDistill,
    CExtract,
    CPipe,
    CRelevant,
    CSummarize,
    CTransform,
    CValidate,
    _compile_context_spec,
    _fingerprint_events,
)

# ======================================================================
# Mock helpers (reused from Phase B pattern)
# ======================================================================


class _MockPart:
    def __init__(self, text=None, function_call=None, function_response=None):
        self.text = text
        self.function_call = function_call
        self.function_response = function_response


class _MockContent:
    def __init__(self, parts):
        self.parts = parts


class _MockEvent:
    def __init__(self, author, text, tags=None, timestamp=None):
        self.author = author
        self.content = _MockContent([_MockPart(text=text)])
        self.tags = tags or []
        self.timestamp = timestamp


class _MockToolCallEvent:
    def __init__(self, author="model"):
        self.author = author
        fc = type("FC", (), {"name": "search"})()
        self.content = _MockContent([_MockPart(function_call=fc)])
        self.tags = []
        self.timestamp = None


class _MockToolResponseEvent:
    def __init__(self, author="tool"):
        self.author = author
        fr = type("FR", (), {"name": "search"})()
        self.content = _MockContent([_MockPart(function_response=fr)])
        self.tags = []
        self.timestamp = None


class _MockSession:
    def __init__(self, events):
        self.events = events


class _MockState(dict):
    pass


class _MockCtx:
    def __init__(self, events=None, state=None):
        self.session = _MockSession(events or [])
        self.state = _MockState(state or {})


def _run(coro):
    """Run async provider in sync test."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _mock_llm(response_text):
    """Create a mock _call_llm that returns fixed text."""

    async def _mock(model, prompt, response_schema=None):
        return response_text

    return _mock


def _mock_llm_fn(fn):
    """Create a mock _call_llm that calls fn(prompt) to produce response."""

    async def _mock(model, prompt, response_schema=None):
        return fn(prompt)

    return _mock


# ======================================================================
# _fingerprint_events
# ======================================================================


class TestFingerprint:
    def test_returns_string(self):
        events = [_MockEvent("user", "hello")]
        fp = _fingerprint_events(events)
        assert isinstance(fp, str)
        assert len(fp) == 12

    def test_stable(self):
        events = [_MockEvent("user", "hello")]
        assert _fingerprint_events(events) == _fingerprint_events(events)

    def test_changes_with_content(self):
        e1 = [_MockEvent("user", "hello")]
        e2 = [_MockEvent("user", "goodbye")]
        assert _fingerprint_events(e1) != _fingerprint_events(e2)

    def test_changes_with_author(self):
        e1 = [_MockEvent("user", "hello")]
        e2 = [_MockEvent("model", "hello")]
        assert _fingerprint_events(e1) != _fingerprint_events(e2)

    def test_empty_events(self):
        fp = _fingerprint_events([])
        assert isinstance(fp, str)
        assert len(fp) == 12


# ======================================================================
# C.summarize()
# ======================================================================


class TestSummarize:
    def test_creates_transform(self):
        t = C.summarize()
        assert isinstance(t, CSummarize)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.summarize()
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.summarize()
        assert callable(t.instruction_provider)

    def test_frozen(self):
        t = C.summarize()
        with pytest.raises(AttributeError):
            t.scope = "before_window"

    def test_defaults(self):
        t = C.summarize()
        assert t.scope == "all"
        assert t.model == "gemini-2.5-flash"
        assert t.prompt is None
        assert t.schema is None

    def test_custom_params(self):
        t = C.summarize(scope="tool_results", model="custom-model", prompt="Be concise.")
        assert t.scope == "tool_results"
        assert t.model == "custom-model"
        assert t.prompt == "Be concise."

    def test_summarize_calls_llm(self):
        events = [_MockEvent("user", "hello"), _MockEvent("model", "hi there")]
        ctx = _MockCtx(events=events)
        t = C.summarize()
        with unittest.mock.patch(
            "adk_fluent._context_providers._call_llm", new=_mock_llm("Summary: greeting exchange")
        ):
            result = _run(t.instruction_provider(ctx))
        assert "Summary: greeting exchange" in result

    def test_summarize_caches_result(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events)
        t = C.summarize()

        call_count = 0

        async def _counting_mock(model, prompt, response_schema=None):
            nonlocal call_count
            call_count += 1
            return "cached summary"

        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_counting_mock):
            result1 = _run(t.instruction_provider(ctx))
            result2 = _run(t.instruction_provider(ctx))  # Should use cache

        assert call_count == 1
        assert "cached summary" in result1
        assert "cached summary" in result2

    def test_summarize_scope_tool_results(self):
        events = [
            _MockEvent("user", "find something"),
            _MockToolResponseEvent(),
            _MockEvent("model", "here you go"),
        ]
        ctx = _MockCtx(events=events)
        t = C.summarize(scope="tool_results")
        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_mock_llm("tool summary")):
            result = _run(t.instruction_provider(ctx))
        # The provider should have selected only tool response events
        assert "tool summary" in result

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.summarize()
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.relevant()
# ======================================================================


class TestRelevant:
    def test_creates_transform(self):
        t = C.relevant(query="test")
        assert isinstance(t, CRelevant)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.relevant(query="test")
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.relevant(query="test")
        assert callable(t.instruction_provider)

    def test_frozen(self):
        t = C.relevant(query="test")
        with pytest.raises(AttributeError):
            t.query = "other"

    def test_defaults(self):
        t = C.relevant()
        assert t.query_key is None
        assert t.query is None
        assert t.top_k == 5

    def test_relevant_with_literal_query(self):
        events = [
            _MockEvent("user", "What is machine learning?"),
            _MockEvent("model", "ML is a branch of AI"),
            _MockEvent("user", "What about cooking?"),
            _MockEvent("model", "Cooking is a culinary art"),
        ]
        ctx = _MockCtx(events=events)
        t = C.relevant(query="artificial intelligence", top_k=2)

        scores_json = json.dumps(
            [
                {"index": 0, "score": 9},
                {"index": 1, "score": 8},
                {"index": 2, "score": 1},
                {"index": 3, "score": 0},
            ]
        )
        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_mock_llm(scores_json)):
            result = _run(t.instruction_provider(ctx))
        assert "machine learning" in result
        assert "ML is a branch" in result
        # Cooking should be excluded (low score, top_k=2)
        assert "cooking" not in result.lower()

    def test_relevant_with_query_key(self):
        events = [_MockEvent("user", "hello"), _MockEvent("model", "hi")]
        ctx = _MockCtx(events=events, state={"intent": "greetings"})
        t = C.relevant(query_key="intent", top_k=1)

        scores_json = json.dumps([{"index": 0, "score": 8}, {"index": 1, "score": 7}])
        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_mock_llm(scores_json)):
            result = _run(t.instruction_provider(ctx))
        assert "hello" in result

    def test_relevant_caches(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events)
        t = C.relevant(query="test")

        call_count = 0

        async def _counting_mock(model, prompt, response_schema=None):
            nonlocal call_count
            call_count += 1
            return json.dumps([{"index": 0, "score": 10}])

        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_counting_mock):
            _run(t.instruction_provider(ctx))
            _run(t.instruction_provider(ctx))

        assert call_count == 1

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.relevant(query="test")
        result = _run(t.instruction_provider(ctx))
        assert result == ""

    def test_no_query_returns_all(self):
        events = [_MockEvent("user", "hello"), _MockEvent("model", "hi")]
        ctx = _MockCtx(events=events)
        t = C.relevant()  # No query at all
        result = _run(t.instruction_provider(ctx))
        assert "hello" in result
        assert "hi" in result


# ======================================================================
# C.extract()
# ======================================================================


class TestExtract:
    def test_creates_transform(self):
        t = C.extract(schema={"name": "str"})
        assert isinstance(t, CExtract)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.extract()
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.extract()
        assert callable(t.instruction_provider)

    def test_frozen(self):
        t = C.extract()
        with pytest.raises(AttributeError):
            t.key = "other"

    def test_defaults(self):
        t = C.extract()
        assert t.key == "extracted"

    def test_extract_writes_to_state(self):
        events = [_MockEvent("user", "Budget is $5000, timeline is March")]
        ctx = _MockCtx(events=events)
        t = C.extract(schema={"budget": "float", "timeline": "str"}, key="requirements")

        mock_json = '{"budget": 5000, "timeline": "March"}'
        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_mock_llm(mock_json)):
            result = _run(t.instruction_provider(ctx))

        assert "[requirements]:" in result
        assert "5000" in result
        # Verify state was written
        assert ctx.state.get("requirements") is not None

    def test_extract_caches(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events)
        t = C.extract(key="data")

        call_count = 0

        async def _counting_mock(model, prompt, response_schema=None):
            nonlocal call_count
            call_count += 1
            return '{"result": "ok"}'

        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_counting_mock):
            _run(t.instruction_provider(ctx))
            _run(t.instruction_provider(ctx))

        assert call_count == 1

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.extract()
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.distill()
# ======================================================================


class TestDistill:
    def test_creates_transform(self):
        t = C.distill()
        assert isinstance(t, CDistill)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.distill()
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.distill()
        assert callable(t.instruction_provider)

    def test_frozen(self):
        t = C.distill()
        with pytest.raises(AttributeError):
            t.key = "other"

    def test_defaults(self):
        t = C.distill()
        assert t.key == "facts"

    def test_distill_extracts_facts(self):
        events = [
            _MockEvent("user", "Budget is $5000"),
            _MockEvent("user", "Deadline is March 15"),
        ]
        ctx = _MockCtx(events=events)
        t = C.distill(key="findings")

        facts_json = json.dumps(["Budget is $5000", "Deadline is March 15"])
        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_mock_llm(facts_json)):
            result = _run(t.instruction_provider(ctx))

        assert "Budget is $5000" in result
        assert "Deadline is March 15" in result
        # Check state
        assert ctx.state.get("_facts_findings") is not None

    def test_distill_caches(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events)
        t = C.distill()

        call_count = 0

        async def _counting_mock(model, prompt, response_schema=None):
            nonlocal call_count
            call_count += 1
            return '["fact1"]'

        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_counting_mock):
            _run(t.instruction_provider(ctx))
            _run(t.instruction_provider(ctx))

        assert call_count == 1

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.distill()
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.validate()
# ======================================================================


class TestValidate:
    def test_creates_transform(self):
        t = C.validate("completeness")
        assert isinstance(t, CValidate)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.validate()
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.validate()
        assert callable(t.instruction_provider)

    def test_frozen(self):
        t = C.validate()
        with pytest.raises(AttributeError):
            t.checks = ("freshness",)

    def test_defaults(self):
        t = C.validate()
        assert t.checks == ("completeness",)

    def test_completeness_check_no_warning(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events, state={"intent": "greeting"})
        t = C.validate("completeness")
        result = _run(t.instruction_provider(ctx))
        assert "<warning>" not in result

    def test_completeness_check_empty_key_warning(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events, state={"intent": ""})
        t = C.validate("completeness")
        result = _run(t.instruction_provider(ctx))
        assert "<warning>" in result
        assert "intent" in result

    def test_freshness_check(self):
        now = time.time()
        events = [
            _MockEvent("user", "old message", timestamp=now - 7200),
            _MockEvent("user", "new message", timestamp=now - 60),
        ]
        ctx = _MockCtx(events=events)
        t = C.validate("freshness")
        result = _run(t.instruction_provider(ctx))
        assert "<warning>" in result
        assert "older than 1 hour" in result

    def test_token_efficiency_check(self):
        events = [
            _MockEvent("user", "same message"),
            _MockEvent("user", "same message"),
            _MockEvent("user", "same message"),
            _MockEvent("user", "same message"),
        ]
        ctx = _MockCtx(events=events)
        t = C.validate("token_efficiency")
        result = _run(t.instruction_provider(ctx))
        assert "<warning>" in result
        assert "duplicate" in result

    def test_contradictions_check(self):
        events = [
            _MockEvent("user", "The budget is $5000"),
            _MockEvent("user", "The budget is $3000"),
        ]
        ctx = _MockCtx(events=events)
        t = C.validate("contradictions")

        with unittest.mock.patch(
            "adk_fluent._context_providers._call_llm",
            new=_mock_llm("Budget contradiction: $5000 vs $3000"),
        ):
            result = _run(t.instruction_provider(ctx))

        assert "<warning>" in result
        assert "contradiction" in result.lower()

    def test_contradictions_none_result(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events)
        t = C.validate("contradictions")

        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_mock_llm("none")):
            result = _run(t.instruction_provider(ctx))

        assert "<warning>" not in result

    def test_multiple_checks(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events, state={"intent": ""})
        t = C.validate("completeness", "freshness")
        result = _run(t.instruction_provider(ctx))
        assert "<warning>" in result

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.validate()
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# Extended CDedup (strategy="semantic")
# ======================================================================


class TestDedupSemantic:
    def test_has_model_field(self):
        t = C.dedup(strategy="semantic")
        assert t.model == "gemini-2.5-flash"

    def test_semantic_dedup(self):
        events = [
            _MockEvent("user", "The budget is $5000"),
            _MockEvent("user", "Our budget is five thousand dollars"),
            _MockEvent("user", "Deadline is March"),
        ]
        ctx = _MockCtx(events=events)
        t = C.dedup(strategy="semantic")

        # LLM says keep indices 1 and 2 (drop 0 as semantic dup of 1)
        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_mock_llm("[1, 2]")):
            result = _run(t.instruction_provider(ctx))

        assert "five thousand" in result
        assert "Deadline" in result

    def test_semantic_dedup_caches(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events)
        t = C.dedup(strategy="semantic")

        call_count = 0

        async def _counting_mock(model, prompt, response_schema=None):
            nonlocal call_count
            call_count += 1
            return "[0]"

        with unittest.mock.patch("adk_fluent._context_providers._call_llm", new=_counting_mock):
            _run(t.instruction_provider(ctx))
            _run(t.instruction_provider(ctx))

        assert call_count == 1

    def test_exact_dedup_unchanged(self):
        """Existing exact strategy still works without model."""
        events = [
            _MockEvent("user", "hello"),
            _MockEvent("user", "hello"),
            _MockEvent("model", "hi"),
        ]
        ctx = _MockCtx(events=events)
        t = C.dedup(strategy="exact")
        result = _run(t.instruction_provider(ctx))
        assert result.count("[user]: hello") == 1


# ======================================================================
# Extended CFit (strategy="cascade")
# ======================================================================


class TestFitCascade:
    def test_has_model_field(self):
        t = C.fit(strategy="cascade")
        assert t.model == "gemini-2.5-flash"

    def test_cascade_under_budget(self):
        """If already under budget, no LLM call needed."""
        events = [_MockEvent("user", "short")]
        ctx = _MockCtx(events=events)
        t = C.fit(max_tokens=4000, strategy="cascade")
        result = _run(t.instruction_provider(ctx))
        assert "short" in result

    def test_cascade_compacts_first(self):
        """Cascade compacts tool calls as first step."""
        events = [
            _MockEvent("user", "search"),
            _MockToolCallEvent(),
            _MockToolResponseEvent(),
            _MockEvent("model", "results"),
        ]
        ctx = _MockCtx(events=events)
        t = C.fit(max_tokens=4000, strategy="cascade")
        result = _run(t.instruction_provider(ctx))
        assert "tool calls" in result
        assert "results" in result

    def test_compact_then_summarize_under_budget(self):
        events = [_MockEvent("user", "short")]
        ctx = _MockCtx(events=events)
        t = C.fit(max_tokens=4000, strategy="compact_then_summarize")
        result = _run(t.instruction_provider(ctx))
        assert "short" in result

    def test_strict_unchanged(self):
        """Existing strict strategy still works."""
        events = [_MockEvent("user", f"msg_{i}" + "x" * 200) for i in range(20)]
        ctx = _MockCtx(events=events)
        t = C.fit(max_tokens=200, strategy="strict")
        result = _run(t.instruction_provider(ctx))
        assert "msg_19" in result


# ======================================================================
# Composition with Phase C
# ======================================================================


class TestPhaseCComposition:
    def test_summarize_plus_relevant(self):
        result = C.summarize() + C.relevant(query="test")
        assert isinstance(result, CComposite)
        assert len(result.blocks) == 2

    def test_window_pipe_summarize(self):
        result = C.window(n=3) | C.summarize()
        assert isinstance(result, CPipe)

    def test_select_pipe_relevant(self):
        result = C.select(author="user") | C.relevant(query="test")
        assert isinstance(result, CPipe)

    def test_from_state_plus_extract(self):
        result = C.from_state("topic") + C.extract(schema={"topic": "str"})
        assert isinstance(result, CComposite)

    def test_all_phase_c_are_ctransform(self):
        transforms = [
            C.summarize(),
            C.relevant(query="test"),
            C.extract(),
            C.distill(),
            C.validate(),
        ]
        for t in transforms:
            assert isinstance(t, CTransform), f"{type(t)} is not a CTransform"

    def test_all_phase_c_are_frozen(self):
        transforms = [
            C.summarize(),
            C.relevant(query="test"),
            C.extract(),
            C.distill(),
            C.validate(),
        ]
        for t in transforms:
            with pytest.raises(AttributeError):
                t._kind = "changed"

    def test_compile_with_summarize(self):
        compiled = _compile_context_spec("Analyze.", C.summarize())
        assert compiled["include_contents"] == "none"
        assert callable(compiled["instruction"])

    def test_compile_with_relevant(self):
        compiled = _compile_context_spec("Review.", C.relevant(query="test"))
        assert compiled["include_contents"] == "none"
        assert callable(compiled["instruction"])

    def test_compile_composite_phase_c(self):
        composite = C.summarize() + C.extract(key="data")
        compiled = _compile_context_spec("Process.", composite)
        assert compiled["include_contents"] == "none"
        assert callable(compiled["instruction"])
