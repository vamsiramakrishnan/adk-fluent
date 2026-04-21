"""Context Engineering module — declarative transforms for controlling what each agent sees.

The C class is the public API namespace. Each static method returns a
frozen dataclass (CTransform subclass) describing *what* context an
agent should receive. At build-time, ``_compile_context_spec`` lowers
these descriptors into the two ADK knobs: ``include_contents`` and
``instruction`` (as an async InstructionProvider).

Composition operators:
    |  union  (CComposite) — the one composition operator for C
    >> pipe   (CPipe)       — source transform piped through another
                              (expressed via ``a >> b`` between transforms)

Usage:
    from adk_fluent._context import C

    Agent("writer")
        .context(C.window(n=3) | C.from_state("topic"))
        .instruct("Write about {topic}.")

    Agent("reviewer")
        .context(C.user_only())
        .instruct("Review the draft.")
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from adk_fluent._context_providers import (  # noqa: F401 — re-exports for backward compat
    _fingerprint_events,
    _format_events_as_context,
    _make_budget_provider,
    _make_compact_provider,
    _make_composite_provider,
    _make_dedup_provider,
    _make_distill_provider,
    _make_exclude_agents_provider,
    _make_extract_provider,
    _make_fit_provider,
    _make_fresh_provider,
    _make_from_agents_provider,
    _make_from_agents_windowed_provider,
    _make_from_state_provider,
    _make_notes_provider,
    _make_pipe_provider,
    _make_project_provider,
    _make_recent_provider,
    _make_redact_provider,
    _make_relevant_provider,
    _make_rolling_provider,
    _make_select_provider,
    _make_summarize_provider,
    _make_template_provider,
    _make_truncate_provider,
    _make_user_only_provider,
    _make_user_strategy_provider,
    _make_validate_provider,
    _make_when_provider,
    _make_window_provider,
    _SyntheticEvent,
    clear_notes,
    consolidate_notes,
    make_write_notes_callback,
)
from adk_fluent._frozen import _set_frozen_fields

_DEFAULT_MODEL = "gemini-2.5-flash"

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
    # Phase D: Scratchpads + Sugar
    "CNotes",
    "CWriteNotes",
    "CRolling",
    "CFromAgentsWindowed",
    "CUser",
    "CManusCascade",
    "CWhen",
    "CPipelineAware",
    "CSharedThread",
    "_compile_context_spec",
]


# ======================================================================
# Base transform type
# ======================================================================


@dataclass(frozen=True, slots=True)
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

    def __or__(self, other: CTransform) -> CComposite:
        """Union: ``a | b`` combines two transforms into one CComposite."""
        return CComposite(blocks=(*self._as_list(), *other._as_list()))

    def __rshift__(self, other: Any) -> Any:
        """Chain or attach: ``self >> other``.

        - ``CTransform >> Builder`` → attach via ``builder.context(self)``,
          returns the modified builder.
        - ``CTransform >> CTransform`` → pipe (returns ``CPipe``).
        """
        from adk_fluent._base import BuilderBase

        if isinstance(other, BuilderBase):
            return other.context(self)
        return CPipe(source=self, transform=other)

    def _as_list(self) -> tuple[CTransform, ...]:
        """Flatten for composite building. Overridden by CComposite."""
        return (self,)

    # ------------------------------------------------------------------
    # NamespaceSpec protocol: key metadata for contract tracing
    # ------------------------------------------------------------------

    @property
    def _reads_keys(self) -> frozenset[str] | None:
        """State keys this context spec reads. Subclasses override."""
        return None  # opaque by default

    @property
    def _writes_keys(self) -> frozenset[str] | None:
        """Context transforms never write state."""
        return frozenset()


# ======================================================================
# Composition helpers
# ======================================================================


def _derive_include_contents(
    children: tuple[CTransform, ...] | list[CTransform],
) -> str:
    """Derive ``include_contents`` from child transforms.

    Rule: if ANY child explicitly suppresses history (``"none"``),
    the composite suppresses.  Only when ALL children are neutral
    (``"default"``) does the composite keep history.  This makes
    data-injection transforms composable with history-filtering ones.
    """
    for child in children:
        if child.include_contents == "none":
            return "none"
    return "default"


# ======================================================================
# Composition types
# ======================================================================


@dataclass(frozen=True, slots=True)
class CComposite(CTransform):
    """Union of multiple context blocks (via + operator).

    The composite derives ``include_contents`` from its children:
    if ANY child suppresses history (``"none"``), the composite
    suppresses.  Only when ALL children are neutral (``"default"``)
    does the composite keep history.  This makes data-injection
    transforms (``CFromState``, ``CTemplate``, ``CNotes``) truly
    composable with history-filtering transforms.
    """

    blocks: tuple[CTransform, ...] = ()

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            include_contents=_derive_include_contents(self.blocks),
            instruction_provider=_make_composite_provider(self.blocks),
        )

    def _as_list(self) -> tuple[CTransform, ...]:
        return self.blocks

    @property
    def _reads_keys(self) -> frozenset[str] | None:
        """Aggregate _reads_keys from all children."""
        keys: set[str] = set()
        for block in self.blocks:
            child_keys = block._reads_keys
            if child_keys is not None:
                keys.update(child_keys)
        return frozenset(keys) if keys else None


@dataclass(frozen=True, slots=True)
class CPipe(CTransform):
    """Pipe transform: source feeds into transform (via | operator)."""

    source: CTransform | None = None
    transform: CTransform | None = None

    def __post_init__(self) -> None:
        children = tuple(c for c in (self.source, self.transform) if c is not None)
        _set_frozen_fields(
            self,
            include_contents=_derive_include_contents(children),
            instruction_provider=_make_pipe_provider(self.source, self.transform),
        )


# ======================================================================
# Conditional
# ======================================================================


@dataclass(frozen=True, slots=True)
class CWhen(CTransform):
    """Conditional context inclusion.

    Include the wrapped block only if the predicate evaluates to truthy
    at runtime. When ``predicate`` is a string, it is treated as a
    state key check: include when ``state[key]`` is truthy.

    PredicateSchema classes work via the callable path.
    """

    predicate: Any = None
    block: CTransform | None = None
    _kind: str = "when"

    def __post_init__(self) -> None:
        children = (self.block,) if self.block is not None else ()
        _set_frozen_fields(
            self,
            include_contents=_derive_include_contents(children),
            instruction_provider=_make_when_provider(self.predicate, self.block),
        )


# ======================================================================
# SELECT primitives
# ======================================================================


@dataclass(frozen=True, slots=True)
class CFromState(CTransform):
    """Read named keys from session state and format as context.

    This is a pure data-injection transform — it adds state values to the
    agent's prompt without suppressing conversation history.  If you also
    want to suppress history, compose explicitly::

        C.none() | C.from_state("key")   # inject state, no history
        C.from_state("key")              # inject state, keep history

    The convenience method ``.reads()`` composes ``C.none()`` for you
    (the common pipeline case) and accepts ``keep_history=True`` to opt
    out of suppression.
    """

    keys: tuple[str, ...] = ()
    include_contents: Literal["default", "none"] = "default"
    _kind: str = "from_state"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_from_state_provider(self.keys),
        )

    @property
    def _reads_keys(self) -> frozenset[str]:
        return frozenset(self.keys)


@dataclass(frozen=True, slots=True)
class CWindow(CTransform):
    """Include only the last N turn-pairs from conversation history."""

    n: int = 5
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "window"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_window_provider(self.n),
        )


@dataclass(frozen=True, slots=True)
class CUserOnly(CTransform):
    """Include only user messages from conversation history."""

    include_contents: Literal["default", "none"] = "none"
    _kind: str = "user_only"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_user_only_provider(),
        )


@dataclass(frozen=True, slots=True)
class CFromAgents(CTransform):
    """Include user messages + outputs from named agents."""

    agents: tuple[str, ...] = ()
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "from_agents"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_from_agents_provider(self.agents),
        )


@dataclass(frozen=True, slots=True)
class CExcludeAgents(CTransform):
    """Exclude outputs from named agents."""

    agents: tuple[str, ...] = ()
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "exclude_agents"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_exclude_agents_provider(self.agents),
        )


@dataclass(frozen=True, slots=True)
class CTemplate(CTransform):
    """Render a template string with {key} and {key?} placeholders from state.

    Pure data-injection transform — injects templated state values into the
    agent's prompt without suppressing conversation history.
    """

    template: str = ""
    include_contents: Literal["default", "none"] = "default"
    _kind: str = "template"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_template_provider(self.template),
        )

    @property
    def _reads_keys(self) -> frozenset[str]:
        # Extract {key} and {key?} placeholders from template
        return frozenset(re.findall(r"\{(\w+)\??}", self.template))


# ======================================================================
# SELECT primitives (Phase B)
# ======================================================================


@dataclass(frozen=True, slots=True)
class CSelect(CTransform):
    """Filter events by metadata: author, type, and/or tag."""

    author: str | tuple[str, ...] | None = None
    type: str | tuple[str, ...] | None = None
    tag: str | tuple[str, ...] | None = None
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "select"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_select_provider(self.author, self.type, self.tag),
        )


@dataclass(frozen=True, slots=True)
class CRecent(CTransform):
    """Importance-weighted selection based on recency with exponential decay."""

    decay: str = "exponential"
    half_life: int = 10
    min_weight: float = 0.1
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "recent"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_recent_provider(self.decay, self.half_life, self.min_weight),
        )


# ======================================================================
# COMPRESS primitives (Phase B)
# ======================================================================


@dataclass(frozen=True, slots=True)
class CCompact(CTransform):
    """Structural compaction — merge sequential same-author messages or tool calls."""

    strategy: str = "tool_calls"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "compact"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_compact_provider(self.strategy),
        )


@dataclass(frozen=True, slots=True)
class CDedup(CTransform):
    """Remove duplicate or redundant events."""

    strategy: str = "exact"
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "dedup"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_dedup_provider(self.strategy, self.model),
        )


@dataclass(frozen=True, slots=True)
class CTruncate(CTransform):
    """Hard limit on context size by turn count or estimated tokens."""

    max_turns: int | None = None
    max_tokens: int | None = None
    strategy: str = "tail"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "truncate"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_truncate_provider(self.max_turns, self.max_tokens, self.strategy),
        )


@dataclass(frozen=True, slots=True)
class CProject(CTransform):
    """Keep only specific fields from event content."""

    fields: tuple[str, ...] = ("text",)
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "project"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_project_provider(self.fields),
        )


# ======================================================================
# BUDGET primitives
# ======================================================================


@dataclass(frozen=True, slots=True)
class CBudget(CTransform):
    """Token budget constraint for context."""

    max_tokens: int = 8000
    overflow: str = "truncate_oldest"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "budget"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_budget_provider(self.max_tokens, self.overflow),
        )


@dataclass(frozen=True, slots=True)
class CPriority(CTransform):
    """Priority tier for context ordering (lower = higher priority)."""

    tier: int = 2
    _kind: str = "priority"


@dataclass(frozen=True, slots=True)
class CFit(CTransform):
    """Aggressive pruning to fit a hard token limit."""

    max_tokens: int = 4000
    strategy: str = "strict"
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "fit"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_fit_provider(self.max_tokens, self.strategy, self.model),
        )


# ======================================================================
# PROTECT primitives (Phase B)
# ======================================================================


@dataclass(frozen=True, slots=True)
class CFresh(CTransform):
    """Prune stale context based on event timestamp."""

    max_age: float = 3600.0
    stale_action: str = "drop"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "fresh"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_fresh_provider(self.max_age, self.stale_action),
        )


@dataclass(frozen=True, slots=True)
class CRedact(CTransform):
    """Remove PII or sensitive patterns from context via regex."""

    patterns: tuple[str, ...] = ()
    replacement: str = "[REDACTED]"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "redact"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_redact_provider(self.patterns, self.replacement),
        )


# ======================================================================
# Phase C: LLM-powered primitives
# ======================================================================


@dataclass(frozen=True, slots=True)
class CSummarize(CTransform):
    """Lossy compression via LLM summarization."""

    scope: str = "all"
    model: str = _DEFAULT_MODEL
    prompt: str | None = None
    schema: dict | None = None
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "summarize"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_summarize_provider(self.scope, self.model, self.prompt, self.schema),
        )


@dataclass(frozen=True, slots=True)
class CRelevant(CTransform):
    """Semantic relevance selection via LLM scoring."""

    query_key: str | None = None
    query: str | None = None
    top_k: int = 5
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "relevant"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_relevant_provider(self.query_key, self.query, self.top_k, self.model),
        )


@dataclass(frozen=True, slots=True)
class CExtract(CTransform):
    """Structured extraction from conversation via LLM."""

    schema: dict | None = None
    key: str = "extracted"
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "extract"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_extract_provider(self.schema or {}, self.key, self.model),
        )


@dataclass(frozen=True, slots=True)
class CDistill(CTransform):
    """Fact distillation from conversation via LLM."""

    key: str = "facts"
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "distill"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_distill_provider(self.key, self.model),
        )


@dataclass(frozen=True, slots=True)
class CValidate(CTransform):
    """Context quality validation."""

    checks: tuple[str, ...] = ("completeness",)
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "validate"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_validate_provider(self.checks, self.model),
        )


# ======================================================================
# Phase D: WRITE primitives (Scratchpads)
# ======================================================================


@dataclass(frozen=True, slots=True)
class CNotes(CTransform):
    """Read from an agent's structured scratchpad stored in session state.

    Notes are stored at ``state["_notes_{key}"]``. They are persistent
    across turns within a session. The ``format`` parameter controls
    rendering: ``"plain"`` (default), ``"checklist"``, ``"numbered"``.

    Pure data-injection transform — reads scratchpad notes without
    suppressing conversation history.
    """

    key: str = "default"
    format: str = "plain"
    include_contents: Literal["default", "none"] = "default"
    _kind: str = "notes"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_notes_provider(self.key, self.format),
        )

    @property
    def _reads_keys(self) -> frozenset[str]:
        return frozenset({f"_notes_{self.key}"})


@dataclass(frozen=True, slots=True)
class CWriteNotes(CTransform):
    """Write to an agent's structured scratchpad after agent execution.

    Compiles to a post-agent state write into ``state["_notes_{key}"]``.
    Strategies:

    - ``"append"`` — append new content to existing notes
    - ``"replace"`` — overwrite notes entirely
    - ``"merge"`` — merge new content, deduplicating entries
    - ``"prepend"`` — prepend new content before existing notes
    """

    key: str = "default"
    strategy: str = "append"
    source_key: str | None = None
    _kind: str = "write_notes"
    include_contents: Literal["default", "none"] = "default"

    def __post_init__(self) -> None:
        # CWriteNotes doesn't have an instruction_provider — it compiles
        # to a companion FnAgent that mutates state after the target agent.
        pass

    @property
    def _reads_keys(self) -> frozenset[str]:
        keys = {f"_notes_{self.key}"}
        if self.source_key:
            keys.add(self.source_key)
        return frozenset(keys)

    @property
    def _writes_keys(self) -> frozenset[str]:
        return frozenset({f"_notes_{self.key}"})


# ======================================================================
# Phase D: Molecule sugar (convenience compositions)
# ======================================================================


@dataclass(frozen=True, slots=True)
class CRolling(CTransform):
    """Rolling window with optional summarization of older turns.

    Equivalent to: ``C.window(n=n) | C.summarize(scope="before_window")``
    when ``summarize=True``, or just ``C.window(n=n)`` otherwise.
    """

    n: int = 5
    summarize: bool = False
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "rolling"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_rolling_provider(self.n, self.summarize, self.model),
        )


@dataclass(frozen=True, slots=True)
class CFromAgentsWindowed(CTransform):
    """Per-agent selective windowing.

    Takes a mapping of ``agent_name -> window_size``. Each agent's
    events are windowed independently, then combined.

    Example::

        C.from_agents_windowed(researcher=1, critic=3)
        # ≡ (C.select(author="researcher") | C.truncate(max_turns=1))
        #   + (C.select(author="critic") | C.truncate(max_turns=3))
    """

    agent_windows: tuple[tuple[str, int], ...] = ()
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "from_agents_windowed"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_from_agents_windowed_provider(self.agent_windows),
        )


@dataclass(frozen=True, slots=True)
class CUser(CTransform):
    """User message strategies.

    Strategies:

    - ``"all"`` — all user messages (same as ``C.user_only()``)
    - ``"first"`` — only the first user message
    - ``"last"`` — only the most recent user message
    - ``"bookend"`` — first and last user messages
    """

    strategy: str = "all"
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "user_strategy"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_user_strategy_provider(self.strategy),
        )


@dataclass(frozen=True, slots=True)
class CManusCascade(CTransform):
    """Manus-inspired progressive compression cascade.

    Applies: compact → dedup → summarize → truncate, stopping
    as soon as the context fits within the token budget.

    Equivalent to: ``C.fit(max_tokens=budget, strategy="cascade")``
    """

    budget: int = 8000
    model: str = _DEFAULT_MODEL
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "manus_cascade"

    def __post_init__(self) -> None:
        _set_frozen_fields(
            self,
            instruction_provider=_make_fit_provider(self.budget, "cascade", self.model),
        )


# Provider factories are in _context_providers.py (imported at module top).


@dataclass(frozen=True, slots=True)
class CPipelineAware(CTransform):
    """Topology-aware context for pipeline agents.

    Includes user messages plus explicit state keys while suppressing
    intermediate agent conversation history.  This addresses the gap
    between ``include_contents='default'`` (everything, including
    noisy intermediate agent text) and ``include_contents='none'``
    (current turn only, losing the user's original message).

    A pipeline agent often needs:
    - The user's original message (conversational context)
    - Structured data from state (routing info, extracted entities)
    - But NOT the raw text of intermediate agents (noise, duplication)

    ``C.pipeline_aware(*keys)`` is shorthand for
    ``C.user_only() | C.from_state(*keys)`` — it gives the agent
    exactly the user message plus named state values.

    Usage::

        # Classifier writes intent, handler reads it + user message
        classifier = Agent("classify").writes("intent")
        handler = Agent("handle").context(C.pipeline_aware("intent"))
        pipeline = classifier >> handler
    """

    keys: tuple[str, ...] = ()
    include_contents: Literal["default", "none"] = "none"
    _kind: str = "pipeline_aware"

    def __post_init__(self) -> None:
        # Compose: user messages + state keys
        user_provider = _make_user_only_provider()
        state_provider = _make_from_state_provider(self.keys) if self.keys else None

        async def _pipeline_aware_provider(ctx: Any) -> str:
            parts: list[str] = []
            user_ctx = await user_provider(ctx)
            if user_ctx:
                parts.append(user_ctx)
            if state_provider:
                state_ctx = await state_provider(ctx)
                if state_ctx:
                    parts.append(state_ctx)
            return "\n\n".join(parts)

        _set_frozen_fields(self, instruction_provider=_pipeline_aware_provider)

    @property
    def _reads_keys(self) -> frozenset[str]:
        return frozenset(self.keys)


@dataclass(frozen=True, slots=True)
class CSharedThread(CTransform):
    """Shared conversational thread for multi-agent loops.

    Every agent in the loop sees the full transcript of what all other
    agents said — like a group chat. No explicit ``.reads()`` / ``.writes()``
    wiring required.

    Under the hood: collects all agent events from the session and presents
    them as a formatted conversation transcript. Each agent sees who said
    what, enabling natural multi-agent discussion.

    Usage::

        loop = (
            (researcher >> writer >> critic)
            * until(lambda s: s.get("approved"), max=4)
        ).context(C.shared_thread())
    """

    include_contents: Literal["default", "none"] = "none"
    _kind: str = "shared_thread"

    def __post_init__(self) -> None:
        async def _shared_thread_provider(ctx: Any) -> str:
            events = list(ctx.session.events)
            agent_events = [
                e
                for e in events
                if getattr(e, "author", None) and getattr(e, "author", None) != "user" and getattr(e, "content", None)
            ]
            if not agent_events:
                return ""
            parts: list[str] = []
            for e in agent_events:
                author = getattr(e, "author", "unknown")
                content = getattr(e, "content", None)
                if content and hasattr(content, "parts"):
                    text_parts = [p.text for p in content.parts if hasattr(p, "text") and p.text]
                    if text_parts:
                        parts.append(f"[{author}]: {' '.join(text_parts)}")
            if not parts:
                return ""
            return "<shared_thread>\n" + "\n\n".join(parts) + "\n</shared_thread>"

        _set_frozen_fields(self, instruction_provider=_shared_thread_provider)


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
    def template(text: str) -> CTemplate:
        """Render a template string with {key} and {key?} state placeholders."""
        return CTemplate(template=text)

    @staticmethod
    def when(predicate: Callable | str, block: CTransform) -> CWhen:
        """Include block only if predicate is truthy at runtime.

        String predicate is a shortcut for state key check::

            C.when("has_history", C.rolling("conversation"))
            C.when(lambda s: s.get("debug"), C.notes("debug_scratchpad"))
        """
        return CWhen(predicate=predicate, block=block)

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

    # --- Phase D: Scratchpads + Sugar ---

    @staticmethod
    def notes(key: str = "default", *, format: str = "plain") -> CNotes:
        """Read structured notes from scratchpad at ``state["_notes_{key}"]``."""
        return CNotes(key=key, format=format)

    @staticmethod
    def write_notes(
        key: str = "default",
        *,
        strategy: str = "append",
        source_key: str | None = None,
    ) -> CWriteNotes:
        """Write to scratchpad after agent execution.

        Strategies: 'append', 'replace', 'merge', 'prepend'.
        """
        return CWriteNotes(
            key=key,
            strategy=strategy,
            source_key=source_key,
        )

    @staticmethod
    def rolling(
        n: int = 5,
        *,
        summarize: bool = False,
        model: str = _DEFAULT_MODEL,
    ) -> CRolling:
        """Rolling window with optional summarization of older turns.

        When ``summarize=True``, events before the window are
        summarized via LLM.
        """
        return CRolling(n=n, summarize=summarize, model=model)

    @staticmethod
    def from_agents_windowed(**agent_windows: int) -> CFromAgentsWindowed:
        """Per-agent selective windowing.

        Example::

            C.from_agents_windowed(researcher=1, critic=3)
        """
        return CFromAgentsWindowed(
            agent_windows=tuple(agent_windows.items()),
        )

    @staticmethod
    def user(*, strategy: str = "all") -> CUser:
        """Select user messages with a strategy.

        Strategies: 'all', 'first', 'last', 'bookend'.
        """
        return CUser(strategy=strategy)

    @staticmethod
    def manus_cascade(
        *,
        budget: int = 8000,
        model: str = _DEFAULT_MODEL,
    ) -> CManusCascade:
        """Manus-inspired progressive compression cascade.

        Applies: compact → dedup → summarize → truncate.
        """
        return CManusCascade(budget=budget, model=model)

    @staticmethod
    def pipeline_aware(*keys: str) -> CPipelineAware:
        """Topology-aware context: user messages + named state keys.

        Designed for pipeline agents that need the user's original
        message plus structured data from upstream agents, but should
        NOT see raw intermediate agent conversation history.

        Equivalent to ``C.user_only() | C.from_state(*keys)`` but
        with clearer intent and better contract checker support.

        Example::

            # classifier writes intent, handler sees user msg + intent
            classifier = Agent("classify").writes("intent")
            handler = Agent("handle").context(C.pipeline_aware("intent"))
            pipeline = classifier >> handler

        Args:
            *keys: State key names to include alongside user messages.
        """
        return CPipelineAware(keys=keys)

    @staticmethod
    def shared_thread() -> CSharedThread:
        """Shared conversational context for multi-agent loops.

        Every agent sees the full transcript of what all other agents said.
        Like a group chat — no explicit state wiring needed.

        Usage::

            loop = (
                (researcher >> writer >> critic)
                * until(lambda s: s.get("approved"), max=4)
            ).context(C.shared_thread())
        """
        return CSharedThread()

    @staticmethod
    def with_ui(surface_id: str | None = None) -> CTransform:
        """Include current UI surface state in agent context.

        Injects the A2UI data model for the given surface (or all surfaces)
        into the agent's context as a ``<ui_state>`` block.

        Args:
            surface_id: Optional surface to include. If ``None``, includes all.

        Usage::

            Agent("renderer").context(C.with_ui("dashboard"))
            Agent("updater").context(C.from_state("total") | C.with_ui())
        """
        key_pattern = f"_a2ui_data_{surface_id}" if surface_id else "_a2ui_data_"

        async def _ui_provider(ctx: Any) -> str:
            state = ctx.state
            ui_data: dict[str, Any] = {}
            for k, v in state.items():
                if isinstance(k, str) and k.startswith(key_pattern):
                    surface = k.replace("_a2ui_data_", "")
                    ui_data[surface] = v
            if not ui_data:
                return ""
            import json

            return f"<ui_state>\n{json.dumps(ui_data, indent=2)}\n</ui_state>"

        return CTransform(
            include_contents="default",
            instruction_provider=_ui_provider,
        )


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

    # Build a combined async instruction provider.
    #
    # Fast path: if ``developer_instruction`` is a static string, compile
    # its {key}/{key?} placeholders into a flat segment tuple once here
    # (build time). The hot per-turn path then walks the segments and
    # joins — no regex, no per-call closures. Missing required keys are
    # left as literal ``{key}`` to match the legacy re.sub behaviour.
    #
    # Slow path: if the instruction is a callable (dynamic), we resolve
    # it per turn but still use the module-level precompiled pattern.
    from adk_fluent._context_providers import _compile_template, _render_template

    raw_instruction = developer_instruction
    static_segments: tuple | None = None
    static_text: str | None = None
    if isinstance(raw_instruction, str):
        static_segments = _compile_template(raw_instruction)
        if static_segments is None:
            # No placeholders — instruction is fully static.
            static_text = raw_instruction

    async def _combined_provider(ctx: Any) -> str:
        # Step 1: resolve the developer instruction
        if static_text is not None:
            instruction = static_text
        elif static_segments is not None:
            instruction = _render_template(static_segments, ctx.state, raise_on_missing=False)
        elif raw_instruction is None:
            instruction = ""
        elif callable(raw_instruction):
            result = raw_instruction(ctx)
            # Handle async instruction providers
            import asyncio

            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                instruction = await result
            else:
                instruction = str(result)
            # Dynamic instructions may still contain placeholders.
            if instruction and "{" in instruction:
                dyn_segments = _compile_template(instruction)
                if dyn_segments is not None:
                    instruction = _render_template(dyn_segments, ctx.state, raise_on_missing=False)
        else:
            instruction = str(raw_instruction)

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
