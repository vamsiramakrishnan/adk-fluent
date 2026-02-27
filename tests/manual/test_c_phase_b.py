"""Tests for Phase B C Atoms — SELECT, COMPRESS, BUDGET, PROTECT primitives."""

import asyncio
import time

import pytest

from adk_fluent._context import (
    C,
    CCompact,
    CComposite,
    CDedup,
    CFit,
    CFresh,
    CPipe,
    CProject,
    CRecent,
    CRedact,
    CSelect,
    CTransform,
    CTruncate,
    _compile_context_spec,
    _SyntheticEvent,
)

# ======================================================================
# Mock helpers
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
        # Already in an event loop (e.g. pytest-asyncio) — use new loop
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ======================================================================
# C.select()
# ======================================================================


class TestSelect:
    def test_creates_transform(self):
        t = C.select(author="user")
        assert isinstance(t, CSelect)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.select(author="user")
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.select(author="user")
        assert callable(t.instruction_provider)

    def test_frozen(self):
        t = C.select(author="user")
        with pytest.raises(AttributeError):
            t.author = "model"

    def test_filter_by_author(self):
        events = [
            _MockEvent("user", "hello"),
            _MockEvent("model", "hi there"),
            _MockEvent("user", "thanks"),
        ]
        ctx = _MockCtx(events=events)
        t = C.select(author="user")
        result = _run(t.instruction_provider(ctx))
        assert "[user]: hello" in result
        assert "[user]: thanks" in result
        assert "[model]" not in result

    def test_filter_by_multiple_authors(self):
        events = [
            _MockEvent("user", "hello"),
            _MockEvent("writer", "draft"),
            _MockEvent("reviewer", "looks good"),
        ]
        ctx = _MockCtx(events=events)
        t = C.select(author=("user", "writer"))
        result = _run(t.instruction_provider(ctx))
        assert "[user]" in result
        assert "[writer]" in result
        assert "[reviewer]" not in result

    def test_filter_by_type_message(self):
        events = [
            _MockEvent("user", "hello"),
            _MockToolCallEvent(),
        ]
        ctx = _MockCtx(events=events)
        t = C.select(type="message")
        result = _run(t.instruction_provider(ctx))
        assert "[user]: hello" in result
        # tool_call has no text so should not appear

    def test_filter_by_tag(self):
        events = [
            _MockEvent("user", "hello", tags=["important"]),
            _MockEvent("user", "bye", tags=["mundane"]),
        ]
        ctx = _MockCtx(events=events)
        t = C.select(tag="important")
        result = _run(t.instruction_provider(ctx))
        assert "hello" in result
        assert "bye" not in result

    def test_no_filters_returns_all(self):
        events = [
            _MockEvent("user", "hello"),
            _MockEvent("model", "hi"),
        ]
        ctx = _MockCtx(events=events)
        t = C.select()
        result = _run(t.instruction_provider(ctx))
        assert "[user]: hello" in result
        assert "[model]: hi" in result

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.select(author="user")
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.recent()
# ======================================================================


class TestRecent:
    def test_creates_transform(self):
        t = C.recent()
        assert isinstance(t, CRecent)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.recent()
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.recent()
        assert callable(t.instruction_provider)

    def test_defaults(self):
        t = C.recent()
        assert t.decay == "exponential"
        assert t.half_life == 10
        assert t.min_weight == 0.1

    def test_keeps_recent_drops_old(self):
        # With half_life=2 and min_weight=0.5, old events should drop
        events = [_MockEvent("user", f"msg_{i}") for i in range(20)]
        ctx = _MockCtx(events=events)
        t = C.recent(half_life=2, min_weight=0.5)
        result = _run(t.instruction_provider(ctx))
        # Most recent should be present
        assert "msg_19" in result
        # Very old should be dropped
        assert "msg_0" not in result

    def test_linear_decay(self):
        events = [_MockEvent("user", f"msg_{i}") for i in range(10)]
        ctx = _MockCtx(events=events)
        t = C.recent(decay="linear", half_life=3, min_weight=0.1)
        result = _run(t.instruction_provider(ctx))
        assert "msg_9" in result  # most recent

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.recent()
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.compact()
# ======================================================================


