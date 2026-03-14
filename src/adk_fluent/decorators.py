"""Decorator syntax for defining agents -- inspired by FastAPI's @app.route."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["agent"]


def agent(name: str, **kwargs: Any) -> Callable:
    """Decorator that creates an Agent builder from a function.

    The decorated function's docstring becomes the agent's instruction.
    """

    def decorator(fn: Callable) -> Any:
        from adk_fluent.agent import Agent

        builder = Agent(name)
        if fn.__doc__:
            builder = builder.instruct(fn.__doc__.strip())
        for k, v in kwargs.items():
            method = getattr(builder, k, None)
            if method and callable(method):
                builder = method(v) or builder
            else:
                # Fallback: use with_raw_config for unknown kwargs
                builder = builder.with_raw_config(**{k: v})

        # Capture the original .tool method before overriding
        _original_tool = builder.tool.__func__ if hasattr(builder.tool, '__func__') else None

        # Override .tool to work as decorator (returns function, not self)
        def tool_decorator(tool_fn: Callable) -> Callable:
            # Append to the tools list via the internal list
            builder._lists["tools"].append(tool_fn)
            return tool_fn

        builder.tool = tool_decorator  # type: ignore[reportAttributeAccessIssue]  # decorator override

        # Add .on(event_name) decorator factory
        def on(event_name: str) -> Callable:
            def event_decorator(callback_fn: Callable) -> Callable:
                cb_field = builder._CALLBACK_ALIASES.get(event_name, event_name)
                builder._callbacks[cb_field].append(callback_fn)
                return callback_fn

            return event_decorator

        builder.on = on  # type: ignore[reportAttributeAccessIssue]  # decorator override

        return builder

    return decorator
