"""Compute layer — infrastructure bindings for model, state, tools, and artifacts.

This package provides protocols and default implementations for the
compute concerns that are independent of the execution engine:

- ``ModelProvider``: LLM API abstraction
- ``StateStore``: Session/state persistence
- ``ToolRuntime``: Tool execution environment
- ``ArtifactStore``: Artifact persistence
- ``ComputeConfig``: Bundles compute resources for an execution

Usage::

    from adk_fluent.compute import ComputeConfig, InMemoryStateStore

    config = ComputeConfig(
        state_store=InMemoryStateStore(),
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adk_fluent.compute._protocol import (
    ArtifactStore,
    Chunk,
    GenerateConfig,
    GenerateResult,
    Message,
    ModelProvider,
    StateStore,
    ToolDef,
    ToolRuntime,
)
from adk_fluent.compute.memory import InMemoryArtifactStore, InMemoryStateStore

__all__ = [
    # Protocols
    "ModelProvider",
    "StateStore",
    "ToolRuntime",
    "ArtifactStore",
    # Data types
    "Message",
    "ToolDef",
    "GenerateConfig",
    "GenerateResult",
    "Chunk",
    # Config
    "ComputeConfig",
    # Default implementations
    "InMemoryStateStore",
    "InMemoryArtifactStore",
]


@dataclass
class ComputeConfig:
    """Bundles compute resources for an execution.

    When ``model_provider`` is a string (e.g., "gemini-2.5-flash"), the
    backend resolves it using its native model handling. When it's a
    ``ModelProvider`` instance, the backend uses it directly.

    This lets the ADK backend keep using ADK's model handling by default
    while other backends can use any provider.
    """

    model_provider: ModelProvider | str | None = None
    """LLM provider. String = model name resolved by backend. Instance = used directly."""

    state_store: StateStore | None = None
    """Session/state persistence. None = in-memory (ephemeral)."""

    tool_runtime: ToolRuntime | None = None
    """Tool execution environment. None = local execution."""

    artifact_store: ArtifactStore | None = None
    """Artifact persistence. None = in-memory (ephemeral)."""

    metadata: dict[str, Any] | None = None
    """Additional compute configuration."""
