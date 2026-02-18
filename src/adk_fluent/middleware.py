"""Middleware protocol and adapter for adk-fluent.

Middleware provides composable cross-cutting behavior (logging, retry,
cost tracking, etc.) that compiles to ADK BasePlugin instances.

Middleware is app-global (attached via ExecutionConfig). This is separate
from agent-level callbacks (stored per-agent in IR nodes).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from google.adk.plugins.base_plugin import BasePlugin

__all__ = [
    "Middleware",
    "_MiddlewarePlugin",
]


@runtime_checkable
class Middleware(Protocol):
    """A composable unit of cross-cutting behavior.

    All methods are optional -- implement only the hooks you need.
    Stack execution: in-order, first non-None return short-circuits.

    Lifecycle groups:
        Runner:  on_user_message, before_run, after_run, on_event
        Agent:   before_agent, after_agent
        Model:   before_model, after_model, on_model_error
        Tool:    before_tool, after_tool, on_tool_error
        Cleanup: close
    """

    @classmethod
    def __subclasshook__(cls, C):
        # All methods are optional -- any class conforms to Middleware.
        return True

    # --- Runner lifecycle ---

    async def on_user_message(self, ctx: Any, message: Any) -> Any:
        """Called when a user message is received."""
        return None

    async def before_run(self, ctx: Any) -> Any:
        """Called before execution starts."""
        return None

    async def after_run(self, ctx: Any) -> None:
        """Called after execution completes."""
        return None

    async def on_event(self, ctx: Any, event: Any) -> Any:
        """Called for each event during execution."""
        return None

    # --- Agent lifecycle ---

    async def before_agent(self, ctx: Any, agent_name: str) -> Any:
        """Called before an agent executes."""
        return None

    async def after_agent(self, ctx: Any, agent_name: str) -> Any:
        """Called after an agent executes."""
        return None

    # --- Model lifecycle ---

    async def before_model(self, ctx: Any, request: Any) -> Any:
        """Called before an LLM request."""
        return None

    async def after_model(self, ctx: Any, response: Any) -> Any:
        """Called after an LLM response."""
        return None

    async def on_model_error(self, ctx: Any, request: Any, error: Exception) -> Any:
        """Called when an LLM request fails."""
        return None

    # --- Tool lifecycle ---

    async def before_tool(self, ctx: Any, tool_name: str, args: dict) -> dict | None:
        """Called before a tool executes."""
        return None

    async def after_tool(
        self, ctx: Any, tool_name: str, args: dict, result: dict
    ) -> dict | None:
        """Called after a tool executes."""
        return None

    async def on_tool_error(
        self, ctx: Any, tool_name: str, args: dict, error: Exception
    ) -> dict | None:
        """Called when a tool execution fails."""
        return None

    # --- Cleanup ---

    async def close(self) -> None:
        """Called when the app shuts down."""
        pass


# ---------------------------------------------------------------------------
# Adapter: compile a middleware stack into a single ADK BasePlugin
# ---------------------------------------------------------------------------


class _MiddlewarePlugin(BasePlugin):
    """Compiles a middleware stack into a single ADK-compatible plugin.

    ADK execution order: plugins first -> agent callbacks second.
    This ensures middleware has priority over user-defined callbacks.

    Each callback iterates the stack in order. First non-None return
    short-circuits the remaining middleware (matching ADK semantics).
    Void hooks (after_run, close) always call all middleware.
    """

    def __init__(self, name: str, stack: list) -> None:
        super().__init__(name=name)
        self._stack = list(stack)

    # --- Helpers: iterate stack ---

    async def _run_stack(self, method_name: str, *args, **kwargs) -> Any:
        """Call *method_name* on each middleware in order.

        Short-circuits on the first non-None return.
        """
        for mw in self._stack:
            fn = getattr(mw, method_name, None)
            if fn is not None:
                result = await fn(*args, **kwargs)
                if result is not None:
                    return result
        return None

    async def _run_stack_void(self, method_name: str, *args, **kwargs) -> None:
        """Call *method_name* on ALL middleware (no short-circuit).

        Used for void hooks like ``after_run`` and ``close``.
        """
        for mw in self._stack:
            fn = getattr(mw, method_name, None)
            if fn is not None:
                await fn(*args, **kwargs)

    # --- Runner lifecycle ---

    async def on_user_message_callback(
        self, *, invocation_context, user_message
    ):
        return await self._run_stack(
            "on_user_message", invocation_context, user_message
        )

    async def before_run_callback(self, *, invocation_context):
        return await self._run_stack("before_run", invocation_context)

    async def after_run_callback(self, *, invocation_context):
        await self._run_stack_void("after_run", invocation_context)

    async def on_event_callback(self, *, invocation_context, event):
        return await self._run_stack("on_event", invocation_context, event)

    # --- Agent lifecycle ---

    async def before_agent_callback(self, *, agent, callback_context):
        return await self._run_stack(
            "before_agent",
            callback_context,
            getattr(agent, "name", str(agent)),
        )

    async def after_agent_callback(self, *, agent, callback_context):
        return await self._run_stack(
            "after_agent",
            callback_context,
            getattr(agent, "name", str(agent)),
        )

    # --- Model lifecycle ---

    async def before_model_callback(self, *, callback_context, llm_request):
        return await self._run_stack(
            "before_model", callback_context, llm_request
        )

    async def after_model_callback(self, *, callback_context, llm_response):
        return await self._run_stack(
            "after_model", callback_context, llm_response
        )

    async def on_model_error_callback(
        self, *, callback_context, llm_request, error
    ):
        return await self._run_stack(
            "on_model_error", callback_context, llm_request, error
        )

    # --- Tool lifecycle ---

    async def before_tool_callback(self, *, tool, tool_args, tool_context):
        return await self._run_stack(
            "before_tool",
            tool_context,
            getattr(tool, "name", str(tool)),
            tool_args,
        )

    async def after_tool_callback(
        self, *, tool, tool_args, tool_context, result
    ):
        return await self._run_stack(
            "after_tool",
            tool_context,
            getattr(tool, "name", str(tool)),
            tool_args,
            result,
        )

    async def on_tool_error_callback(
        self, *, tool, tool_args, tool_context, error
    ):
        return await self._run_stack(
            "on_tool_error",
            tool_context,
            getattr(tool, "name", str(tool)),
            tool_args,
            error,
        )

    # --- Cleanup ---

    async def close(self):
        await self._run_stack_void("close")
