"""Compile layer — validates, optimizes, and lowers IR to backend-specific runnables.

This package formalizes the compile step as a distinct layer between IR
construction (builders) and execution (backends). It provides:

- ``CompilationResult``: structured output of the compile step
- ``EngineCapabilities``: what a backend supports
- ``compile()``: the main entry point that validates, optimizes, and lowers IR
- Optimization passes in ``compile.passes``

Usage::

    from adk_fluent.compile import compile

    ir = agent_builder.to_ir()
    result = compile(ir, backend="adk")
    # result.runnable is a backend-specific object (e.g., ADK App)
    # result.capabilities describes what the backend supports
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adk_fluent._ir import ExecutionConfig
    from adk_fluent._ir_generated import FullNode

__all__ = [
    "CompilationResult",
    "EngineCapabilities",
    "compile",
]


@dataclass(frozen=True)
class EngineCapabilities:
    """Declares what an execution engine supports.

    Used by the runtime layer to decide which code paths are available
    and to give clear errors when a feature is requested that the engine
    does not support.
    """

    streaming: bool = True
    parallel: bool = True
    durable: bool = False
    replay: bool = False
    checkpointing: bool = False
    signals: bool = False
    dispatch_join: bool = True
    distributed: bool = False


@dataclass
class CompilationResult:
    """Structured output of the compile step.

    Carries the backend-specific runnable along with metadata for
    introspection, diagnostics, and runtime decisions.
    """

    ir: Any
    """Original IR tree (for introspection and diagnostics)."""

    runnable: Any
    """Backend-specific executable (e.g., ADK App, Temporal workflow class)."""

    backend_name: str
    """Name of the backend that produced this result."""

    capabilities: EngineCapabilities
    """What the backend supports."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Backend-specific metadata (e.g., task queue, worker config)."""

    warnings: list[str] = field(default_factory=list)
    """Non-fatal compilation warnings."""


def compile(
    ir: FullNode,
    *,
    backend: str | Any = "adk",
    config: ExecutionConfig | None = None,
    optimize: bool = True,
) -> CompilationResult:
    """Compile an IR tree to a backend-specific runnable.

    Args:
        ir: Root IR node of the agent tree.
        backend: Backend name (string) or Backend instance.
        config: Optional execution configuration.
        optimize: Whether to run optimization passes before lowering.

    Returns:
        A ``CompilationResult`` containing the runnable and metadata.
    """
    from adk_fluent.backends import get_backend

    if optimize:
        from adk_fluent.compile import passes

        ir = passes.run_passes(ir)

    # Resolve backend
    if isinstance(backend, str):
        backend_impl = get_backend(backend)
    else:
        backend_impl = backend

    # Compile
    runnable = backend_impl.compile(ir, config)

    # Extract capabilities
    capabilities = getattr(backend_impl, "capabilities", EngineCapabilities())

    # Extract name
    backend_name = getattr(backend_impl, "name", type(backend_impl).__name__)

    return CompilationResult(
        ir=ir,
        runnable=runnable,
        backend_name=backend_name,
        capabilities=capabilities,
    )
