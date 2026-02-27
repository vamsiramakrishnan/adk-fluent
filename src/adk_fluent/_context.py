"""Context Engineering module — declarative transforms for controlling what each agent sees.

The C class is the public API namespace. Each static method returns a
frozen dataclass (CTransform subclass) describing *what* context an
agent should receive. At build-time, ``_compile_context_spec`` lowers
these descriptors into the two ADK knobs: ``include_contents`` and
``instruction`` (as an async InstructionProvider).

Composition operators:
    +  union  (CComposite)
    |  pipe   (CPipe)

Usage:
    from adk_fluent._context import C

    Agent("writer")
        .context(C.window(n=3) + C.from_state("topic"))
        .instruct("Write about {topic}.")

    Agent("reviewer")
        .context(C.user_only())
        .instruct("Review the draft.")
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

_DEFAULT_MODEL = "gemini-2.5-flash"
_log = logging.getLogger(__name__)

__all__ = [
    "C",
    "CTransform",
    "CComposite",
    "CPipe",
    "CFromState",
    "CWindow",
    "CUserOnly",
    "CFromAgents",
    "CExcludeAgents",
    "CTemplate",
    "CSelect",
    "CRecent",
    "CCompact",
    "CDedup",
    "CTruncate",
    "CProject",
    "CBudget",
    "CPriority",
    "CFit",
    "CFresh",
    "CRedact",
    "CSummarize",
    "CRelevant",
    "CExtract",
    "CDistill",
    "CValidate",
    "_compile_context_spec",
]


# ======================================================================
# Base transform type
# ======================================================================


@dataclass(frozen=True)
class CTransform:
    """Base context transform descriptor.

    Every C.xxx() factory returns a frozen CTransform (or subclass).
    The two core fields map directly to ADK's LlmAgent knobs:

    - include_contents: "default" keeps conversation history, "none" suppresses it
    - instruction_provider: async callable(ctx) -> str that replaces instruction
    """

    include_contents: Literal["default", "none"] = "default"
    instruction_provider: Callable | None = None
    _kind: str = "base"

    def __add__(self, other: CTransform) -> CComposite:
        """Union: combine two transforms via +."""
        return CComposite(blocks=(*self._as_list(), *other._as_list()))

    def __or__(self, other: CTransform) -> CPipe:
        """Pipe: source | transform."""
        return CPipe(source=self, transform=other)

    def _as_list(self) -> tuple[CTransform, ...]:
        """Flatten for composite building. Overridden by CComposite."""
        return (self,)


# ======================================================================
# Composition types
# ======================================================================


@dataclass(frozen=True)
class CComposite(CTransform):
    """Union of multiple context blocks (via + operator)."""

    blocks: tuple[CTransform, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "include_contents", "none")
        object.__setattr__(self, "instruction_provider", _make_composite_provider(self.blocks))

    def _as_list(self) -> tuple[CTransform, ...]:
        return self.blocks


@dataclass(frozen=True)
class CPipe(CTransform):
    """Pipe transform: source feeds into transform (via | operator)."""

    source: CTransform | None = None
    transform: CTransform | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "include_contents", "none")
        object.__setattr__(self, "instruction_provider", _make_pipe_provider(self.source, self.transform))


# ======================================================================
# SELECT primitives
# ======================================================================


@dataclass(frozen=True)
class CFromState(CTransform):
    """Read named keys from session state and format as context."""

    keys: tuple[str, ...] = ()
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "from_state"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_from_state_provider(self.keys),
        )


@dataclass(frozen=True)
class CWindow(CTransform):
    """Include only the last N turn-pairs from conversation history."""

    n: int = 5
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "window"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_window_provider(self.n),
        )


@dataclass(frozen=True)
class CUserOnly(CTransform):
    """Include only user messages from conversation history."""

    include_contents: Literal["default", "none"] = "none"
    _kind: str = "user_only"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_user_only_provider(),
        )


@dataclass(frozen=True)
class CFromAgents(CTransform):
    """Include user messages + outputs from named agents."""

    agents: tuple[str, ...] = ()
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "from_agents"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_from_agents_provider(self.agents),
        )


@dataclass(frozen=True)
class CExcludeAgents(CTransform):
    """Exclude outputs from named agents."""

    agents: tuple[str, ...] = ()
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "exclude_agents"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_exclude_agents_provider(self.agents),
        )


@dataclass(frozen=True)
class CTemplate(CTransform):
    """Render a template string with {key} and {key?} placeholders from state."""

    template: str = ""
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "template"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_template_provider(self.template),
        )


# ======================================================================
# SELECT primitives (Phase B)
# ======================================================================


@dataclass(frozen=True)
class CSelect(CTransform):
    """Filter events by metadata: author, type, and/or tag."""

    author: str | tuple[str, ...] | None = None
    type: str | tuple[str, ...] | None = None
    tag: str | tuple[str, ...] | None = None
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "select"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_select_provider(self.author, self.type, self.tag),
        )


@dataclass(frozen=True)
class CRecent(CTransform):
    """Importance-weighted selection based on recency with exponential decay."""

    decay: str = "exponential"
    half_life: int = 10
    min_weight: float = 0.1
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "recent"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_recent_provider(self.decay, self.half_life, self.min_weight),
        )


# ======================================================================
# COMPRESS primitives (Phase B)
# ======================================================================


@dataclass(frozen=True)
class CCompact(CTransform):
    """Structural compaction — merge sequential same-author messages or tool calls."""

    strategy: str = "tool_calls"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "compact"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_compact_provider(self.strategy),
        )


@dataclass(frozen=True)
class CDedup(CTransform):
    """Remove duplicate or redundant events."""

    strategy: str = "exact"
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "dedup"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_dedup_provider(self.strategy, self.model),
        )


@dataclass(frozen=True)
class CTruncate(CTransform):
    """Hard limit on context size by turn count or estimated tokens."""

    max_turns: int | None = None
    max_tokens: int | None = None
    strategy: str = "tail"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "truncate"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_truncate_provider(self.max_turns, self.max_tokens, self.strategy),
        )


@dataclass(frozen=True)
class CProject(CTransform):
    """Keep only specific fields from event content."""

    fields: tuple[str, ...] = ("text",)
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "project"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_project_provider(self.fields),
        )


# ======================================================================
# BUDGET primitives
# ======================================================================


@dataclass(frozen=True)
class CBudget(CTransform):
    """Token budget constraint for context."""

    max_tokens: int = 8000
    overflow: str = "truncate_oldest"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "budget"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_budget_provider(self.max_tokens, self.overflow),
        )


@dataclass(frozen=True)
class CPriority(CTransform):
    """Priority tier for context ordering (lower = higher priority)."""

    tier: int = 2
    _kind: str = "priority"


@dataclass(frozen=True)
class CFit(CTransform):
    """Aggressive pruning to fit a hard token limit."""

    max_tokens: int = 4000
    strategy: str = "strict"
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "fit"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_fit_provider(self.max_tokens, self.strategy, self.model),
        )


# ======================================================================
# PROTECT primitives (Phase B)
# ======================================================================


@dataclass(frozen=True)
class CFresh(CTransform):
    """Prune stale context based on event timestamp."""

    max_age: float = 3600.0
    stale_action: str = "drop"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "fresh"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_fresh_provider(self.max_age, self.stale_action),
        )


@dataclass(frozen=True)
class CRedact(CTransform):
    """Remove PII or sensitive patterns from context via regex."""

    patterns: tuple[str, ...] = ()
    replacement: str = "[REDACTED]"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "redact"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_redact_provider(self.patterns, self.replacement),
        )


# ======================================================================
# Phase C: LLM-powered primitives
# ======================================================================


@dataclass(frozen=True)
class CSummarize(CTransform):
    """Lossy compression via LLM summarization."""

    scope: str = "all"
    model: str = _DEFAULT_MODEL
    prompt: str | None = None
    schema: dict | None = None
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "summarize"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_summarize_provider(self.scope, self.model, self.prompt, self.schema),
        )


@dataclass(frozen=True)
class CRelevant(CTransform):
    """Semantic relevance selection via LLM scoring."""

    query_key: str | None = None
    query: str | None = None
    top_k: int = 5
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "relevant"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_relevant_provider(self.query_key, self.query, self.top_k, self.model),
        )


@dataclass(frozen=True)
class CExtract(CTransform):
    """Structured extraction from conversation via LLM."""

    schema: dict | None = None
    key: str = "extracted"
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "extract"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_extract_provider(self.schema or {}, self.key, self.model),
        )


@dataclass(frozen=True)
class CDistill(CTransform):
    """Fact distillation from conversation via LLM."""

    key: str = "facts"
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "distill"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_distill_provider(self.key, self.model),
        )


@dataclass(frozen=True)
class CValidate(CTransform):
    """Context quality validation."""

    checks: tuple[str, ...] = ("completeness",)
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "validate"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_provider",
            _make_validate_provider(self.checks, self.model),
        )


# ======================================================================
# InstructionProvider helper
# ======================================================================


def _format_events_as_context(events: list) -> str:
    """Format a list of ADK events as ``[author]: text`` lines."""
    lines: list[str] = []
    for event in events:
        author = getattr(event, "author", "unknown")
        content = getattr(event, "content", None)
        if content is None:
            continue
        parts = getattr(content, "parts", None) or []
        texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", None)]
        if texts:
            text = "\n".join(texts)
            lines.append(f"[{author}]: {text}")
    return "\n".join(lines)


# ======================================================================
# InstructionProvider factories (private)
# ======================================================================


def _make_from_state_provider(keys: tuple[str, ...]) -> Callable:
    """Create an async provider that reads named keys from session state."""

    async def _provider(ctx: Any) -> str:
        parts: list[str] = []
        for key in keys:
            value = ctx.state.get(key)
            if value is not None:
                parts.append(f"[{key}]: {value}")
        return "\n".join(parts)

    _provider.__name__ = f"from_state_{'_'.join(keys)}"
    return _provider


def _make_window_provider(n: int) -> Callable:
    """Create an async provider that includes the last N turn-pairs."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        # A turn-pair is a user message + the model response(s) after it.
        # Walk backwards to find the last N user messages.
        user_indices: list[int] = []
        for i, event in enumerate(events):
            if getattr(event, "author", None) == "user":
                user_indices.append(i)

        # Take the last N turn-pair start indices
        start_indices = user_indices[-n:] if len(user_indices) >= n else user_indices
        if not start_indices:
            return ""

        # Include everything from the earliest selected user message onward
        window_start = start_indices[0]
        window_events = events[window_start:]
        return _format_events_as_context(window_events)

    _provider.__name__ = f"window_{n}"
    return _provider


