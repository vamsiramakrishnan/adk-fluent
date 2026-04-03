"""Tests for G namespace -- guard composition and compilation."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from adk_fluent._guards import (
    G,
    GComposite,
    GGuard,
    GuardViolation,
    JudgmentResult,
    PIIFinding,
)
from adk_fluent._namespace_protocol import NamespaceSpec

# ── GComposite composition ────────────────────────────────────────────


class TestGComposite:
    def test_guard_or_guard(self):
        g = G.json() | G.length(max=500)
        assert isinstance(g, GComposite)
        assert len(g._items) == 2

    def test_guard_chain_three(self):
        g = G.json() | G.length(max=500) | G.regex(r"bad", action="block")
        assert len(g._items) == 3

    def test_guard_reads_keys_union(self):
        g = G.grounded(sources_key="docs") | G.json()
        assert g._reads_keys is not None
        assert "docs" in g._reads_keys

    def test_guard_writes_keys_always_empty(self):
        g = G.json() | G.length(max=500)
        assert g._writes_keys == frozenset()

    def test_namespace_spec_protocol(self):
        g = G.json()
        assert isinstance(g, NamespaceSpec)

    def test_composite_repr(self):
        g = G.json() | G.length(max=500)
        r = repr(g)
        assert "json" in r
        assert "length" in r

    def test_composite_len(self):
        g = G.json() | G.length(max=500) | G.pii("block")
        assert len(g) == 3

    def test_composite_as_list(self):
        g = G.json() | G.length(max=500)
        items = g._as_list()
        assert isinstance(items, tuple)
        assert len(items) == 2
        assert all(isinstance(i, GGuard) for i in items)

    def test_composite_kind(self):
        g = G.json() | G.length(max=500)
        assert g._kind == "guard_chain"

    def test_gguard_or_gcomposite(self):
        """GGuard | GComposite should work."""
        a = G.json()
        b = G.length(max=500) | G.pii("block")
        c = a._items[0] | b
        assert isinstance(c, GComposite)
        assert len(c._items) == 3

    def test_reads_keys_none_if_any_opaque(self):
        """If any guard has None reads, composite reads is None."""
        g = G.grounded(sources_key="docs") | G.toxicity()
        # toxicity has frozenset() reads, grounded has frozenset({"docs"})
        # so union should be frozenset({"docs"})
        assert g._reads_keys is not None


# ── GuardViolation exception ─────────────────────────────────────────


class TestGuardViolation:
    def test_fields(self):
        e = GuardViolation(
            guard_kind="pii",
            phase="post_model",
            detail="SSN detected",
            value="123-45-6789",
        )
        assert e.guard_kind == "pii"
        assert e.phase == "post_model"
        assert "SSN" in e.detail
        assert e.value == "123-45-6789"

    def test_str_contains_kind(self):
        e = GuardViolation("json", "post_model", "Invalid JSON")
        assert "[json]" in str(e)

    def test_is_exception(self):
        e = GuardViolation("test", "pre_model", "test detail")
        assert isinstance(e, Exception)


# ── JSON guard ────────────────────────────────────────────────────────


class TestJsonGuard:
    def test_creates_guard(self):
        g = G.json()
        assert isinstance(g, GComposite)

    def test_kind(self):
        g = G.json()
        assert g._items[0]._kind == "json"

    def test_phase(self):
        from adk_fluent._guards import _Phase

        g = G.json()
        assert g._items[0]._phase == _Phase.POST_MODEL


# ── Length guard ──────────────────────────────────────────────────────


class TestLengthGuard:
    def test_max(self):
        g = G.length(max=100)
        assert g._items[0]._kind == "length"

    def test_min_max(self):
        g = G.length(min=10, max=500)
        assert len(g._items) == 1


# ── Regex guard ───────────────────────────────────────────────────────


class TestRegexGuard:
    def test_block(self):
        g = G.regex(r"ignore previous", action="block")
        assert g._items[0]._kind == "regex"

    def test_redact(self):
        g = G.regex(r"\d{3}-\d{2}-\d{4}", action="redact")
        assert len(g._items) == 1


# ── Output guard ──────────────────────────────────────────────────────


class TestOutputGuard:
    def test_creates_guard(self):
        @dataclass
        class Schema:
            answer: str

        g = G.output(Schema)
        assert g._items[0]._kind == "output"


# ── Input guard ───────────────────────────────────────────────────────


class TestInputGuard:
    def test_creates_guard(self):
        @dataclass
        class Schema:
            query: str

        g = G.input(Schema)
        assert g._items[0]._kind == "input"

    def test_phase_is_pre_model(self):
        from adk_fluent._guards import _Phase

        @dataclass
        class Schema:
            query: str

        g = G.input(Schema)
        assert g._items[0]._phase == _Phase.PRE_MODEL


# ── Budget guard ──────────────────────────────────────────────────────


class TestBudgetGuard:
    def test_creates_guard(self):
        g = G.budget(max_tokens=5000)
        assert any(guard._kind == "budget" for guard in g._items)


# ── Rate limit guard ─────────────────────────────────────────────────


class TestRateLimitGuard:
    def test_creates_guard(self):
        g = G.rate_limit(rpm=60)
        assert g._items[0]._kind == "rate_limit"


# ── Max turns guard ──────────────────────────────────────────────────


class TestMaxTurnsGuard:
    def test_creates_guard(self):
        g = G.max_turns(n=10)
        assert g._items[0]._kind == "max_turns"


# ── PII guard ─────────────────────────────────────────────────────────


class TestPiiGuard:
    def test_creates_guard(self):
        g = G.pii(action="redact")
        assert any(guard._kind == "pii" for guard in g._items)

    def test_custom_detector(self):
        class FakeDetector:
            async def detect(self, text):
                return [PIIFinding("TEST", 0, 4, 1.0, text[:4])]

        g = G.pii(action="block", detector=FakeDetector())
        assert len(g._items) >= 1

    def test_regex_detector_factory(self):
        detector = G.regex_detector(patterns=[r"\d{3}-\d{2}-\d{4}"])
        assert hasattr(detector, "detect")

    def test_regex_detector_default(self):
        detector = G.regex_detector()
        assert hasattr(detector, "detect")

    def test_regex_detector_dict_patterns(self):
        detector = G.regex_detector({"SSN": r"\d{3}-\d{2}-\d{4}"})
        assert hasattr(detector, "detect")


# ── Toxicity guard ────────────────────────────────────────────────────


class TestToxicityGuard:
    def test_creates_guard(self):
        g = G.toxicity(threshold=0.8)
        assert g._items[0]._kind == "toxicity"


# ── Grounded guard ───────────────────────────────────────────────────


class TestGroundedGuard:
    def test_reads_sources_key(self):
        g = G.grounded(sources_key="docs")
        assert g._reads_keys == frozenset({"docs"})


# ── Hallucination guard ──────────────────────────────────────────────


class TestHallucinationGuard:
    def test_creates_guard(self):
        g = G.hallucination(threshold=0.7, sources_key="refs")
        assert g._items[0]._kind == "hallucination"

    def test_reads_sources_key(self):
        g = G.hallucination(sources_key="refs")
        assert g._reads_keys == frozenset({"refs"})


# ── Topic guard ───────────────────────────────────────────────────────


class TestTopicGuard:
    def test_creates_guard(self):
        g = G.topic(deny=["politics"])
        assert g._items[0]._kind == "topic"


# ── When guard ────────────────────────────────────────────────────────


class TestWhenGuard:
    def test_wraps_guard(self):
        g = G.when(lambda s: s.get("premium"), G.budget(max_tokens=50000))
        assert len(g._items) >= 1

    def test_kind(self):
        g = G.when(lambda s: True, G.json())
        assert g._items[0]._kind == "when"


# ── Provider factories ───────────────────────────────────────────────


class TestProviderFactories:
    def test_multi_detector(self):
        d1 = G.regex_detector()
        d2 = G.regex_detector(patterns=[r"\b\d{9}\b"])
        multi = G.multi(d1, d2)
        assert hasattr(multi, "detect")

    def test_custom_detector(self):
        async def my_detect(text):
            return []

        det = G.custom(my_detect)
        assert hasattr(det, "detect")

    def test_llm_judge(self):
        judge = G.llm_judge(model="gemini-2.5-pro")
        assert hasattr(judge, "judge")

    def test_custom_judge(self):
        async def my_judge(text, context=None):
            return JudgmentResult(passed=True, score=0.0, reason="ok")

        judge = G.custom_judge(my_judge)
        assert hasattr(judge, "judge")


# ── Async provider behavior ──────────────────────────────────────────


class TestRegexDetectorAsync:
    @pytest.mark.asyncio
    async def test_detect_ssn(self):
        from adk_fluent._guards import _RegexDetector

        det = _RegexDetector()
        findings = await det.detect("My SSN is 123-45-6789")
        assert len(findings) >= 1
        assert any(f.kind == "SSN" for f in findings)

    @pytest.mark.asyncio
    async def test_detect_email(self):
        from adk_fluent._guards import _RegexDetector

        det = _RegexDetector()
        findings = await det.detect("Email me at test@example.com")
        assert len(findings) >= 1
        assert any(f.kind == "EMAIL" for f in findings)

    @pytest.mark.asyncio
    async def test_no_findings(self):
        from adk_fluent._guards import _RegexDetector

        det = _RegexDetector()
        findings = await det.detect("Nothing sensitive here")
        assert len(findings) == 0


class TestLLMJudgeAsync:
    @pytest.mark.asyncio
    async def test_always_passes(self):
        from adk_fluent._guards import _LLMJudge

        judge = _LLMJudge()
        result = await judge.judge("some text")
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_custom_judge_async(self):
        from adk_fluent._guards import _CustomJudge

        async def my_fn(text, context=None):
            return JudgmentResult(passed=False, score=0.9, reason="toxic")

        judge = _CustomJudge(my_fn)
        result = await judge.judge("bad text")
        assert result.passed is False
        assert result.score == 0.9


class TestMultiDetectorAsync:
    @pytest.mark.asyncio
    async def test_dedup_by_span(self):
        from adk_fluent._guards import _MultiDetector, _RegexDetector

        d1 = _RegexDetector()
        d2 = _RegexDetector()  # Same patterns — should dedup
        multi = _MultiDetector([d1, d2])
        findings = await multi.detect("SSN: 123-45-6789")
        # Both detectors find the same span, should be deduped
        spans = [(f.start, f.end) for f in findings]
        assert len(spans) == len(set(spans))


# ── GGuard repr ───────────────────────────────────────────────────────


class TestGGuardRepr:
    def test_repr(self):
        g = G.json()
        guard = g._items[0]
        assert repr(guard) == "GGuard('json')"


# ── PIIFinding dataclass ─────────────────────────────────────────────


class TestPIIFinding:
    def test_frozen(self):
        f = PIIFinding("SSN", 0, 11, 0.95, "123-45-6789")
        with pytest.raises(AttributeError):
            f.kind = "other"  # type: ignore[misc]

    def test_fields(self):
        f = PIIFinding("EMAIL", 5, 20, 0.9, "test@example.com")
        assert f.kind == "EMAIL"
        assert f.start == 5
        assert f.end == 20
        assert f.confidence == 0.9
        assert f.text == "test@example.com"
