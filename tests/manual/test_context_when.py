"""Tests for C.when — conditional context inclusion."""

import asyncio
import concurrent.futures

import pytest

from adk_fluent._context import C, CComposite, CTransform, CWhen


# ======================================================================
# Mock helpers (same pattern as test_c_phase_b.py)
# ======================================================================


class _MockPart:
    def __init__(self, text=None):
        self.text = text


class _MockContent:
    def __init__(self, parts):
        self.parts = parts


class _MockEvent:
    def __init__(self, author, text):
        self.author = author
        self.content = _MockContent([_MockPart(text=text)])
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
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ======================================================================
# CWhen dataclass
# ======================================================================


class TestCWhenDataclass:
    def test_returns_cwhen(self):
        t = C.when("verbose", C.from_state("topic"))
        assert isinstance(t, CWhen)

    def test_is_ctransform(self):
        t = C.when("verbose", C.from_state("topic"))
        assert isinstance(t, CTransform)

    def test_is_frozen(self):
        t = C.when("verbose", C.from_state("topic"))
        with pytest.raises(AttributeError):
            t.predicate = "other"

    def test_has_instruction_provider(self):
        t = C.when("verbose", C.from_state("topic"))
        assert t.instruction_provider is not None
        assert callable(t.instruction_provider)

    def test_include_contents_is_none(self):
        t = C.when("verbose", C.from_state("topic"))
        assert t.include_contents == "none"

    def test_kind(self):
        t = C.when("verbose", C.from_state("topic"))
        assert t._kind == "when"


# ======================================================================
# Runtime evaluation: callable predicates
# ======================================================================


class TestCWhenCallable:
    def test_true_callable_includes_block(self):
        t = C.when(lambda s: True, C.from_state("topic"))
        ctx = _MockCtx(state={"topic": "AI safety"})
        result = _run(t.instruction_provider(ctx))
        assert "AI safety" in result

    def test_false_callable_excludes_block(self):
        t = C.when(lambda s: False, C.from_state("topic"))
        ctx = _MockCtx(state={"topic": "AI safety"})
        result = _run(t.instruction_provider(ctx))
        assert result == ""

    def test_callable_receives_state(self):
        received = {}

        def pred(s):
            received.update(s)
            return True

        t = C.when(pred, C.from_state("x"))
        ctx = _MockCtx(state={"x": "hello", "y": "world"})
        _run(t.instruction_provider(ctx))
        assert "x" in received
        assert "y" in received

    def test_predicate_based_on_state_value(self):
        t = C.when(lambda s: s.get("score", 0) > 5, C.from_state("topic"))
        # Score too low — excluded
        ctx_low = _MockCtx(state={"score": 3, "topic": "AI"})
        assert _run(t.instruction_provider(ctx_low)) == ""
        # Score high enough — included
        ctx_high = _MockCtx(state={"score": 10, "topic": "AI"})
        assert "AI" in _run(t.instruction_provider(ctx_high))


# ======================================================================
# Runtime evaluation: string predicates (state key shortcut)
# ======================================================================


class TestCWhenString:
    def test_truthy_key_includes_block(self):
        t = C.when("verbose", C.from_state("topic"))
        ctx = _MockCtx(state={"verbose": True, "topic": "AI"})
        result = _run(t.instruction_provider(ctx))
        assert "AI" in result

    def test_falsy_key_excludes_block(self):
        t = C.when("verbose", C.from_state("topic"))
        ctx = _MockCtx(state={"verbose": False, "topic": "AI"})
        result = _run(t.instruction_provider(ctx))
        assert result == ""

    def test_missing_key_excludes_block(self):
        t = C.when("verbose", C.from_state("topic"))
        ctx = _MockCtx(state={"topic": "AI"})
        result = _run(t.instruction_provider(ctx))
        assert result == ""

    def test_empty_string_key_excludes_block(self):
        t = C.when("verbose", C.from_state("topic"))
        ctx = _MockCtx(state={"verbose": "", "topic": "AI"})
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# Exception safety
# ======================================================================


class TestCWhenExceptionSafe:
    def test_exception_in_predicate_treated_as_false(self):
        def boom(s):
            raise ValueError("bad predicate")

        t = C.when(boom, C.from_state("topic"))
        ctx = _MockCtx(state={"topic": "AI"})
        result = _run(t.instruction_provider(ctx))
        assert result == ""


# ======================================================================
# Composition
# ======================================================================


class TestCWhenComposition:
    def test_when_plus_window_creates_composite(self):
        t = C.when("verbose", C.from_state("topic")) + C.from_state("name")
        assert isinstance(t, CComposite)

    def test_composite_includes_conditional_when_true(self):
        t = C.when("verbose", C.from_state("topic")) + C.from_state("name")
        ctx = _MockCtx(state={"verbose": True, "topic": "AI", "name": "Alice"})
        result = _run(t.instruction_provider(ctx))
        assert "AI" in result
        assert "Alice" in result

    def test_composite_excludes_conditional_when_false(self):
        t = C.when("verbose", C.from_state("topic")) + C.from_state("name")
        ctx = _MockCtx(state={"verbose": False, "topic": "AI", "name": "Alice"})
        result = _run(t.instruction_provider(ctx))
        assert "AI" not in result
        assert "Alice" in result

    def test_multiple_when_blocks(self):
        t = C.when("a", C.from_state("x")) + C.when("b", C.from_state("y"))
        # Both true
        ctx = _MockCtx(state={"a": True, "b": True, "x": "X", "y": "Y"})
        result = _run(t.instruction_provider(ctx))
        assert "X" in result
        assert "Y" in result
        # Only first true
        ctx = _MockCtx(state={"a": True, "b": False, "x": "X", "y": "Y"})
        result = _run(t.instruction_provider(ctx))
        assert "X" in result
        assert "Y" not in result