def _make_user_only_provider() -> Callable:
    """Create an async provider that includes only user messages."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        user_events = [e for e in events if getattr(e, "author", None) == "user"]
        return _format_events_as_context(user_events)

    _provider.__name__ = "user_only"
    return _provider


def _make_from_agents_provider(agent_names: tuple[str, ...]) -> Callable:
    """Create an async provider including user + named agent outputs."""
    names_set = set(agent_names)

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        filtered = [
            e for e in events if getattr(e, "author", None) == "user" or getattr(e, "author", None) in names_set
        ]
        return _format_events_as_context(filtered)

    _provider.__name__ = f"from_agents_{'_'.join(agent_names)}"
    return _provider


def _make_exclude_agents_provider(agent_names: tuple[str, ...]) -> Callable:
    """Create an async provider excluding named agents."""
    names_set = set(agent_names)

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        filtered = [e for e in events if getattr(e, "author", None) not in names_set]
        return _format_events_as_context(filtered)

    _provider.__name__ = f"exclude_agents_{'_'.join(agent_names)}"
    return _provider


def _make_template_provider(template: str) -> Callable:
    """Create an async provider that renders a template with state values.

    Supports:
    - {key}  — required placeholder, raises KeyError if missing
    - {key?} — optional placeholder, replaced with empty string if missing
    """

    async def _provider(ctx: Any) -> str:
        state = ctx.state

        def _replace(match: re.Match) -> str:
            key = match.group(1)
            optional = match.group(2) == "?"
            value = state.get(key)
            if value is None:
                if optional:
                    return ""
                raise KeyError(f"Template placeholder '{{{key}}}' not found in state")
            return str(value)

        # Match {key} and {key?} patterns
        return re.sub(r"\{(\w+)(\??)}", _replace, template)

    _provider.__name__ = "template"
    return _provider


# ======================================================================
# LLM client helper (Phase C)
# ======================================================================

_genai_client: Any = None


async def _call_llm(model: str, prompt: str, response_schema: dict | None = None) -> str:
    """Call an LLM model with the given prompt. Lazily initializes the genai client.

    Args:
        model: Model name (e.g. "gemini-2.5-flash").
        prompt: The prompt text.
        response_schema: If provided, request JSON output conforming to this schema.

    Returns:
        The generated text response.
    """
    global _genai_client
    if _genai_client is None:
        from google import genai

        _genai_client = genai.Client()

    config: dict[str, Any] | None = None
    if response_schema is not None:
        config = {
            "response_mime_type": "application/json",
        }

    response = await _genai_client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return response.text or ""


def _fingerprint_events(events: list) -> str:
    """Compute a stable fingerprint for a list of events.

    Returns the first 12 hex chars of the SHA-256 hash of concatenated
    event texts. Used as cache key suffix.
    """
    h = hashlib.sha256()
    for event in events:
        author = getattr(event, "author", "?")
        text = _extract_event_text(event)
        h.update(f"{author}:{text}".encode())
    return h.hexdigest()[:12]


# ======================================================================
# Composition provider factories
# ======================================================================


def _make_composite_provider(blocks: tuple[CTransform, ...]) -> Callable:
    """Create a provider that runs all block providers and concatenates results."""

    async def _provider(ctx: Any) -> str:
        parts: list[str] = []
        for block in blocks:
            p = block.instruction_provider
            if p is not None:
                result = await p(ctx)
                if result:
                    parts.append(result)
        return "\n".join(parts)

    _provider.__name__ = "composite"
    return _provider


def _make_pipe_provider(source: CTransform | None, transform: CTransform | None) -> Callable:
    """Create a provider that pipes source output through transform.

    The transform's provider receives a modified context where
    session.events is replaced with a single synthetic event
    containing the source's output text.
    """

    async def _provider(ctx: Any) -> str:
        # Step 1: get source output
        source_text = ""
        if source is not None and source.instruction_provider is not None:
            source_text = await source.instruction_provider(ctx)

        if not source_text:
            return ""

        # Step 2: if transform has no provider, return source as-is
        if transform is None or transform.instruction_provider is None:
            return source_text

        # Step 3: pipe through transform — create a synthetic context
        # with the source output as a single event
        synthetic_event = _SyntheticEvent("context", source_text)

        class _PipedSession:
            """Minimal session stand-in with synthetic events."""

            def __init__(self, events: list) -> None:
                self.events = events

        class _PipedCtx:
            """Minimal context wrapping the piped session."""

            def __init__(self, original_ctx: Any, events: list) -> None:
                self.session = _PipedSession(events)
                self.state = original_ctx.state

        piped_ctx = _PipedCtx(ctx, [synthetic_event])
        return await transform.instruction_provider(piped_ctx)

    _provider.__name__ = "pipe"
    return _provider


# ======================================================================
# Synthetic event for compact provider output
# ======================================================================


class _SyntheticPart:
    """Minimal part object with a .text attribute."""

    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        self.text = text


class _SyntheticContent:
    """Minimal content object with a .parts list."""

    __slots__ = ("parts",)

    def __init__(self, text: str) -> None:
        self.parts = [_SyntheticPart(text)]


class _SyntheticEvent:
    """Lightweight event stand-in for compacted output.

    Compatible with _format_events_as_context(): has .author and
    .content.parts[].text attributes.
    """

    __slots__ = ("author", "content")

    def __init__(self, author: str, text: str) -> None:
        self.author = author
        self.content = _SyntheticContent(text)


# ======================================================================
# Phase B provider factories
# ======================================================================


def _extract_event_text(event: Any) -> str:
    """Extract text content from an event, returning empty string if none."""
    content = getattr(event, "content", None)
    if content is None:
        return ""
    parts = getattr(content, "parts", None) or []
    texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", None)]
    return "\n".join(texts)


def _event_has_tool_call(event: Any) -> bool:
    """Check if an event contains a function call (tool invocation)."""
    content = getattr(event, "content", None)
    if content is None:
        return False
    parts = getattr(content, "parts", None) or []
    return any(getattr(p, "function_call", None) is not None for p in parts)


def _event_has_tool_response(event: Any) -> bool:
    """Check if an event contains a function response (tool result)."""
    content = getattr(event, "content", None)
    if content is None:
        return False
    parts = getattr(content, "parts", None) or []
    return any(getattr(p, "function_response", None) is not None for p in parts)


def _normalize_filter(value: str | tuple[str, ...] | None) -> set[str] | None:
    """Normalize a filter value to a set or None."""
    if value is None:
        return None
    if isinstance(value, str):
        return {value}
    return set(value)


# --- SELECT providers ---


def _make_select_provider(
    author: str | tuple[str, ...] | None,
    type_filter: str | tuple[str, ...] | None,
    tag: str | tuple[str, ...] | None,
) -> Callable:
    """Create a provider that filters events by author, type, and/or tag."""
    authors = _normalize_filter(author)
    types = _normalize_filter(type_filter)
    tags = _normalize_filter(tag)

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        filtered = []
        for event in events:
            # Filter by author
            if authors is not None:
                event_author = getattr(event, "author", None)
                if event_author not in authors:
                    continue
            # Filter by type
            if types is not None:
                matched_type = False
                if "message" in types and _extract_event_text(event):
                    matched_type = True
                if "tool_call" in types and _event_has_tool_call(event):
                    matched_type = True
                if "tool_response" in types and _event_has_tool_response(event):
                    matched_type = True
                if not matched_type:
                    continue
            # Filter by tag (custom metadata)
            if tags is not None:
                event_tags = getattr(event, "tags", None) or []
                if not tags.intersection(set(event_tags)):
                    continue
            filtered.append(event)
        return _format_events_as_context(filtered)

    _provider.__name__ = "select"
    return _provider


def _make_recent_provider(decay: str, half_life: int, min_weight: float) -> Callable:
    """Create a provider that weights events by recency using exponential decay."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""
        n = len(events)
        # Assign weights: most recent = 1.0, decaying backwards
        weighted: list[tuple[Any, float]] = []
        for i, event in enumerate(events):
            age = n - 1 - i  # 0 for most recent
            if decay == "linear":
                weight = max(1.0 - age / max(half_life * 2, 1), 0.0)
            else:  # exponential
                weight = math.exp(-0.693 * age / max(half_life, 1))  # ln(2) ≈ 0.693
            if weight >= min_weight:
                weighted.append((event, weight))
        # Keep only events above threshold, format them
        kept = [e for e, _ in weighted]
        return _format_events_as_context(kept)

    _provider.__name__ = "recent"
    return _provider


