"""Enumerated types for adk-fluent APIs.

Replaces stringly-typed magic strings with type-safe StrEnums
while staying backwards-compatible (StrEnum inherits from str).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["SessionStrategy", "ExecutionMode"]


class SessionStrategy(StrEnum):
    """Session management strategy for :class:`~adk_fluent.stream.StreamRunner`."""

    PER_ITEM = "per_item"
    """Fresh session per stream item (stateless)."""

    SHARED = "shared"
    """Single persistent session (stateful, sequential context)."""

    KEYED = "keyed"
    """Session per key extracted by ``.session_key(fn)``."""


class ExecutionMode(StrEnum):
    """Current execution context for agents within adk-fluent."""

    PIPELINE = "pipeline"
    """Normal sequential pipeline execution (default)."""

    DISPATCHED = "dispatched"
    """Running inside a dispatched background task."""

    STREAM = "stream"
    """Running inside a StreamRunner processing loop."""
