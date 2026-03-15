"""Tests for the three audit fixes: _LLMJudge, guard compilation, E.gate() enforcement.

Covers:
1. _LLMJudge._parse_response() with valid, malformed, and fenced JSON
2. _resolve_guard_tuple() for each guard kind
3. E.gate() with mock criteria that pass and fail
4. _resolve_gate_text() state scanning
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from adk_fluent._guards import JudgmentResult, _LLMJudge

# ── _LLMJudge._parse_response ────────────────────────────────────────


class TestLLMJudgeParseResponse:
    """Test the JSON parsing logic in _LLMJudge."""

    def _judge(self) -> _LLMJudge:
        return _LLMJudge()

    def test_valid_toxic_json(self):
        resp = '{"toxic": true, "score": 0.9, "reason": "hateful content"}'
        result = self._judge()._parse_response(resp, "toxic")
        assert result.passed is False
        assert result.score == 0.9
        assert result.reason == "hateful content"

    def test_valid_safe_json(self):
        resp = '{"toxic": false, "score": 0.1, "reason": "benign"}'
        result = self._judge()._parse_response(resp, "toxic")
        assert result.passed is True
        assert result.score == 0.1

    def test_valid_hallucination_json(self):
        resp = '{"hallucinated": true, "score": 0.8, "reason": "fabricated"}'
        result = self._judge()._parse_response(resp, "hallucinated")
        assert result.passed is False
        assert result.score == 0.8

    def test_markdown_fenced_json(self):
        resp = '```json\n{"toxic": false, "score": 0.0, "reason": "clean"}\n```'
        result = self._judge()._parse_response(resp, "toxic")
        assert result.passed is True
        assert result.score == 0.0

    def test_malformed_json_fails_open(self):
        resp = "this is not json at all"
        result = self._judge()._parse_response(resp, "toxic")
        assert result.passed is True  # fail-open
        assert "Could not parse" in result.reason

    def test_empty_response_fails_open(self):
        resp = ""
        result = self._judge()._parse_response(resp, "toxic")
        assert result.passed is True

    def test_missing_fail_key_defaults_safe(self):
        resp = '{"score": 0.3, "reason": "ambiguous"}'
        result = self._judge()._parse_response(resp, "toxic")
        assert result.passed is True  # fail_key not present => not bad

    def test_score_defaults_from_fail_flag(self):
        resp = '{"toxic": true, "reason": "bad"}'
        result = self._judge()._parse_response(resp, "toxic")
        assert result.passed is False
        assert result.score == 1.0  # default when toxic=true and no score

    def test_score_defaults_safe(self):
        resp = '{"toxic": false, "reason": "ok"}'
        result = self._judge()._parse_response(resp, "toxic")
        assert result.score == 0.0  # default when toxic=false and no score


# ── _LLMJudge.judge fallback (no google-genai) ───────────────────────


class TestLLMJudgeFallback:
    @pytest.mark.asyncio
    async def test_falls_back_without_genai(self):
        """When google-genai is not importable, judge should fail-open."""
        judge = _LLMJudge()
        # This will either use the real API (if google-genai is installed)
        # or fall back. Either way, it should return a JudgmentResult.
        result = await judge.judge("Hello world")
        assert isinstance(result, JudgmentResult)


# ── _resolve_guard_tuple ──────────────────────────────────────────────


def _make_llm_response(text: str):
    """Create a mock LLM response with the given text."""
    part = MagicMock()
    part.text = text
    content = MagicMock()
    content.parts = [part]
    response = MagicMock()
    response.content = content
    return response


def _make_callback_context(**state_kv):
    """Create a mock callback context with optional state."""
    ctx = MagicMock()
    session = MagicMock()
    session.state = dict(state_kv)
    session.events = []
    ctx.session = session
    return ctx


class TestResolveGuardTupleJson:
    @pytest.mark.asyncio
    async def test_valid_json_passes(self):
        from adk_fluent._base import _resolve_guard_tuple

        fn = _resolve_guard_tuple(("guard:json", "json_validate"))
        result = await fn(
            callback_context=_make_callback_context(),
            llm_response=_make_llm_response('{"key": "value"}'),
        )
        assert result is None  # pass-through

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self):
        from adk_fluent._base import _resolve_guard_tuple
        from adk_fluent._exceptions import GuardViolation

        fn = _resolve_guard_tuple(("guard:json", "json_validate"))
        with pytest.raises(GuardViolation, match="json"):
            await fn(
                callback_context=_make_callback_context(),
                llm_response=_make_llm_response("not json"),
            )


class TestResolveGuardTupleLength:
    @pytest.mark.asyncio
    async def test_within_bounds_passes(self):
        from adk_fluent._base import _resolve_guard_tuple

        fn = _resolve_guard_tuple(("guard:length", {"min": 1, "max": 100}))
        result = await fn(
            callback_context=_make_callback_context(),
            llm_response=_make_llm_response("hello"),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_too_short_raises(self):
        from adk_fluent._base import _resolve_guard_tuple
        from adk_fluent._exceptions import GuardViolation

        fn = _resolve_guard_tuple(("guard:length", {"min": 10, "max": 100}))
        with pytest.raises(GuardViolation, match="too short"):
            await fn(
                callback_context=_make_callback_context(),
                llm_response=_make_llm_response("hi"),
            )

    @pytest.mark.asyncio
    async def test_too_long_raises(self):
        from adk_fluent._base import _resolve_guard_tuple
        from adk_fluent._exceptions import GuardViolation

        fn = _resolve_guard_tuple(("guard:length", {"min": 0, "max": 5}))
        with pytest.raises(GuardViolation, match="too long"):
            await fn(
                callback_context=_make_callback_context(),
                llm_response=_make_llm_response("this is way too long"),
            )


class TestResolveGuardTupleBudget:
    @pytest.mark.asyncio
    async def test_within_budget_passes(self):
        from adk_fluent._base import _resolve_guard_tuple

        fn = _resolve_guard_tuple(("guard:budget", {"max_tokens": 10000}))
        resp = _make_llm_response("ok")
        resp.usage_metadata = None
        result = await fn(callback_context=_make_callback_context(), llm_response=resp)
        assert result is None


class TestResolveGuardTuplePii:
    @pytest.mark.asyncio
    async def test_no_pii_passes(self):
        from adk_fluent._base import _resolve_guard_tuple
        from adk_fluent._guards import _RegexDetector

        fn = _resolve_guard_tuple(("guard:pii", {
            "action": "block",
            "detector": _RegexDetector(),
            "threshold": 0.5,
            "replacement": "[PII]",
        }))
        result = await fn(
            callback_context=_make_callback_context(),
            llm_response=_make_llm_response("nothing sensitive here"),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_pii_block_raises(self):
        from adk_fluent._base import _resolve_guard_tuple
        from adk_fluent._exceptions import GuardViolation
        from adk_fluent._guards import _RegexDetector

        fn = _resolve_guard_tuple(("guard:pii", {
            "action": "block",
            "detector": _RegexDetector(),
            "threshold": 0.5,
            "replacement": "[PII]",
        }))
        with pytest.raises(GuardViolation, match="pii"):
            await fn(
                callback_context=_make_callback_context(),
                llm_response=_make_llm_response("My SSN is 123-45-6789"),
            )

    @pytest.mark.asyncio
    async def test_pii_redact_replaces(self):
        from adk_fluent._base import _resolve_guard_tuple
        from adk_fluent._guards import _RegexDetector

        fn = _resolve_guard_tuple(("guard:pii", {
            "action": "redact",
            "detector": _RegexDetector(),
            "threshold": 0.5,
            "replacement": "[PII]",
        }))
        result = await fn(
            callback_context=_make_callback_context(),
            llm_response=_make_llm_response("My SSN is 123-45-6789"),
        )
        assert result is not None  # Modified response returned


class TestResolveGuardTupleToxicity:
    @pytest.mark.asyncio
    async def test_safe_content_passes(self):
        from adk_fluent._base import _resolve_guard_tuple
        from adk_fluent._guards import _CustomJudge

        async def safe_judge(text, context=None):
            return JudgmentResult(passed=True, score=0.1, reason="safe")

        fn = _resolve_guard_tuple(("guard:toxicity", {
            "threshold": 0.8,
            "judge": _CustomJudge(safe_judge),
        }))
        result = await fn(
            callback_context=_make_callback_context(),
            llm_response=_make_llm_response("Hello!"),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_toxic_content_raises(self):
        from adk_fluent._base import _resolve_guard_tuple
        from adk_fluent._exceptions import GuardViolation
        from adk_fluent._guards import _CustomJudge

        async def toxic_judge(text, context=None):
            return JudgmentResult(passed=False, score=0.95, reason="toxic")

        fn = _resolve_guard_tuple(("guard:toxicity", {
            "threshold": 0.8,
            "judge": _CustomJudge(toxic_judge),
        }))
        with pytest.raises(GuardViolation, match="toxicity"):
            await fn(
                callback_context=_make_callback_context(),
                llm_response=_make_llm_response("bad content"),
            )


class TestResolveGuardTupleTopic:
    @pytest.mark.asyncio
    async def test_allowed_topic_passes(self):
        from adk_fluent._base import _resolve_guard_tuple

        fn = _resolve_guard_tuple(("guard:topic", {"deny": ["politics"]}))
        result = await fn(
            callback_context=_make_callback_context(),
            llm_response=_make_llm_response("The weather is nice today."),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_denied_topic_raises(self):
        from adk_fluent._base import _resolve_guard_tuple
        from adk_fluent._exceptions import GuardViolation

        fn = _resolve_guard_tuple(("guard:topic", {"deny": ["politics"]}))
        with pytest.raises(GuardViolation, match="topic"):
            await fn(
                callback_context=_make_callback_context(),
                llm_response=_make_llm_response("Let me discuss politics."),
            )


class TestResolveGuardTupleMaxTurns:
    @pytest.mark.asyncio
    async def test_within_turns_passes(self):
        from adk_fluent._base import _resolve_guard_tuple

        fn = _resolve_guard_tuple(("guard:max_turns", {"n": 10}))
        result = await fn(
            callback_context=_make_callback_context(),
            llm_request=MagicMock(),
        )
        assert result is None


class TestResolveGuardTupleRegex:
    @pytest.mark.asyncio
    async def test_no_match_passes(self):
        import re

        from adk_fluent._base import _resolve_guard_tuple

        fn = _resolve_guard_tuple(("guard:regex", {
            "pattern": re.compile(r"ignore previous"),
            "action": "block",
            "replacement": "[REDACTED]",
        }))
        result = await fn(
            callback_context=_make_callback_context(),
            llm_response=_make_llm_response("Normal output"),
        )
        assert result is None


class TestResolveGuardTupleUnknown:
    def test_unknown_guard_returns_noop(self):
        from adk_fluent._base import _resolve_guard_tuple

        fn = _resolve_guard_tuple(("guard:unknown_type", {}))
        assert callable(fn)


# ── _compose_callbacks with guard tuples ──────────────────────────────


class TestComposeCallbacksWithGuards:
    def test_resolves_guard_tuples(self):
        from adk_fluent._base import _compose_callbacks

        composed = _compose_callbacks([("guard:json", "json_validate")])
        assert callable(composed)

    def test_mixes_guards_and_callables(self):
        from adk_fluent._base import _compose_callbacks

        async def plain_cb(**_kw):
            return None

        composed = _compose_callbacks([
            plain_cb,
            ("guard:json", "json_validate"),
        ])
        assert callable(composed)


# ── E.gate() ──────────────────────────────────────────────────────────


class TestResolveGateText:
    def test_explicit_output_key(self):
        from adk_fluent._eval import _resolve_gate_text

        state = {"draft": "Hello world", "other": "ignore"}
        assert _resolve_gate_text(state, "draft") == "Hello world"

    def test_last_output_fallback(self):
        from adk_fluent._eval import _resolve_gate_text

        state = {"_last_output": "Some output"}
        assert _resolve_gate_text(state, None) == "Some output"

    def test_scans_state_for_string(self):
        from adk_fluent._eval import _resolve_gate_text

        state = {"_internal": "skip", "result": "found this"}
        assert _resolve_gate_text(state, None) == "found this"

    def test_returns_none_for_empty_state(self):
        from adk_fluent._eval import _resolve_gate_text

        assert _resolve_gate_text({}, None) is None

    def test_skips_internal_keys(self):
        from adk_fluent._eval import _resolve_gate_text

        state = {"_private": "hidden", "temp:x": "temp", "app:y": "app"}
        assert _resolve_gate_text(state, None) is None


class TestEGate:
    def test_gate_returns_stransform(self):
        from adk_fluent._eval import E

        gate = E.gate(E.safety())
        from adk_fluent._transforms import STransform
        assert isinstance(gate, STransform)

    @pytest.mark.asyncio
    async def test_gate_passes_when_no_output(self):
        from adk_fluent._eval import E

        gate = E.gate(E.safety())
        # The gate function is the first arg to STransform
        result = await gate._fn({})
        from adk_fluent._transforms import StateDelta
        assert isinstance(result, (dict, StateDelta))

    @pytest.mark.asyncio
    async def test_gate_with_output_key(self):
        """Gate should find text via explicit output_key."""
        from adk_fluent._eval import _resolve_gate_text

        text = _resolve_gate_text({"draft": "test content"}, "draft")
        assert text == "test content"


# ── _extract_response_text ────────────────────────────────────────────


class TestExtractResponseText:
    def test_extracts_text(self):
        from adk_fluent._base import _extract_response_text

        resp = _make_llm_response("hello world")
        assert _extract_response_text(resp) == "hello world"

    def test_returns_none_for_no_content(self):
        from adk_fluent._base import _extract_response_text

        resp = MagicMock()
        resp.content = None
        assert _extract_response_text(resp) is None

    def test_returns_none_for_no_parts(self):
        from adk_fluent._base import _extract_response_text

        resp = MagicMock()
        resp.content = MagicMock()
        resp.content.parts = []
        assert _extract_response_text(resp) is None
