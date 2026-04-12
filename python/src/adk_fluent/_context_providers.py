"""Context provider factories — private implementation module.

This module contains the async InstructionProvider factory functions used
by the CTransform descriptors in _context.py. Extracted to keep the
public API module focused on the declarative surface.

Do NOT import from this module directly. Use C.xxx() factories instead.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from adk_fluent._session_index import get_session_index

if TYPE_CHECKING:
    from adk_fluent._context import CTransform

_DEFAULT_MODEL = "gemini-2.5-flash"
_log = logging.getLogger(__name__)


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
        idx = get_session_index(ctx.session)
        window_events = idx.window_tail(n)
        if not window_events:
            return ""
        return _format_events_as_context(window_events)

    _provider.__name__ = f"window_{n}"
    return _provider


def _make_user_only_provider() -> Callable:
    """Create an async provider that includes only user messages."""

    async def _provider(ctx: Any) -> str:
        idx = get_session_index(ctx.session)
        return _format_events_as_context(idx.user_events())

    _provider.__name__ = "user_only"
    return _provider


def _make_from_agents_provider(agent_names: tuple[str, ...]) -> Callable:
    """Create an async provider including user + named agent outputs."""
    names_set = set(agent_names) | {"user"}

    async def _provider(ctx: Any) -> str:
        idx = get_session_index(ctx.session)
        return _format_events_as_context(idx.events_by_authors(names_set))

    _provider.__name__ = f"from_agents_{'_'.join(agent_names)}"
    return _provider


def _make_exclude_agents_provider(agent_names: tuple[str, ...]) -> Callable:
    """Create an async provider excluding named agents."""
    names_set = set(agent_names)

    async def _provider(ctx: Any) -> str:
        idx = get_session_index(ctx.session)
        return _format_events_as_context(idx.events_excluding_authors(names_set))

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
        from google import genai  # type: ignore[attr-defined]

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


def _make_when_provider(predicate: Any, block: CTransform | None) -> Callable:
    """Create a provider that conditionally includes a block's output."""
    from adk_fluent._predicate_utils import evaluate_predicate

    async def _provider(ctx: Any) -> str:
        state = dict(ctx.state) if hasattr(ctx, "state") else {}
        if not evaluate_predicate(predicate, state):
            return ""
        if block is None or block.instruction_provider is None:
            return ""
        return await block.instruction_provider(ctx)

    _provider.__name__ = "when"
    return _provider


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
            f'Score each event below from 0 to 10 for relevance to this query: "{resolved_query}"\n\n'
            + "\n".join(numbered)
            + '\n\nRespond with a JSON array of objects: [{"index": <int>, "score": <float>}, ...]'
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
            f'Respond with a JSON array of strings: ["fact1", "fact2", ...]'
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
# Phase D provider factories (Scratchpads + Sugar)
# ======================================================================


def _make_notes_provider(key: str, fmt: str) -> Callable:
    """Create a provider that reads structured notes from session state."""
    state_key = f"_notes_{key}"

    async def _provider(ctx: Any) -> str:
        raw = ctx.state.get(state_key)
        if raw is None:
            return ""

        # Parse stored notes (JSON list of strings or plain string)
        entries: list[str] = []
        if isinstance(raw, list):
            entries = [str(e) for e in raw]
        elif isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    entries = [str(e) for e in parsed]
                else:
                    entries = [raw]
            except (json.JSONDecodeError, ValueError):
                entries = [raw]
        else:
            entries = [str(raw)]

        if not entries:
            return ""

        # Format based on requested style
        if fmt == "checklist":
            lines = [f"- [ ] {e}" for e in entries]
        elif fmt == "numbered":
            lines = [f"{i + 1}. {e}" for i, e in enumerate(entries)]
        else:  # "plain"
            lines = entries

        return f"[Notes: {key}]\n" + "\n".join(lines)

    _provider.__name__ = f"notes_{key}"
    return _provider


