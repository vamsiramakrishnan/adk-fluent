"""G module -- fluent guard composition surface.

Consistent with P, C, S, M, T, A, E namespaces.
G answers: 'What must this agent NEVER do?'

Usage::

    from adk_fluent import G

    agent.guard(G.pii("redact") | G.budget(5000) | G.output(Schema))
"""

from __future__ import annotations

import enum
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from adk_fluent._composite import Composite
from adk_fluent._exceptions import GuardViolation as GuardViolation

__all__ = [
    "G",
    "GComposite",
    "GGuard",
    "GuardViolation",
    "PIIDetector",
    "PIIFinding",
    "ContentJudge",
    "JudgmentResult",
]


# ── Data types and protocols ──────────────────────────────────────────


@dataclass(frozen=True)
class PIIFinding:
    """A single PII detection result."""

    kind: str
    start: int
    end: int
    confidence: float
    text: str


@runtime_checkable
class PIIDetector(Protocol):
    """Protocol for PII detection providers."""

    async def detect(self, text: str) -> list[PIIFinding]: ...


@dataclass(frozen=True)
class JudgmentResult:
    """Result from a content judgment provider."""

    passed: bool
    score: float
    reason: str


@runtime_checkable
class ContentJudge(Protocol):
    """Protocol for content judgment providers (toxicity, hallucination)."""

    async def judge(self, text: str, context: dict | None = None) -> JudgmentResult: ...


# ── Internal phase enum ───────────────────────────────────────────────


class _Phase(enum.Enum):
    PRE_AGENT = "pre_agent"
    PRE_MODEL = "pre_model"
    POST_MODEL = "post_model"
    CONTEXT = "context"
    MIDDLEWARE = "middleware"


# ── GGuard spec ───────────────────────────────────────────────────────


class GGuard:
    """A single guard specification. Composable via ``|``."""

    __slots__ = ("_kind", "_phase", "_reads_keys", "_writes_keys", "_compile")

    def __init__(
        self,
        kind: str,
        phase: _Phase,
        reads: frozenset[str] | None,
        compile_fn: Callable[[Any], None],
    ):
        self._kind = kind
        self._phase = phase
        self._reads_keys = reads
        self._writes_keys: frozenset[str] = frozenset()
        self._compile = compile_fn

    def _as_list(self) -> tuple[GGuard, ...]:
        return (self,)

    def __or__(self, other: GGuard | GComposite | Any) -> GComposite:
        if isinstance(other, GComposite):
            return GComposite([self, *other._items])
        if isinstance(other, GGuard):
            return GComposite([self, other])
        return NotImplemented

    def __repr__(self) -> str:
        return f"GGuard({self._kind!r})"


# ── GComposite chain ─────────────────────────────────────────────────


class GComposite(Composite, kind="guard_chain"):
    """Composable guard chain. The result of any ``G.xxx()`` call.

    Supports ``|`` for composition::

        G.json() | G.length(max=500) | G.pii("redact")
    """

    def __init__(self, guards: list[GGuard]) -> None:
        super().__init__(guards)

    # -- Builder integration --------------------------------------------------

    def _compile_into(self, builder: Any) -> None:
        """Compile all guards into a builder's callback/config state."""
        for guard in self._items:
            guard._compile(builder)
        existing = builder._config.get("_guard_specs", ())
        builder._config["_guard_specs"] = existing + tuple(self._items)

    # -- Override: guards compute _reads_keys from children -------------------

    @property
    def _reads_keys(self) -> frozenset[str] | None:
        """Union of all guard reads. ``None`` if any guard is opaque."""
        result: frozenset[str] = frozenset()
        for g in self._items:
            if g._reads_keys is None:
                return None
            result = result | g._reads_keys
        return result

    @property
    def _writes_keys(self) -> frozenset[str]:
        """Guards never write state."""
        return frozenset()


# ── Built-in provider implementations ────────────────────────────────


