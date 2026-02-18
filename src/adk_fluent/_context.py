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

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

__all__ = ["C", "CTransform", "CComposite", "CPipe", "_compile_context_spec"]


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

    def _as_list(self) -> tuple[CTransform, ...]:
        return self.blocks


@dataclass(frozen=True)
class CPipe(CTransform):
    """Pipe transform: source feeds into transform (via | operator)."""

    source: CTransform | None = None
    transform: CTransform | None = None


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
# BUDGET primitives
# ======================================================================


@dataclass(frozen=True)
class CBudget(CTransform):
    """Token budget constraint for context."""

    max_tokens: int = 8000
    overflow: str = "truncate_oldest"
    _kind: str = "budget"


@dataclass(frozen=True)
class CPriority(CTransform):
    """Priority tier for context ordering (lower = higher priority)."""

    tier: int = 2
    _kind: str = "priority"


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
    def budget(*, max_tokens: int = 8000, overflow: str = "truncate_oldest") -> CBudget:
        """Set token budget constraint for context."""
        return CBudget(max_tokens=max_tokens, overflow=overflow)

    @staticmethod
    def priority(*, tier: int = 2) -> CPriority:
        """Set priority tier for context ordering."""
        return CPriority(tier=tier)


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
