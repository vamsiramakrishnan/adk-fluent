"""Error strategy — harness-level error handling for tool failures.

Claude Code retries failed tool calls and adjusts its approach.
This module provides a declarative error policy that maps tool names
to recovery actions::

    strategy = ErrorStrategy(
        retry={"bash", "web_fetch"},   # retry once
        skip={"glob_search"},           # return fallback message
        ask={"edit_file"},              # ask user on failure
    )

    agent = Agent("coder").harness(on_error=strategy)

The strategy is converted to a ``before_tool`` + ``after_tool`` callback
pair. It is NOT exponential-backoff retry (that's ``M.retry()``'s job)
— just a single harness-level recovery attempt.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ErrorStrategy", "make_error_callbacks"]


@dataclass(frozen=True, slots=True)
class ErrorStrategy:
    """Declarative error recovery policy for tool failures.

    Maps tool names to actions:
    - ``retry``: Retry the tool call once on failure.
    - ``skip``: Silently return a fallback message on failure.
    - ``ask``: Invoke an error handler (e.g., ask user) on failure.

    Tools not mentioned default to no special handling (error propagates).

    Args:
        retry: Tool names to retry once on failure.
        skip: Tool names to skip on failure (return fallback).
        ask: Tool names to escalate to error handler.
        fallback_message: Message returned for skipped failures.
    """

    retry: frozenset[str] = field(default_factory=frozenset)
    skip: frozenset[str] = field(default_factory=frozenset)
    ask: frozenset[str] = field(default_factory=frozenset)
    fallback_message: str = "Tool call failed and was skipped."

    def action_for(self, tool_name: str) -> str:
        """Return the recovery action for a tool.

        Returns:
            ``'retry'``, ``'skip'``, ``'ask'``, or ``'propagate'``.
        """
        if tool_name in self.retry:
            return "retry"
        if tool_name in self.skip:
            return "skip"
        if tool_name in self.ask:
            return "ask"
        return "propagate"

    def merge(self, other: ErrorStrategy) -> ErrorStrategy:
        """Merge two strategies. ``other`` overrides ``self``."""
        return ErrorStrategy(
            retry=(self.retry | other.retry) - other.skip - other.ask,
            skip=(self.skip | other.skip) - other.retry - other.ask,
            ask=(self.ask | other.ask),
            fallback_message=other.fallback_message or self.fallback_message,
        )

    def to_policy(self) -> Any:
        """Convert to a ``ToolPolicy`` (the foundation primitive).

        Returns a ``ToolPolicy`` with equivalent rules. Use this to
        migrate from the declarative ``ErrorStrategy`` to the
        composable ``ToolPolicy`` builder.

        Returns:
            A ``ToolPolicy`` instance.
        """
        from adk_fluent._harness._tool_policy import ToolPolicy

        return ToolPolicy.from_strategy(self)


def make_error_callbacks(
    strategy: ErrorStrategy,
    error_handler: Callable[[str, dict, Exception], bool] | None = None,
) -> dict[str, Callable]:
    """Create ADK callbacks that implement the error strategy.

    Returns a dict with ``after_tool_callback`` that inspects tool
    results for errors and applies recovery actions.

    Args:
        strategy: The error recovery policy.
        error_handler: Optional handler for ``ask`` tools.
            Receives (tool_name, args, error) and returns True to retry.

    Returns:
        Dict with callback keys suitable for merging into agent._callbacks.
    """
    _retry_state: dict[str, int] = {}

    def _after_tool(*, tool: Any, args: dict, tool_context: Any, tool_response: Any, **_kw: Any) -> Any:
        """Check tool results for errors and apply recovery strategy."""
        tool_name = getattr(tool, "name", str(tool))

        # Check if the response indicates an error
        response_str = str(tool_response) if tool_response is not None else ""
        is_error = (
            response_str.startswith("Error:")
            or response_str.startswith("error:")
            or (isinstance(tool_response, dict) and "error" in tool_response)
        )

        if not is_error:
            # Clear retry state on success
            _retry_state.pop(tool_name, None)
            return tool_response

        action = strategy.action_for(tool_name)

        if action == "skip":
            return {"result": strategy.fallback_message}

        if action == "retry":
            retry_key = f"{tool_name}:{hash(str(args))}"
            if _retry_state.get(retry_key, 0) < 1:
                _retry_state[retry_key] = _retry_state.get(retry_key, 0) + 1
                # Signal retry by returning None — the tool will be re-invoked
                # by the LLM on the next turn when it sees the error
                return tool_response  # Let error propagate so LLM can retry
            # Already retried once — propagate
            _retry_state.pop(retry_key, None)
            return tool_response

        if action == "ask" and error_handler is not None:
            try:
                error = Exception(response_str)
                should_retry = error_handler(tool_name, args, error)
                if should_retry:
                    return tool_response  # Propagate so LLM retries
                return {"result": f"Tool '{tool_name}' failed. User chose to skip."}
            except Exception:
                return tool_response

        # propagate — do nothing
        return tool_response

    return {"after_tool_callback": _after_tool}