class _RegexDetector:
    """Default PII detector using regex patterns for SSN, email, CC, phone."""

    _DEFAULT_PATTERNS: dict[str, re.Pattern[str]] = {
        "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "CREDIT_CARD": re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
        "PHONE": re.compile(r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    }

    def __init__(self, patterns: dict[str, re.Pattern[str]] | None = None):
        self._patterns = patterns or self._DEFAULT_PATTERNS

    async def detect(self, text: str) -> list[PIIFinding]:
        findings: list[PIIFinding] = []
        for kind, pattern in self._patterns.items():
            for m in pattern.finditer(text):
                findings.append(
                    PIIFinding(
                        kind=kind,
                        start=m.start(),
                        end=m.end(),
                        confidence=0.9,
                        text=m.group(),
                    )
                )
        return findings


class _DLPDetector:
    """Google Cloud DLP-based PII detector.

    Requires ``google-cloud-dlp`` to be installed.
    """

    def __init__(
        self,
        project: str,
        info_types: list[str] | None = None,
        location: str = "global",
    ):
        try:
            import google.cloud.dlp_v2  # type: ignore[reportMissingImports]  # noqa: F401
        except ImportError as exc:
            msg = (
                "google-cloud-dlp is required for DLP-based PII detection. "
                "Install it with: pip install google-cloud-dlp"
            )
            raise ImportError(msg) from exc
        self._project = project
        self._info_types = info_types or [
            "PERSON_NAME",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "US_SOCIAL_SECURITY_NUMBER",
            "CREDIT_CARD_NUMBER",
        ]
        self._location = location

    async def detect(self, text: str) -> list[PIIFinding]:
        import google.cloud.dlp_v2 as dlp  # type: ignore[reportMissingImports]

        client = dlp.DlpServiceClient()
        inspect_config = {
            "info_types": [{"name": t} for t in self._info_types],
            "min_likelihood": dlp.Likelihood.POSSIBLE,
        }
        item = {"value": text}
        parent = f"projects/{self._project}/locations/{self._location}"
        response = client.inspect_content(request={"parent": parent, "inspect_config": inspect_config, "item": item})
        findings: list[PIIFinding] = []
        for finding in response.result.findings:
            findings.append(
                PIIFinding(
                    kind=finding.info_type.name,
                    start=0,
                    end=len(finding.quote) if finding.quote else 0,
                    confidence=finding.likelihood / 5.0,
                    text=finding.quote or "",
                )
            )
        return findings


class _PresidioDetector:
    """Presidio-analyzer-based PII detector.

    Uses Microsoft Presidio (presidio-analyzer), a widely-adopted
    context-aware PII detection engine with recognizers for names,
    addresses, IBANs, IP addresses, and many other entity types that
    regex alone cannot reliably match.

    Install with: ``pip install adk-fluent[pii-presidio]`` (or
    ``pip install presidio-analyzer``). The default NLP engine is spaCy;
    on first use Presidio will require a spaCy model such as
    ``en_core_web_lg``.
    """

    def __init__(
        self,
        *,
        language: str = "en",
        entities: list[str] | None = None,
        score_threshold: float = 0.5,
        analyzer: Any = None,
    ):
        self._language = language
        self._entities = entities
        self._score_threshold = score_threshold

        if analyzer is not None:
            self._analyzer = analyzer
            return
        try:
            from presidio_analyzer import AnalyzerEngine  # type: ignore[reportMissingImports]
        except ImportError as exc:
            msg = (
                "presidio-analyzer is required for Presidio-based PII detection. "
                "Install with: pip install adk-fluent[pii-presidio] "
                "(or pip install presidio-analyzer and a spaCy model, e.g. en_core_web_lg)."
            )
            raise ImportError(msg) from exc
        self._analyzer = AnalyzerEngine()

    async def detect(self, text: str) -> list[PIIFinding]:
        # Presidio is sync; run in the default executor so we do not block
        # the event loop on larger inputs.
        import asyncio

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self._analyzer.analyze(
                text=text,
                language=self._language,
                entities=self._entities,
                score_threshold=self._score_threshold,
            ),
        )
        findings: list[PIIFinding] = []
        for r in results:
            findings.append(
                PIIFinding(
                    kind=r.entity_type,
                    start=r.start,
                    end=r.end,
                    confidence=float(r.score),
                    text=text[r.start : r.end],
                )
            )
        return findings