# --- COMPRESS providers ---


def _make_compact_provider(strategy: str) -> Callable:
    """Create a provider that merges sequential same-author events."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""

        if strategy == "tool_calls":
            # Merge consecutive tool_call + tool_response pairs into summaries
            compacted: list[Any] = []
            i = 0
            while i < len(events):
                if _event_has_tool_call(events[i]):
                    # Collect consecutive tool call/response pairs
                    tool_count = 0
                    while i < len(events) and (_event_has_tool_call(events[i]) or _event_has_tool_response(events[i])):
                        tool_count += 1
                        i += 1
                    compacted.append(_SyntheticEvent("tool", f"[tool calls: {tool_count} interactions]"))
                else:
                    compacted.append(events[i])
                    i += 1
            return _format_events_as_context(compacted)
        else:
            # "all" — merge consecutive same-author messages
            compacted = []
            i = 0
            while i < len(events):
                current_author = getattr(events[i], "author", None)
                texts: list[str] = []
                while i < len(events) and getattr(events[i], "author", None) == current_author:
                    text = _extract_event_text(events[i])
                    if text:
                        texts.append(text)
                    i += 1
                if texts:
                    compacted.append(_SyntheticEvent(current_author or "unknown", "\n".join(texts)))
            return _format_events_as_context(compacted)

    _provider.__name__ = "compact"
    return _provider


def _make_dedup_provider(strategy: str, model: str = _DEFAULT_MODEL) -> Callable:
    """Create a provider that removes duplicate events."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""

        if strategy == "semantic":
            # LLM-judged semantic deduplication
            fp = _fingerprint_events(events)
            cache_key = f"temp:_dedup_semantic_{fp}"
            cached = ctx.state.get(cache_key)
            if cached is not None:
                try:
                    indices = json.loads(str(cached))
                    selected = [events[i] for i in indices if i < len(events)]
                    return _format_events_as_context(selected)
                except (json.JSONDecodeError, IndexError):
                    pass

            # Format events for LLM
            numbered: list[str] = []
            for i, event in enumerate(events):
                text = _extract_event_text(event)
                author = getattr(event, "author", "unknown")
                if text:
                    numbered.append(f"{i}. [{author}]: {text[:200]}")

            if not numbered:
                return ""

            dedup_prompt = (
                "Identify semantically unique events from this list. "
                "If two events convey the same information, keep only the later one.\n\n"
                + "\n".join(numbered)
                + "\n\nRespond with a JSON array of indices to KEEP: [0, 2, 5, ...]"
            )

            try:
                result = await _call_llm(model, dedup_prompt)
                indices = json.loads(result)
                if not isinstance(indices, list):
                    indices = list(range(len(events)))
            except Exception as e:
                _log.warning("C.dedup(semantic) LLM call failed: %s", e)
                indices = list(range(len(events)))

            ctx.state[cache_key] = json.dumps(indices)
            selected = [events[i] for i in indices if i < len(events)]
            return _format_events_as_context(selected)

        # Non-LLM strategies: exact and structural
        seen: set[str] = set()
        deduped: list[Any] = []
        for event in events:
            text = _extract_event_text(event)
            if strategy == "structural":
                key = " ".join(text.split())
            else:
                key = text
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            deduped.append(event)
        return _format_events_as_context(deduped)

    _provider.__name__ = "dedup"
    return _provider


