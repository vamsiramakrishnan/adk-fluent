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
            builder.instruct(fn.__doc__.strip())
        for k, v in kwargs.items():
            method = getattr(builder, k, None)
            if method and callable(method):
                method(v)
            else:
                builder._config[k] = v

        # Override .tool to work as decorator (returns function, not self)
        original_tool_append = builder._lists["tools"].append

        def tool_decorator(tool_fn: Callable) -> Callable:
            original_tool_append(tool_fn)
            return tool_fn

        builder.tool = tool_decorator

        # Add .on(event_name) decorator factory
        def on(event_name: str) -> Callable:
            cb_field = builder._CALLBACK_ALIASES.get(event_name, event_name)

            def event_decorator(callback_fn: Callable) -> Callable:
                builder._callbacks[cb_field].append(callback_fn)
                return callback_fn

            return event_decorator

        builder.on = on

        return builder

    return decorator