def _make_rolling_provider(n: int, summarize: bool, model: str) -> Callable:
    """Create a provider for rolling window with optional summarization."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""

        # Find user turn boundaries
        user_indices = [i for i, e in enumerate(events) if getattr(e, "author", None) == "user"]

        # Window: last N turn-pairs
        start_indices = user_indices[-n:] if len(user_indices) >= n else user_indices
        window_start = start_indices[0] if start_indices else 0
        window_events = events[window_start:]
        window_text = _format_events_as_context(window_events)

        if not summarize or window_start == 0:
            return window_text

        # Summarize events before the window
        older_events = events[:window_start]
        if not older_events:
            return window_text

        fp = _fingerprint_events(older_events)
        cache_key = f"temp:_rolling_summary_{n}_{fp}"
        cached = ctx.state.get(cache_key)
        if cached is not None:
            summary = str(cached)
        else:
            older_text = _format_events_as_context(older_events)
            try:
                summary = await _call_llm(
                    model,
                    "Summarize this earlier conversation concisely, "
                    "preserving key facts and decisions:\n\n" + older_text,
                )
            except Exception as e:
                _log.warning("C.rolling() summarize failed: %s", e)
                summary = older_text
            ctx.state[cache_key] = summary

        return f"<earlier_context_summary>\n{summary}\n</earlier_context_summary>\n\n{window_text}"

    _provider.__name__ = f"rolling_{n}"
    return _provider


def _make_from_agents_windowed_provider(
    agent_windows: tuple[tuple[str, int], ...],
) -> Callable:
    """Create a provider that windows each agent's events independently."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        if not events:
            return ""

        parts: list[str] = []
        for agent_name, window_size in agent_windows:
            # Filter events by this agent
            agent_events = [e for e in events if getattr(e, "author", None) == agent_name]
            # Take the last window_size events
            if window_size > 0:
                agent_events = agent_events[-window_size:]
            if agent_events:
                text = _format_events_as_context(agent_events)
                parts.append(text)

        # Also include user messages
        user_events = [e for e in events if getattr(e, "author", None) == "user"]
        if user_events:
            parts.insert(0, _format_events_as_context(user_events))

        return "\n".join(parts)

    _provider.__name__ = "from_agents_windowed"
    return _provider


def _make_user_strategy_provider(strategy: str) -> Callable:
    """Create a provider that selects user messages with a strategy."""

    async def _provider(ctx: Any) -> str:
        events = list(ctx.session.events)
        user_events = [e for e in events if getattr(e, "author", None) == "user"]
        if not user_events:
            return ""

        if strategy == "first":
            selected = user_events[:1]
        elif strategy == "last":
            selected = user_events[-1:]
        elif strategy == "bookend":
            if len(user_events) <= 2:
                selected = user_events
            else:
                selected = [user_events[0], user_events[-1]]
        else:  # "all"
            selected = user_events

        return _format_events_as_context(selected)

    _provider.__name__ = f"user_{strategy}"
    return _provider


def make_write_notes_callback(
    key: str,
    strategy: str,
    source_key: str | None,
) -> Callable:
    """Create a post-agent callback that writes notes to session state.

    This is the runtime implementation for ``CWriteNotes``. It is called
    as an ``after_agent_callback`` on the target agent.
    """
    state_key = f"_notes_{key}"

    async def _after_agent(callback_context: Any) -> None:
        state = callback_context.state
        if hasattr(state, "__getitem__"):
            pass  # dict-like
        else:
            return

        # Get new content: from source_key or from the agent's last output
        new_content: str | None = None
        if source_key is not None:
            new_content = state.get(source_key)
        else:
            # Try to read from the agent's output_key or last event text
            for s_key in list(state.keys()):
                if s_key.startswith("temp:"):
                    continue
                # Convention: agent output is often in output_key
            # Fall back to reading the most recent agent event
            session = getattr(callback_context, "session", None)
            if session is not None:
                events = getattr(session, "events", [])
                for e in reversed(list(events)):
                    author = getattr(e, "author", None)
                    if author and author != "user":
                        text = _extract_event_text(e)
                        if text:
                            new_content = text
                            break

        if not new_content:
            return

        existing = state.get(state_key)

        if strategy == "replace":
            state[state_key] = json.dumps([new_content])
        elif strategy == "prepend":
            entries = _parse_notes_entries(existing)
            entries.insert(0, new_content)
            state[state_key] = json.dumps(entries)
        elif strategy == "merge":
            entries = _parse_notes_entries(existing)
            if new_content not in entries:
                entries.append(new_content)
            state[state_key] = json.dumps(entries)
        else:  # "append" (default)
            entries = _parse_notes_entries(existing)
            entries.append(new_content)
            state[state_key] = json.dumps(entries)

    _after_agent.__name__ = f"write_notes_{key}"
    return _after_agent


def _parse_notes_entries(raw: Any) -> list[str]:
    """Parse existing notes from state into a list of strings."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(e) for e in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(e) for e in parsed]
            return [raw]
        except (json.JSONDecodeError, ValueError):
            return [raw]
    return [str(raw)]


def consolidate_notes(
    ctx: Any,
    key: str,
    max_entries: int | None = None,
) -> None:
    """Consolidate notes by deduplicating and optionally capping entries.

    Call this in a callback or tool to manage note lifecycle.
    """
    state = ctx.state if hasattr(ctx, "state") else ctx
    state_key = f"_notes_{key}"
    entries = _parse_notes_entries(state.get(state_key))
    # Deduplicate preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for entry in entries:
        if entry not in seen:
            seen.add(entry)
            deduped.append(entry)
    # Cap if requested
    if max_entries is not None and len(deduped) > max_entries:
        deduped = deduped[-max_entries:]
    state[state_key] = json.dumps(deduped)


def clear_notes(ctx: Any, key: str) -> None:
    """Clear all notes for a given key."""
    state = ctx.state if hasattr(ctx, "state") else ctx
    state_key = f"_notes_{key}"
    state[state_key] = json.dumps([])


# ======================================================================
# C — public API namespace
# ======================================================================