def _make_truncate_provider(
    max_turns: int | None,
    max_tokens: int | None,
    strategy: str,
) -> Callable:
    """Create a provider that limits context by turns or estimated tokens."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""

        if max_turns is not None:
            # Limit by turn count (user messages as turn boundaries)
            user_indices = [i for i, e in enumerate(events) if getattr(e, "author", None) == "user"]
            if strategy == "tail":
                # Keep last N turns
                start_indices = user_indices[-max_turns:] if len(user_indices) > max_turns else user_indices
                start = start_indices[0] if start_indices else 0
                events = events[start:]
            else:
                # "head" — keep first N turns
                end_indices = user_indices[:max_turns]
                if end_indices and len(user_indices) > max_turns:
                    # Include up to the start of the (N+1)th turn
                    next_turn = user_indices[max_turns] if max_turns < len(user_indices) else len(events)
                    events = events[:next_turn]

        if max_tokens is not None:
            # Estimate tokens as chars / 4 (rough approximation)
            formatted = _format_events_as_context(events)
            estimated = len(formatted) // 4
            if estimated > max_tokens:
                # Truncate from the appropriate end
                target_chars = max_tokens * 4
                if strategy == "tail":
                    formatted = formatted[-target_chars:]
                else:
                    formatted = formatted[:target_chars]
                return formatted

        return _format_events_as_context(events)

    _provider.__name__ = "truncate"
    return _provider


def _make_project_provider(fields: tuple[str, ...]) -> Callable:
    """Create a provider that keeps only specified fields from events."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""
        lines: list[str] = []
        for event in events:
            parts_data: list[str] = []
            author = getattr(event, "author", "unknown")
            for field in fields:
                if field == "text":
                    text = _extract_event_text(event)
                    if text:
                        parts_data.append(text)
                elif field == "author":
                    parts_data.append(f"author={author}")
                elif field == "function_call":
                    content = getattr(event, "content", None)
                    if content:
                        for p in getattr(content, "parts", []):
                            fc = getattr(p, "function_call", None)
                            if fc:
                                parts_data.append(f"call={getattr(fc, 'name', '?')}")
                elif field == "function_response":
                    content = getattr(event, "content", None)
                    if content:
                        for p in getattr(content, "parts", []):
                            fr = getattr(p, "function_response", None)
                            if fr:
                                parts_data.append(f"response={getattr(fr, 'name', '?')}")
                else:
                    val = getattr(event, field, None)
                    if val is not None:
                        parts_data.append(f"{field}={val}")
            if parts_data:
                lines.append(f"[{author}]: {' | '.join(parts_data)}")
        return "\n".join(lines)

    _provider.__name__ = "project"
    return _provider


