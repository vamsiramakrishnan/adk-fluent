"""Global configuration for adk-fluent engine and compute defaults.

Usage::

    import adk_fluent
    adk_fluent.configure(engine="temporal", engine_config={"client": client})

    # All agents now use Temporal by default
    result = await Agent("x").instruct("...").ask_async("hello")

    # Reset to defaults
    adk_fluent.reset_config()
"""

from __future__ import annotations

from typing import Any

__all__ = ["configure", "reset_config", "get_config"]

_GLOBAL: dict[str, Any] = {}


def configure(
    *,
    engine: str | None = None,
    engine_config: dict[str, Any] | None = None,
    compute: Any = None,
) -> None:
    """Set global defaults for engine and compute.

    Args:
        engine: Default backend name (e.g., "adk", "temporal", "asyncio").
        engine_config: Keyword arguments forwarded to the backend factory.
        compute: A ``ComputeConfig`` instance for model/state/tool defaults.
    """
    if engine is not None:
        _GLOBAL["engine"] = engine
    if engine_config is not None:
        _GLOBAL["engine_config"] = engine_config
    if compute is not None:
        _GLOBAL["compute"] = compute


def get_config() -> dict[str, Any]:
    """Return a copy of the current global configuration."""
    return dict(_GLOBAL)


def reset_config() -> None:
    """Reset global configuration to defaults."""
    _GLOBAL.clear()