class TestCompact:
    def test_creates_transform(self):
        t = C.compact()
        assert isinstance(t, CCompact)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.compact()
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.compact()
        assert callable(t.instruction_provider)

    def test_default_strategy(self):
        t = C.compact()
        assert t.strategy == "tool_calls"

    def test_tool_calls_compaction(self):
        events = [
            _MockEvent("user", "search for cats"),
            _MockToolCallEvent(),
            _MockToolResponseEvent(),
            _MockToolCallEvent(),
            _MockToolResponseEvent(),
            _MockEvent("model", "here are the results"),
        ]
        ctx = _MockCtx(events=events)
        t = C.compact(strategy="tool_calls")
        result = _run(t.instruction_provider(ctx))
        assert "tool calls" in result
        assert "here are the results" in result

    def test_all_strategy_merges_same_author(self):
        events = [
            _MockEvent("user", "hello"),
            _MockEvent("user", "how are you"),
            _MockEvent("model", "I'm fine"),
            _MockEvent("model", "thanks for asking"),
        ]
        ctx = _MockCtx(events=events)
        t = C.compact(strategy="all")
        result = _run(t.instruction_provider(ctx))
        # Merged user messages
        assert "hello" in result
        assert "how are you" in result
        # Merged model messages
        assert "I'm fine" in result
        assert "thanks for asking" in result

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.compact()
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.dedup()
# ======================================================================


class TestDedup:
    def test_creates_transform(self):
        t = C.dedup()
        assert isinstance(t, CDedup)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.dedup()
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.dedup()
        assert callable(t.instruction_provider)

    def test_default_strategy(self):
        t = C.dedup()
        assert t.strategy == "exact"

    def test_exact_removes_duplicates(self):
        events = [
            _MockEvent("user", "hello"),
            _MockEvent("user", "hello"),
            _MockEvent("model", "hi"),
        ]
        ctx = _MockCtx(events=events)
        t = C.dedup(strategy="exact")
        result = _run(t.instruction_provider(ctx))
        # Only one "hello"
        assert result.count("[user]: hello") == 1
        assert "[model]: hi" in result

    def test_structural_normalizes_whitespace(self):
        events = [
            _MockEvent("user", "hello  world"),
            _MockEvent("user", "hello world"),
            _MockEvent("model", "hi"),
        ]
        ctx = _MockCtx(events=events)
        t = C.dedup(strategy="structural")
        result = _run(t.instruction_provider(ctx))
        # Both normalize to "hello world" so second is dropped
        assert result.count("hello") == 1

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.dedup()
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.truncate()
# ======================================================================


class TestTruncate:
    def test_creates_transform(self):
        t = C.truncate(max_turns=3)
        assert isinstance(t, CTruncate)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.truncate(max_turns=3)
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.truncate(max_turns=3)
        assert callable(t.instruction_provider)

    def test_tail_strategy_keeps_last_turns(self):
        events = [
            _MockEvent("user", "turn1"),
            _MockEvent("model", "resp1"),
            _MockEvent("user", "turn2"),
            _MockEvent("model", "resp2"),
            _MockEvent("user", "turn3"),
            _MockEvent("model", "resp3"),
        ]
        ctx = _MockCtx(events=events)
        t = C.truncate(max_turns=2, strategy="tail")
        result = _run(t.instruction_provider(ctx))
        assert "turn3" in result
        assert "turn2" in result
        assert "turn1" not in result

    def test_head_strategy_keeps_first_turns(self):
        events = [
            _MockEvent("user", "turn1"),
            _MockEvent("model", "resp1"),
            _MockEvent("user", "turn2"),
            _MockEvent("model", "resp2"),
            _MockEvent("user", "turn3"),
            _MockEvent("model", "resp3"),
        ]
        ctx = _MockCtx(events=events)
        t = C.truncate(max_turns=1, strategy="head")
        result = _run(t.instruction_provider(ctx))
        assert "turn1" in result
        assert "turn2" not in result
        assert "turn3" not in result

    def test_max_tokens_truncation(self):
        # Create events with known character count
        events = [_MockEvent("user", "x" * 100) for _ in range(10)]
        ctx = _MockCtx(events=events)
        # 100 chars = ~25 tokens per event, 10 events = ~250 tokens total
        # But formatted includes "[user]: " prefix
        t = C.truncate(max_tokens=50)
        result = _run(t.instruction_provider(ctx))
        # Result should be truncated
        assert len(result) <= 200 + 50  # rough upper bound

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.truncate(max_turns=3)
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.project()
# ======================================================================