# --- BUDGET providers ---


def _estimate_tokens(text: str) -> int:
    """Rough token estimation: chars / 4."""
    return len(text) // 4


def _make_budget_provider(max_tokens: int, overflow: str) -> Callable:
    """Create a provider that enforces a token budget on context."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""
        formatted = _format_events_as_context(events)
        estimated = _estimate_tokens(formatted)
        if estimated <= max_tokens:
            return formatted
        # Over budget — apply overflow strategy
        target_chars = max_tokens * 4
        if overflow == "truncate_oldest":
            return formatted[-target_chars:]
        elif overflow == "truncate_newest":
            return formatted[:target_chars]
        else:
            # Default: truncate oldest
            return formatted[-target_chars:]

    _provider.__name__ = "budget"
    return _provider


def _make_fit_provider(max_tokens: int, strategy: str, model: str = _DEFAULT_MODEL) -> Callable:
    """Create a provider that aggressively prunes to fit a hard token limit."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""

        target_chars = max_tokens * 4

        if strategy == "strict":
            # Drop events from oldest until we fit
            kept: list[Any] = []
            total = 0
            for event in reversed(events):
                text = _extract_event_text(event)
                event_chars = len(f"[{getattr(event, 'author', '?')}]: {text}\n")
                if total + event_chars > target_chars:
                    break
                kept.append(event)
                total += event_chars
            kept.reverse()
            return _format_events_as_context(kept)

        elif strategy == "cascade":
            # Step 1: Compact tool calls
            compacted = _apply_compact_to_events(events)
            formatted = _format_events_as_context(compacted)
            if _estimate_tokens(formatted) <= max_tokens:
                return formatted

            # Step 2: Dedup (exact)
            deduped = _apply_dedup_to_events(compacted)
            formatted = _format_events_as_context(deduped)
            if _estimate_tokens(formatted) <= max_tokens:
                return formatted

            # Step 3: Hard truncate from oldest
            kept = []
            total = 0
            for event in reversed(deduped):
                text = _extract_event_text(event)
                event_chars = len(f"[{getattr(event, 'author', '?')}]: {text}\n")
                if total + event_chars > target_chars:
                    break
                kept.append(event)
                total += event_chars
            kept.reverse()
            formatted = _format_events_as_context(kept)
            if _estimate_tokens(formatted) <= max_tokens:
                return formatted

            # Step 4: Summarize if still over budget
            try:
                summary = await _call_llm(
                    model,
                    f"Summarize this conversation in under {max_tokens} tokens, "
                    f"preserving key facts and decisions:\n\n{formatted}",
                )
                return summary
            except Exception as e:
                _log.warning("C.fit(cascade) summarize failed: %s", e)
                return formatted[-target_chars:]

        elif strategy == "compact_then_summarize":
            # Step 1: Compact
            compacted = _apply_compact_to_events(events)
            formatted = _format_events_as_context(compacted)
            if _estimate_tokens(formatted) <= max_tokens:
                return formatted

            # Step 2: Summarize
            try:
                summary = await _call_llm(
                    model,
                    f"Summarize this conversation in under {max_tokens} tokens:\n\n{formatted}",
                )
                return summary
            except Exception as e:
                _log.warning("C.fit(compact_then_summarize) summarize failed: %s", e)
                return formatted[-target_chars:]

        else:
            # Default: just truncate the string
            formatted = _format_events_as_context(events)
            return formatted[-target_chars:] if len(formatted) > target_chars else formatted

    _provider.__name__ = "fit"
    return _provider


def _apply_compact_to_events(events: list) -> list:
    """Apply tool_calls compaction to events (non-async helper)."""
    compacted: list[Any] = []
    i = 0
    while i < len(events):
        if _event_has_tool_call(events[i]):
            tool_count = 0
            while i < len(events) and (_event_has_tool_call(events[i]) or _event_has_tool_response(events[i])):
                tool_count += 1
                i += 1
            compacted.append(_SyntheticEvent("tool", f"[tool calls: {tool_count} interactions]"))
        else:
            compacted.append(events[i])
            i += 1
    return compacted


def _apply_dedup_to_events(events: list) -> list:
    """Apply exact deduplication to events (non-async helper)."""
    seen: set[str] = set()
    deduped: list[Any] = []
    for event in events:
        text = _extract_event_text(event)
        if text and text in seen:
            continue
        if text:
            seen.add(text)
        deduped.append(event)
    return deduped


# --- PROTECT providers ---