class _MultiDetector:
    """Union of multiple PII detectors, deduplicating by span."""

    def __init__(self, detectors: list[Any]):
        self._detectors = detectors

    async def detect(self, text: str) -> list[PIIFinding]:
        all_findings: list[PIIFinding] = []
        for detector in self._detectors:
            results = await detector.detect(text)
            all_findings.extend(results)
        # Dedup by span (start, end)
        seen: set[tuple[int, int]] = set()
        deduped: list[PIIFinding] = []
        for f in all_findings:
            span = (f.start, f.end)
            if span not in seen:
                seen.add(span)
                deduped.append(f)
        return deduped


class _CustomDetector:
    """Wraps an async callable as a PIIDetector."""

    def __init__(self, fn: Callable[..., Any]):
        self._fn = fn

    async def detect(self, text: str) -> list[PIIFinding]:
        return await self._fn(text)


class _LLMJudge:
    """LLM-based content judge using Google GenAI.

    Calls the configured model to evaluate content for safety, toxicity,
    or hallucination depending on the evaluation prompt.

    Falls back to a conservative pass-through if the GenAI SDK is not
    available or the API call fails (fail-open with a warning).
    """

    _TOXICITY_PROMPT = (
        "You are a content safety evaluator. Analyze the following text for "
        "toxic, harmful, hateful, or inappropriate content.\n\n"
        "Text to evaluate:\n```\n{text}\n```\n\n"
        "Respond with ONLY a JSON object (no markdown, no explanation):\n"
        '{{"toxic": true/false, "score": 0.0-1.0, "reason": "brief explanation"}}\n'
        "where score=0.0 means perfectly safe and score=1.0 means extremely toxic."
    )

    _HALLUCINATION_PROMPT = (
        "You are a factual accuracy evaluator. Analyze whether the following "
        "text contains hallucinated or fabricated information not supported "
        "by the provided sources.\n\n"
        "Text to evaluate:\n```\n{text}\n```\n\n"
        "{sources_section}"
        "Respond with ONLY a JSON object (no markdown, no explanation):\n"
        '{{"hallucinated": true/false, "score": 0.0-1.0, "reason": "brief explanation"}}\n'
        "where score=0.0 means fully grounded and score=1.0 means entirely fabricated."
    )

    def __init__(self, model: str = "gemini-2.5-flash"):
        self._model = model

    async def judge(self, text: str, context: dict | None = None) -> JudgmentResult:
        """Evaluate content using LLM.

        Args:
            text: The content to evaluate.
            context: Optional dict with ``"mode"`` (``"toxicity"`` or
                ``"hallucination"``) and ``"sources"`` for grounding checks.

        Returns:
            JudgmentResult with pass/fail, score, and reason.
        """
        context = context or {}
        mode = context.get("mode", "toxicity")

        if mode == "hallucination":
            sources = context.get("sources", "")
            sources_section = f"Source material:\n```\n{sources}\n```\n\n" if sources else ""
            prompt = self._HALLUCINATION_PROMPT.format(text=text, sources_section=sources_section)
            fail_key = "hallucinated"
        else:
            prompt = self._TOXICITY_PROMPT.format(text=text)
            fail_key = "toxic"

        try:
            from google import genai  # type: ignore[attr-defined]

            client = genai.Client()
            response = await client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            return self._parse_response(response.text or "", fail_key)
        except ImportError:
            import logging
            import warnings

            msg = (
                "google-genai not installed — _LLMJudge guard is disabled and will "
                "pass all content through unchecked. Install with: pip install google-genai"
            )
            logging.getLogger(__name__).warning(msg)
            warnings.warn(msg, stacklevel=2)
            return JudgmentResult(passed=True, score=0.0, reason="google-genai not available")
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("_LLMJudge API call failed: %s", exc)
            return JudgmentResult(passed=True, score=0.0, reason=f"Judge API error: {exc}")

    def _parse_response(self, response_text: str, fail_key: str) -> JudgmentResult:
        """Parse the JSON response from the judge LLM."""
        import json as _json

        # Strip markdown code fences if present
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            data = _json.loads(text)
            is_bad = bool(data.get(fail_key, False))
            score = float(data.get("score", 1.0 if is_bad else 0.0))
            reason = str(data.get("reason", ""))
            return JudgmentResult(passed=not is_bad, score=score, reason=reason)
        except (_json.JSONDecodeError, ValueError, TypeError):
            # If we can't parse the response, fail-open with a warning
            return JudgmentResult(passed=True, score=0.0, reason=f"Could not parse judge response: {text[:200]}")