class TestProject:
    def test_creates_transform(self):
        t = C.project("text")
        assert isinstance(t, CProject)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.project("text")
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.project("text")
        assert callable(t.instruction_provider)

    def test_default_fields(self):
        t = C.project()
        assert t.fields == ("text",)

    def test_text_projection(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events)
        t = C.project("text")
        result = _run(t.instruction_provider(ctx))
        assert "hello" in result

    def test_author_projection(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events)
        t = C.project("author")
        result = _run(t.instruction_provider(ctx))
        assert "author=user" in result

    def test_multiple_fields(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events)
        t = C.project("text", "author")
        result = _run(t.instruction_provider(ctx))
        assert "hello" in result
        assert "author=user" in result

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.project("text")
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.budget() (Phase B updates)
# ======================================================================


class TestBudgetProvider:
    def test_has_provider(self):
        t = C.budget()
        assert callable(t.instruction_provider)

    def test_under_budget_returns_all(self):
        events = [_MockEvent("user", "short message")]
        ctx = _MockCtx(events=events)
        t = C.budget(max_tokens=8000)
        result = _run(t.instruction_provider(ctx))
        assert "short message" in result

    def test_over_budget_truncates(self):
        # Create enough text to exceed budget
        events = [_MockEvent("user", "x" * 1000) for _ in range(10)]
        ctx = _MockCtx(events=events)
        t = C.budget(max_tokens=100)
        result = _run(t.instruction_provider(ctx))
        # Should be truncated to roughly 400 chars (100 tokens * 4)
        assert len(result) <= 500

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.budget()
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.fit()
# ======================================================================


class TestFit:
    def test_creates_transform(self):
        t = C.fit()
        assert isinstance(t, CFit)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.fit()
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.fit()
        assert callable(t.instruction_provider)

    def test_defaults(self):
        t = C.fit()
        assert t.max_tokens == 4000
        assert t.strategy == "strict"

    def test_strict_keeps_recent(self):
        events = [_MockEvent("user", f"message_{i}" + "x" * 200) for i in range(20)]
        ctx = _MockCtx(events=events)
        t = C.fit(max_tokens=200)
        result = _run(t.instruction_provider(ctx))
        # Should keep most recent events that fit
        assert "message_19" in result

    def test_under_limit_returns_all(self):
        events = [_MockEvent("user", "short")]
        ctx = _MockCtx(events=events)
        t = C.fit(max_tokens=4000)
        result = _run(t.instruction_provider(ctx))
        assert "short" in result

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.fit()
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.fresh()
# ======================================================================


class TestFresh:
    def test_creates_transform(self):
        t = C.fresh()
        assert isinstance(t, CFresh)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.fresh()
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.fresh()
        assert callable(t.instruction_provider)

    def test_defaults(self):
        t = C.fresh()
        assert t.max_age == 3600.0
        assert t.stale_action == "drop"

    def test_drops_stale_events(self):
        now = time.time()
        events = [
            _MockEvent("user", "old", timestamp=now - 7200),  # 2 hours ago
            _MockEvent("user", "recent", timestamp=now - 60),  # 1 minute ago
        ]
        ctx = _MockCtx(events=events)
        t = C.fresh(max_age=3600)
        result = _run(t.instruction_provider(ctx))
        assert "recent" in result
        assert "old" not in result

    def test_keeps_events_without_timestamp(self):
        events = [_MockEvent("user", "no_timestamp")]
        ctx = _MockCtx(events=events)
        t = C.fresh(max_age=60)
        result = _run(t.instruction_provider(ctx))
        assert "no_timestamp" in result

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.fresh()
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# C.redact()
# ======================================================================