def _make_fresh_provider(max_age: float, stale_action: str) -> Callable:
    """Create a provider that drops events older than max_age seconds."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""
        now = time.time()
        fresh: list[Any] = []
        for event in events:
            # Try to get timestamp from event
            ts = getattr(event, "timestamp", None)
            if ts is not None:
                # Convert to epoch if it's a datetime
                if hasattr(ts, "timestamp"):
                    event_time = ts.timestamp()
                else:
                    event_time = float(ts)
                age = now - event_time
                if age > max_age and stale_action == "drop":
                    continue
            # No timestamp = always fresh (can't determine age)
            fresh.append(event)
        return _format_events_as_context(fresh)

    _provider.__name__ = "fresh"
    return _provider


def _make_redact_provider(patterns: tuple[str, ...], replacement: str) -> Callable:
    """Create a provider that redacts matching patterns from context."""
    compiled = [re.compile(p) for p in patterns]

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""
        formatted = _format_events_as_context(events)
        for pattern in compiled:
            formatted = pattern.sub(replacement, formatted)
        return formatted

    _provider.__name__ = "redact"
    return _provider


# ======================================================================
# Phase C provider factories (LLM-powered)
# ======================================================================


def _make_summarize_provider(scope: str, model: str, prompt: str | None, schema: dict | None) -> Callable:
    """Create a provider that summarizes context via LLM."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""

        # Select events by scope
        if scope == "tool_results":
            selected = [e for e in events if _event_has_tool_response(e)]
        elif scope == "before_window":
            # Everything before the last 5 user messages
            user_indices = [i for i, e in enumerate(events) if getattr(e, "author", None) == "user"]
            cutoff = user_indices[-5] if len(user_indices) >= 5 else 0
            selected = events[:cutoff]
        else:  # "all"
            selected = events

        if not selected:
            return ""

        fp = _fingerprint_events(selected)
        cache_key = f"temp:_summary_{scope}_{fp}"

        # Check cache
        cached = ctx.state.get(cache_key)
        if cached is not None:
            return str(cached)

        # Build LLM prompt
        formatted = _format_events_as_context(selected)
        system = prompt or "Summarize the following conversation concisely, preserving key facts and decisions."
        if schema:
            system += f"\n\nProvide the summary as JSON conforming to this schema: {json.dumps(schema)}"
        full_prompt = f"{system}\n\n{formatted}"

        try:
            result = await _call_llm(model, full_prompt, response_schema=schema)
        except Exception as e:
            _log.warning("C.summarize() LLM call failed: %s", e)
            result = formatted  # Fallback to raw context

        ctx.state[cache_key] = result
        return result

    _provider.__name__ = "summarize"
    return _provider


def _make_relevant_provider(query_key: str | None, query: str | None, top_k: int, model: str) -> Callable:
    """Create a provider that selects events by semantic relevance via LLM."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""

        # Resolve query
        resolved_query = query
        if query_key is not None:
            resolved_query = ctx.state.get(query_key)
            if resolved_query is None:
                # If query_key == "__user_content__", read last user message
                if query_key == "__user_content__":
                    for e in reversed(events):
                        if getattr(e, "author", None) == "user":
                            resolved_query = _extract_event_text(e)
                            break
                if resolved_query is None:
                    return _format_events_as_context(events)  # Can't score, return all

        if not resolved_query:
            return _format_events_as_context(events)

        # Check cache
        query_hash = hashlib.sha256(str(resolved_query).encode()).hexdigest()[:8]
        events_hash = _fingerprint_events(events)
        cache_key = f"temp:_relevance_{query_hash}_{events_hash}"
        cached = ctx.state.get(cache_key)

        if cached is not None:
            try:
                indices = json.loads(str(cached))
                selected = [events[i] for i in indices if i < len(events)]
                return _format_events_as_context(selected)
            except (json.JSONDecodeError, IndexError):
                pass

        # Format events as numbered list for LLM scoring
        numbered: list[str] = []
        for i, event in enumerate(events):
            text = _extract_event_text(event)
            author = getattr(event, "author", "unknown")
            if text:
                numbered.append(f"{i}. [{author}]: {text[:200]}")

        if not numbered:
            return ""

        score_prompt = (
            f"Score each event below from 0 to 10 for relevance to this query: \"{resolved_query}\"\n\n"
            + "\n".join(numbered)
            + "\n\nRespond with a JSON array of objects: [{\"index\": <int>, \"score\": <float>}, ...]"
        )

        try:
            result = await _call_llm(model, score_prompt)
            scores = json.loads(result)
            if isinstance(scores, list):
                scored = sorted(scores, key=lambda x: x.get("score", 0), reverse=True)
                top_indices = [s["index"] for s in scored[:top_k] if s.get("score", 0) > 0]
            else:
                top_indices = list(range(min(top_k, len(events))))
        except Exception as e:
            _log.warning("C.relevant() LLM call failed: %s", e)
            top_indices = list(range(min(top_k, len(events))))

        # Cache the indices
        ctx.state[cache_key] = json.dumps(top_indices)

        selected = [events[i] for i in top_indices if i < len(events)]
        return _format_events_as_context(selected)

    _provider.__name__ = "relevant"
    return _provider


def _make_extract_provider(schema: dict, key: str, model: str) -> Callable:
    """Create a provider that extracts structured data from conversation via LLM."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""

        fp = _fingerprint_events(events)
        cache_key = f"temp:_extract_{key}_{fp}"

        cached = ctx.state.get(cache_key)
        if cached is not None:
            # Also ensure the key is set in state for downstream agents
            if ctx.state.get(key) is None:
                ctx.state[key] = cached
            return f"[{key}]: {cached}"

        formatted = _format_events_as_context(events)
        schema_desc = json.dumps(schema) if schema else "{}"
        extract_prompt = (
            f"Extract structured data from the following conversation.\n\n"
            f"Schema: {schema_desc}\n\n"
            f"Conversation:\n{formatted}\n\n"
            f"Respond with a JSON object conforming to the schema above."
        )

        try:
            result = await _call_llm(model, extract_prompt, response_schema=schema)
            # Validate JSON
            parsed = json.loads(result)
            result_str = json.dumps(parsed)
        except Exception as e:
            _log.warning("C.extract() LLM call failed: %s", e)
            result_str = "{}"

        ctx.state[cache_key] = result_str
        ctx.state[key] = result_str  # Write to state for downstream agents
        return f"[{key}]: {result_str}"

    _provider.__name__ = "extract"
    return _provider