class _CustomJudge:
    """Wraps an async callable as a ContentJudge."""

    def __init__(self, fn: Callable[..., Any]):
        self._fn = fn

    async def judge(self, text: str, context: dict | None = None) -> JudgmentResult:
        return await self._fn(text, context)


# ── G factory class ───────────────────────────────────────────────────


def _noop_compile(_builder: Any) -> None:
    """No-op compile function for guards that only need spec tracking."""


class G:
    """Factory for composable guard specs.

    Every method returns a ``GComposite`` that can be chained with ``|``
    and compiled into a builder via ``.guard()``.
    """

    # ------------------------------------------------------------------
    # Structural guards
    # ------------------------------------------------------------------

    @staticmethod
    def json() -> GComposite:
        """Validate that model output is valid JSON."""

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("after_model_callback", [])
            cbs.append(("guard:json", "json_validate"))

        return GComposite([GGuard("json", _Phase.POST_MODEL, frozenset(), _compile)])

    @staticmethod
    def length(
        *,
        min: int = 0,
        max: int = 100_000,  # noqa: A002
    ) -> GComposite:
        """Enforce output length bounds."""

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("after_model_callback", [])
            cbs.append(("guard:length", {"min": min, "max": max}))

        return GComposite([GGuard("length", _Phase.POST_MODEL, frozenset(), _compile)])

    @staticmethod
    def regex(
        pattern: str,
        *,
        action: str = "block",
        replacement: str = "[REDACTED]",
    ) -> GComposite:
        """Block or redact text matching a regex pattern.

        Args:
            pattern: Regex pattern to match.
            action: ``"block"`` to raise, ``"redact"`` to replace.
            replacement: Replacement text when action is ``"redact"``.
        """
        compiled = re.compile(pattern)

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("after_model_callback", [])
            cbs.append(
                (
                    "guard:regex",
                    {
                        "pattern": compiled,
                        "action": action,
                        "replacement": replacement,
                    },
                )
            )

        return GComposite([GGuard("regex", _Phase.POST_MODEL, frozenset(), _compile)])

    @staticmethod
    def output(schema_cls: type) -> GComposite:
        """Validate model output against a schema class."""

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("after_model_callback", [])
            cbs.append(("guard:output", schema_cls))

        return GComposite([GGuard("output", _Phase.POST_MODEL, frozenset(), _compile)])

    @staticmethod
    def input(schema_cls: type) -> GComposite:  # noqa: A003
        """Validate model input against a schema class."""

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("before_model_callback", [])
            cbs.append(("guard:input", schema_cls))

        return GComposite([GGuard("input", _Phase.PRE_MODEL, frozenset(), _compile)])

    # ------------------------------------------------------------------
    # Policy guards
    # ------------------------------------------------------------------

    @staticmethod
    def budget(max_tokens: int) -> GComposite:
        """Enforce a token budget."""

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("after_model_callback", [])
            cbs.append(("guard:budget", {"max_tokens": max_tokens}))

        return GComposite([GGuard("budget", _Phase.POST_MODEL, frozenset(), _compile)])

    @staticmethod
    def rate_limit(rpm: int) -> GComposite:
        """Enforce requests-per-minute limit."""

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("before_model_callback", [])
            cbs.append(("guard:rate_limit", {"rpm": rpm}))

        return GComposite([GGuard("rate_limit", _Phase.PRE_MODEL, frozenset(), _compile)])

    @staticmethod
    def max_turns(n: int) -> GComposite:
        """Enforce maximum conversation turns."""

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("before_model_callback", [])
            cbs.append(("guard:max_turns", {"n": n}))

        return GComposite([GGuard("max_turns", _Phase.PRE_MODEL, frozenset(), _compile)])

    # ------------------------------------------------------------------
    # A2UI output guards
    # ------------------------------------------------------------------

    @staticmethod
    def a2ui(
        *,
        max_components: int = 50,
        allowed_types: list[str] | None = None,
        deny_types: list[str] | None = None,
    ) -> GComposite:
        """Validate LLM-generated A2UI output.

        Checks that the number of components doesn't exceed ``max_components``
        and that only allowed component types are used.

        Args:
            max_components: Maximum number of components allowed.
            allowed_types: If set, only these component types are permitted.
            deny_types: If set, these component types are blocked.
        """

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("after_model_callback", [])
            cbs.append(
                (
                    "guard:a2ui",
                    {
                        "max_components": max_components,
                        "allowed_types": allowed_types,
                        "deny_types": deny_types,
                    },
                )
            )

        return GComposite([GGuard("a2ui", _Phase.POST_MODEL, frozenset(), _compile)])

    # ------------------------------------------------------------------
    # Content safety guards
    # ------------------------------------------------------------------

    @staticmethod
    def pii(
        action: str = "redact",
        *,
        detector: PIIDetector | None = None,
        threshold: float = 0.5,
        replacement: str = "[PII]",
    ) -> GComposite:
        """Detect and handle PII in model output.

        Args:
            action: ``"redact"`` to replace, ``"block"`` to raise.
            detector: Custom ``PIIDetector``; defaults to ``_RegexDetector``.
            threshold: Confidence threshold for findings.
            replacement: Replacement text for redaction.
        """
        effective_detector = detector or _RegexDetector()

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("after_model_callback", [])
            cbs.append(
                (
                    "guard:pii",
                    {
                        "action": action,
                        "detector": effective_detector,
                        "threshold": threshold,
                        "replacement": replacement,
                    },
                )
            )

        return GComposite([GGuard("pii", _Phase.POST_MODEL, frozenset(), _compile)])

    @staticmethod
    def toxicity(threshold: float = 0.8, *, judge: ContentJudge | None = None) -> GComposite:
        """Block toxic model output.

        Args:
            threshold: Score threshold above which content is blocked.
            judge: Custom ``ContentJudge``; defaults to ``_LLMJudge``.
        """
        effective_judge = judge or _LLMJudge()

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("after_model_callback", [])
            cbs.append(
                (
                    "guard:toxicity",
                    {"threshold": threshold, "judge": effective_judge},
                )
            )

        return GComposite([GGuard("toxicity", _Phase.POST_MODEL, frozenset(), _compile)])

    @staticmethod
    def topic(deny: list[str]) -> GComposite:
        """Block output that discusses denied topics.

        Args:
            deny: List of topic strings to block.
        """

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("after_model_callback", [])
            cbs.append(("guard:topic", {"deny": list(deny)}))

        return GComposite([GGuard("topic", _Phase.POST_MODEL, frozenset(), _compile)])

    @staticmethod
    def grounded(sources_key: str = "sources") -> GComposite:
        """Require model output to be grounded in source material.

        Args:
            sources_key: State key containing source documents.
        """

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("after_model_callback", [])
            cbs.append(("guard:grounded", {"sources_key": sources_key}))

        return GComposite(
            [
                GGuard(
                    "grounded",
                    _Phase.POST_MODEL,
                    frozenset({sources_key}),
                    _compile,
                )
            ]
        )

    @staticmethod
    def hallucination(
        threshold: float = 0.7,
        *,
        sources_key: str = "sources",
        judge: ContentJudge | None = None,
    ) -> GComposite:
        """Detect hallucinated content not supported by sources.

        Args:
            threshold: Score threshold above which content is flagged.
            sources_key: State key containing source documents.
            judge: Custom ``ContentJudge``; defaults to ``_LLMJudge``.
        """
        effective_judge = judge or _LLMJudge()

        def _compile(builder: Any) -> None:
            cbs = builder._callbacks.setdefault("after_model_callback", [])
            cbs.append(
                (
                    "guard:hallucination",
                    {
                        "threshold": threshold,
                        "sources_key": sources_key,
                        "judge": effective_judge,
                    },
                )
            )

        return GComposite(
            [
                GGuard(
                    "hallucination",
                    _Phase.POST_MODEL,
                    frozenset({sources_key}),
                    _compile,
                )
            ]
        )

    # ------------------------------------------------------------------
    # Conditional
    # ------------------------------------------------------------------

    @staticmethod
    def when(predicate: Callable[[Any], bool], guard: GComposite | GGuard) -> GComposite:
        """Conditionally apply a guard based on a state predicate.

        Args:
            predicate: Callable taking state dict, returning bool.
            guard: Guard to apply when predicate is true.
        """
        inner_guards = guard._items if isinstance(guard, GComposite) else [guard]

        def _compile(builder: Any) -> None:
            for g in inner_guards:
                g._compile(builder)

        reads = guard._reads_keys if isinstance(guard, GComposite) else guard._reads_keys
        return GComposite([GGuard("when", _Phase.CONTEXT, reads, _compile)])

    # ------------------------------------------------------------------
    # Provider factories
    # ------------------------------------------------------------------

    @staticmethod
    def dlp(
        project: str,
        *,
        info_types: list[str] | None = None,
        location: str = "global",
    ) -> _DLPDetector:
        """Create a Google Cloud DLP-based PII detector."""
        return _DLPDetector(project, info_types=info_types, location=location)

    @staticmethod
    def presidio(
        *,
        language: str = "en",
        entities: list[str] | None = None,
        score_threshold: float = 0.5,
        analyzer: Any = None,
    ) -> _PresidioDetector:
        """Create a Presidio-analyzer-based PII detector.

        Presidio is a production-grade, context-aware PII detection engine
        (Microsoft / open source) with built-in recognizers for names,
        addresses, IBANs, IP addresses, API keys, and many other entity
        types that regex cannot reliably match. Prefer this over
        ``G.regex_detector`` for anything beyond smoke tests.

        Args:
            language: ISO language code for the NLP pipeline (default ``en``).
            entities: Optional whitelist of entity types to detect. ``None``
                enables all registered recognizers.
            score_threshold: Confidence cutoff; findings below this score
                are dropped.
            analyzer: Optional pre-constructed ``AnalyzerEngine`` (for
                testing, custom recognizers, or non-default NLP engines).

        Requires ``pip install adk-fluent[pii-presidio]``.
        """
        return _PresidioDetector(
            language=language,
            entities=entities,
            score_threshold=score_threshold,
            analyzer=analyzer,
        )

    @staticmethod
    def regex_detector(
        patterns: list[str] | dict[str, str] | None = None,
    ) -> _RegexDetector:
        """Create a regex-based PII detector.

        Args:
            patterns: List of regex strings (auto-named) or dict of
                ``{kind: pattern}`` pairs. ``None`` uses built-in defaults.
        """
        if patterns is None:
            return _RegexDetector()
        if isinstance(patterns, list):
            compiled = {f"PATTERN_{i}": re.compile(p) for i, p in enumerate(patterns)}
            return _RegexDetector(compiled)
        return _RegexDetector({k: re.compile(v) for k, v in patterns.items()})

    @staticmethod
    def multi(*detectors: Any) -> _MultiDetector:
        """Combine multiple PII detectors, deduplicating by span."""
        return _MultiDetector(list(detectors))

    @staticmethod
    def custom(fn: Callable[..., Any]) -> _CustomDetector:
        """Wrap an async callable as a PII detector."""
        return _CustomDetector(fn)

    @staticmethod
    def llm_judge(model: str = "gemini-2.5-flash") -> _LLMJudge:
        """Create a placeholder LLM-based content judge."""
        return _LLMJudge(model)

    @staticmethod
    def custom_judge(fn: Callable[..., Any]) -> _CustomJudge:
        """Wrap an async callable as a content judge."""
        return _CustomJudge(fn)