class TestRedact:
    def test_creates_transform(self):
        t = C.redact(r"\d{3}-\d{2}-\d{4}")
        assert isinstance(t, CRedact)
        assert isinstance(t, CTransform)

    def test_include_contents_is_none(self):
        t = C.redact(r"\d+")
        assert t.include_contents == "none"

    def test_has_provider(self):
        t = C.redact(r"\d+")
        assert callable(t.instruction_provider)

    def test_default_replacement(self):
        t = C.redact(r"\d+")
        assert t.replacement == "[REDACTED]"

    def test_redacts_ssn_pattern(self):
        events = [_MockEvent("user", "My SSN is 123-45-6789")]
        ctx = _MockCtx(events=events)
        t = C.redact(r"\d{3}-\d{2}-\d{4}")
        result = _run(t.instruction_provider(ctx))
        assert "123-45-6789" not in result
        assert "[REDACTED]" in result

    def test_custom_replacement(self):
        events = [_MockEvent("user", "email: test@example.com")]
        ctx = _MockCtx(events=events)
        t = C.redact(r"\S+@\S+", replacement="***")
        result = _run(t.instruction_provider(ctx))
        assert "test@example.com" not in result
        assert "***" in result

    def test_multiple_patterns(self):
        events = [_MockEvent("user", "SSN: 123-45-6789, phone: 555-1234")]
        ctx = _MockCtx(events=events)
        t = C.redact(r"\d{3}-\d{2}-\d{4}", r"\d{3}-\d{4}")
        result = _run(t.instruction_provider(ctx))
        assert "123-45-6789" not in result
        assert "555-1234" not in result

    def test_no_patterns_returns_unchanged(self):
        events = [_MockEvent("user", "hello world")]
        ctx = _MockCtx(events=events)
        t = C.redact()
        result = _run(t.instruction_provider(ctx))
        assert "hello world" in result

    def test_empty_events(self):
        ctx = _MockCtx(events=[])
        t = C.redact(r"\d+")
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# _SyntheticEvent
# ======================================================================


class TestSyntheticEvent:
    def test_has_author(self):
        e = _SyntheticEvent("user", "hello")
        assert e.author == "user"

    def test_has_content_parts(self):
        e = _SyntheticEvent("user", "hello")
        assert len(e.content.parts) == 1
        assert e.content.parts[0].text == "hello"

    def test_works_with_format_events(self):
        from adk_fluent._context import _format_events_as_context

        events = [_SyntheticEvent("user", "hello"), _SyntheticEvent("model", "hi")]
        result = _format_events_as_context(events)
        assert "[user]: hello" in result
        assert "[model]: hi" in result


# ======================================================================
# Phase B composition tests
# ======================================================================


class TestPhaseBComposition:
    def test_select_plus_recent(self):
        result = C.select(author="user") + C.recent(half_life=5)
        assert isinstance(result, CComposite)
        assert len(result.blocks) == 2

    def test_window_pipe_redact(self):
        result = C.window(n=3) | C.redact(r"\d+")
        assert isinstance(result, CPipe)

    def test_composite_provider_runs_all_blocks(self):
        events = [_MockEvent("user", "hello")]
        ctx = _MockCtx(events=events, state={"topic": "AI"})
        composite = C.from_state("topic") + C.user_only()
        result = _run(composite.instruction_provider(ctx))
        assert "[topic]: AI" in result
        assert "[user]: hello" in result

    def test_pipe_provider_chains(self):
        events = [_MockEvent("user", "My SSN is 123-45-6789")]
        ctx = _MockCtx(events=events)
        piped = C.user_only() | C.redact(r"\d{3}-\d{2}-\d{4}")
        result = _run(piped.instruction_provider(ctx))
        # SSN should be redacted from user_only output
        assert "123-45-6789" not in result
        assert "[REDACTED]" in result

    def test_pipe_with_empty_source(self):
        ctx = _MockCtx(events=[])
        piped = C.user_only() | C.redact(r"\d+")
        result = _run(piped.instruction_provider(ctx))
        assert result == ""

    def test_three_way_composition(self):
        result = C.select(author="user") + C.recent() + C.from_state("key")
        assert isinstance(result, CComposite)
        assert len(result.blocks) == 3

    def test_compile_with_phase_b_transform(self):
        compiled = _compile_context_spec("Analyze.", C.select(author="user"))
        assert compiled["include_contents"] == "none"
        assert callable(compiled["instruction"])

    def test_compile_composite(self):
        composite = C.from_state("topic") + C.user_only()
        compiled = _compile_context_spec("Review.", composite)
        assert compiled["include_contents"] == "none"
        assert callable(compiled["instruction"])

    def test_all_phase_b_are_ctransform(self):
        transforms = [
            C.select(author="user"),
            C.recent(),
            C.compact(),
            C.dedup(),
            C.truncate(max_turns=3),
            C.project("text"),
            C.fit(),
            C.fresh(),
            C.redact(r"\d+"),
        ]
        for t in transforms:
            assert isinstance(t, CTransform), f"{type(t)} is not a CTransform"

    def test_all_phase_b_are_frozen(self):
        transforms = [
            C.select(author="user"),
            C.recent(),
            C.compact(),
            C.dedup(),
            C.truncate(max_turns=3),
            C.project("text"),
            C.fit(),
            C.fresh(),
            C.redact(r"\d+"),
        ]
        for t in transforms:
            with pytest.raises(AttributeError):
                t._kind = "changed"