def _make_distill_provider(key: str, model: str) -> Callable:
    """Create a provider that extracts atomic facts from conversation via LLM."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""

        fp = _fingerprint_events(events)
        cache_key = f"temp:_facts_{key}_{fp}"

        cached = ctx.state.get(cache_key)
        if cached is not None:
            if ctx.state.get(f"_facts_{key}") is None:
                ctx.state[f"_facts_{key}"] = cached
            facts = json.loads(str(cached)) if isinstance(cached, str) else cached
            return "\n".join(f"- {f}" for f in facts) if isinstance(facts, list) else str(cached)

        formatted = _format_events_as_context(events)
        distill_prompt = (
            f"Extract discrete atomic facts from this conversation. "
            f"Each fact should be a single, self-contained statement.\n\n"
            f"{formatted}\n\n"
            f"Respond with a JSON array of strings: [\"fact1\", \"fact2\", ...]"
        )

        try:
            result = await _call_llm(model, distill_prompt)
            facts = json.loads(result)
            if not isinstance(facts, list):
                facts = [str(facts)]
        except Exception as e:
            _log.warning("C.distill() LLM call failed: %s", e)
            facts = []

        facts_json = json.dumps(facts)
        ctx.state[cache_key] = facts_json
        ctx.state[f"_facts_{key}"] = facts_json
        return "\n".join(f"- {f}" for f in facts)

    _provider.__name__ = "distill"
    return _provider


def _make_validate_provider(checks: tuple[str, ...], model: str) -> Callable:
    """Create a provider that validates context quality."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""

        formatted = _format_events_as_context(events)
        warnings: list[str] = []

        for check in checks:
            if check == "completeness":
                # Check that common expected state keys exist
                for k in ("intent", "user_message", "requirements"):
                    val = ctx.state.get(k)
                    if val is not None and str(val).strip() == "":
                        warnings.append(f"State key '{k}' is empty.")

            elif check == "freshness":
                # Check for stale events
                now = time.time()
                stale_count = 0
                for event in events:
                    ts = getattr(event, "timestamp", None)
                    if ts is not None:
                        event_time = ts.timestamp() if hasattr(ts, "timestamp") else float(ts)
                        if now - event_time > 3600:
                            stale_count += 1
                if stale_count > 0:
                    warnings.append(f"{stale_count} event(s) are older than 1 hour.")

            elif check == "token_efficiency":
                # Check for high duplication
                texts = [_extract_event_text(e) for e in events]
                unique = set(texts)
                if len(texts) > 1 and len(unique) < len(texts) * 0.7:
                    dup_pct = int((1 - len(unique) / len(texts)) * 100)
                    warnings.append(f"Context has ~{dup_pct}% duplicate content.")

            elif check == "contradictions":
                fp = _fingerprint_events(events)
                cache_key = f"temp:_contradictions_{fp}"
                cached = ctx.state.get(cache_key)
                if cached is not None:
                    if str(cached).strip() and str(cached) != "none":
                        warnings.append(str(cached))
                else:
                    validate_prompt = (
                        "Analyze this conversation for contradictions. "
                        "If you find contradictory statements, describe them briefly. "
                        "If no contradictions, respond with exactly 'none'.\n\n"
                        f"{formatted}"
                    )
                    try:
                        result = await _call_llm(model, validate_prompt)
                        ctx.state[cache_key] = result
                        if result.strip().lower() != "none":
                            warnings.append(result)
                    except Exception as e:
                        _log.warning("C.validate() contradiction check failed: %s", e)

        if warnings:
            warning_block = "\n".join(f"<warning>{w}</warning>" for w in warnings)
            return f"{formatted}\n\n{warning_block}"
        return formatted

    _provider.__name__ = "validate"
    return _provider


# ======================================================================
# C — public API namespace
# ======================================================================


