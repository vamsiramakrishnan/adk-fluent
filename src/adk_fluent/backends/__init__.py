"""Backend protocol, registry, and implementations for adk-fluent IR compilation.

The backend registry allows multiple execution engines to coexist.
ADK is registered by default. Other backends register themselves when
their extras are installed (e.g., ``pip install adk-fluent[temporal]``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from adk_fluent.backends._protocol import Backend, final_text

__all__ = [
    "Backend",
    "final_text",
    "register_backend",
    "get_backend",
    "available_backends",
]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_backend(name: str, factory: Callable[..., Any]) -> None:
    """Register a backend factory by name.

    Args:
        name: Short identifier (e.g., "adk", "temporal", "asyncio").
        factory: Callable that returns a Backend instance. Called with
                 keyword arguments from ``get_backend(name, **kwargs)``.
    """
    _REGISTRY[name] = factory


def get_backend(name: str, **kwargs: Any) -> Any:
    """Retrieve and instantiate a backend by name.

    Args:
        name: Registered backend name.
        **kwargs: Forwarded to the backend factory.

    Returns:
        A Backend instance.

    Raises:
        KeyError: If no backend is registered under ``name``.
    """
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(
            f"No backend registered as {name!r}. "
            f"Available backends: {available}. "
            f"Install extras for additional backends "
            f"(e.g., pip install adk-fluent[temporal])."
        )
    return _REGISTRY[name](**kwargs)


def available_backends() -> list[str]:
    """Return names of all registered backends."""
    return sorted(_REGISTRY)


# ---------------------------------------------------------------------------
# Auto-register the ADK backend
# ---------------------------------------------------------------------------


def _adk_factory(**kwargs: Any) -> Any:
    from adk_fluent.backends.adk import ADKBackend

    return ADKBackend(**kwargs)


register_backend("adk", _adk_factory)