class C:
    """Context engineering namespace. Each method returns a frozen CTransform descriptor.

    Usage:
        Agent("writer").context(C.window(n=3))
        Agent("summarizer").context(C.from_state("topic", "style"))
        Agent("reviewer").context(C.user_only())
        Agent("analyst").context(C.none())
    """

    @staticmethod
    def none() -> CTransform:
        """Suppress all conversation history."""
        return CTransform(include_contents="none")

    @staticmethod
    def default() -> CTransform:
        """Keep default conversation history (pass-through)."""
        return CTransform(include_contents="default")

    @staticmethod
    def user_only() -> CUserOnly:
        """Include only user messages."""
        return CUserOnly()

    @staticmethod
    def from_agents(*names: str) -> CFromAgents:
        """Include user messages + outputs from named agents."""
        return CFromAgents(agents=names)

    @staticmethod
    def exclude_agents(*names: str) -> CExcludeAgents:
        """Exclude outputs from named agents."""
        return CExcludeAgents(agents=names)

    @staticmethod
    def window(*, n: int = 5) -> CWindow:
        """Include last N turn-pairs from conversation history."""
        return CWindow(n=n)

    @staticmethod
    def last_n_turns(n: int) -> CWindow:
        """Alias for C.window(n=n)."""
        return CWindow(n=n)

    @staticmethod
    def from_state(*keys: str) -> CFromState:
        """Read named keys from session state as context."""
        return CFromState(keys=keys)

    @staticmethod
    def template(template_str: str) -> CTemplate:
        """Render a template string with {key} and {key?} state placeholders."""
        return CTemplate(template=template_str)

    @staticmethod
    def capture(key: str) -> Callable:
        """Capture the most recent user message into state[key].

        Delegates to S.capture(key) from adk_fluent._transforms.
        """
        from adk_fluent._transforms import S

        return S.capture(key)

    @staticmethod
    def select(
        *,
        author: str | tuple[str, ...] | None = None,
        type: str | tuple[str, ...] | None = None,
        tag: str | tuple[str, ...] | None = None,
    ) -> CSelect:
        """Filter events by metadata: author, type, and/or tag."""
        return CSelect(author=author, type=type, tag=tag)

    @staticmethod
    def recent(*, decay: str = "exponential", half_life: int = 10, min_weight: float = 0.1) -> CRecent:
        """Importance-weighted selection based on recency with exponential decay."""
        return CRecent(decay=decay, half_life=half_life, min_weight=min_weight)

    @staticmethod
    def compact(*, strategy: str = "tool_calls") -> CCompact:
        """Structural compaction — merge sequential same-author messages or tool calls."""
        return CCompact(strategy=strategy)

    @staticmethod
    def dedup(*, strategy: str = "exact", model: str = _DEFAULT_MODEL) -> CDedup:
        """Remove duplicate or redundant events. strategy='semantic' uses LLM."""
        return CDedup(strategy=strategy, model=model)

    @staticmethod
    def truncate(*, max_turns: int | None = None, max_tokens: int | None = None, strategy: str = "tail") -> CTruncate:
        """Hard limit on context by turn count or estimated tokens."""
        return CTruncate(max_turns=max_turns, max_tokens=max_tokens, strategy=strategy)

    @staticmethod
    def project(*fields: str) -> CProject:
        """Keep only specified fields from event content."""
        return CProject(fields=fields if fields else ("text",))

    @staticmethod
    def budget(*, max_tokens: int = 8000, overflow: str = "truncate_oldest") -> CBudget:
        """Set token budget constraint for context."""
        return CBudget(max_tokens=max_tokens, overflow=overflow)

    @staticmethod
    def priority(*, tier: int = 2) -> CPriority:
        """Set priority tier for context ordering."""
        return CPriority(tier=tier)

    @staticmethod
    def fit(*, max_tokens: int = 4000, strategy: str = "strict", model: str = _DEFAULT_MODEL) -> CFit:
        """Aggressive pruning to fit a hard token limit. strategy='cascade' uses LLM."""
        return CFit(max_tokens=max_tokens, strategy=strategy, model=model)

    @staticmethod
    def fresh(*, max_age: float = 3600.0, stale_action: str = "drop") -> CFresh:
        """Prune stale context based on event timestamp."""
        return CFresh(max_age=max_age, stale_action=stale_action)

    @staticmethod
    def redact(*patterns: str, replacement: str = "[REDACTED]") -> CRedact:
        """Remove PII or sensitive patterns from context via regex."""
        return CRedact(patterns=patterns, replacement=replacement)

    # --- Phase C: LLM-powered methods ---

    @staticmethod
    def summarize(
        *, scope: str = "all", model: str = _DEFAULT_MODEL, prompt: str | None = None, schema: dict | None = None
    ) -> CSummarize:
        """Summarize context via LLM. Scope: 'all', 'before_window', 'tool_results'."""
        return CSummarize(scope=scope, model=model, prompt=prompt, schema=schema)

    @staticmethod
    def relevant(
        *, query_key: str | None = None, query: str | None = None, top_k: int = 5, model: str = _DEFAULT_MODEL
    ) -> CRelevant:
        """Select events by semantic relevance to a query via LLM scoring."""
        return CRelevant(query_key=query_key, query=query, top_k=top_k, model=model)

    @staticmethod
    def extract(*, schema: dict | None = None, key: str = "extracted", model: str = _DEFAULT_MODEL) -> CExtract:
        """Extract structured data from conversation via LLM."""
        return CExtract(schema=schema, key=key, model=model)

    @staticmethod
    def distill(*, key: str = "facts", model: str = _DEFAULT_MODEL) -> CDistill:
        """Extract atomic facts from conversation via LLM."""
        return CDistill(key=key, model=model)

    @staticmethod
    def validate(*checks: str, model: str = _DEFAULT_MODEL) -> CValidate:
        """Validate context quality. Checks: 'contradictions', 'completeness', 'freshness', 'token_efficiency'."""
        return CValidate(checks=checks if checks else ("completeness",), model=model)


# ======================================================================
# _compile_context_spec — lower C descriptors to ADK config
# ======================================================================


def _compile_context_spec(
    developer_instruction: str | Callable | None,
    context_spec: CTransform | None,
) -> dict[str, Any]:
    """Lower a CTransform descriptor + developer instruction to ADK config.

    Returns a dict with:
        - "include_contents": "default" | "none"
        - "instruction": str | async Callable (InstructionProvider) | None

    When context_spec has an instruction_provider, creates a combined
    async provider that:
        1. Templates state variables into the developer instruction
        2. Gets context from the C transform's provider
        3. Returns combined instruction + context block
    """
    if context_spec is None:
        return {
            "include_contents": "default",
            "instruction": developer_instruction,
        }

    include_contents = context_spec.include_contents
    spec_provider = context_spec.instruction_provider

    if spec_provider is None:
        # No provider — just pass through the instruction as-is
        return {
            "include_contents": include_contents,
            "instruction": developer_instruction,
        }

    # Build a combined async instruction provider
    raw_instruction = developer_instruction

    async def _combined_provider(ctx: Any) -> str:
        # Step 1: resolve the developer instruction
        if raw_instruction is None:
            instruction = ""
        elif callable(raw_instruction):
            result = raw_instruction(ctx)
            # Handle async instruction providers
            import asyncio

            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                instruction = await result
            else:
                instruction = str(result)
        else:
            instruction = str(raw_instruction)

        # Template state variables into instruction ({key} patterns)
        if instruction and "{" in instruction:
            state = ctx.state

            def _sub(match: re.Match) -> str:
                key = match.group(1)
                optional = match.group(2) == "?"
                value = state.get(key)
                if value is None:
                    if optional:
                        return ""
                    # Leave unreplaced if not optional and not in state
                    return match.group(0)
                return str(value)

            instruction = re.sub(r"\{(\w+)(\??)}", _sub, instruction)

        # Step 2: get context from the C transform's provider
        context = await spec_provider(ctx)

        # Step 3: combine
        if not context:
            return instruction
        if not instruction:
            return context

        return f"{instruction}\n\n<conversation_context>\n{context}\n</conversation_context>"

    return {
        "include_contents": include_contents,
        "instruction": _combined_provider,
    }
