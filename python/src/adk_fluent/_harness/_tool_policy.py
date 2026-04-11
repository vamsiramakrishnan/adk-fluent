"""Per-tool error recovery — the policy layer.

``M.retry()`` is agent-scoped: every tool in the agent gets the same
retry behavior. But a real harness needs per-tool granularity:
``read_file`` should retry (transient I/O), ``glob_search`` should
skip on failure (non-critical), ``bash`` should escalate (dangerous).

``ToolPolicy`` fills this gap. Each tool gets its own recovery rule.
Rules compile to a single ``after_tool`` callback — no middleware
overhead, just one dict lookup per tool call.

Design decisions:
    - **Fluent builder** — ``policy.retry("bash", 2).skip("glob")`` reads
      like a policy document, not code.
    - **Backoff support** — retry rules include optional exponential backoff,
      bridging the gap where ErrorStrategy had single-retry only.
    - **Composable** — ``policy_a.merge(policy_b)`` combines policies.
      ``ToolPolicy.from_strategy(error_strategy)`` bridges the old API.
    - **Event emission** — when wired to an EventBus, emits ErrorOccurred
      events on failure for unified observability.

Usage::

    policy = (
        H.tool_policy()
        .retry("bash", max_attempts=3, backoff=1.0)
        .retry("web_fetch", max_attempts=2)
        .skip("glob_search", fallback="No results found.")
        .ask("edit_file", handler=user_confirm)
    )

    agent = Agent("coder").after_tool(policy.after_tool_hook())
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = ["ToolPolicy", "ToolRule"]


@dataclass(frozen=True, slots=True)
class ToolRule:
    """Recovery rule for a single tool.

    Attributes:
        action: ``"retry"``, ``"skip"``, ``"ask"``, or ``"propagate"``.
        max_attempts: Max retry attempts (for retry action).
        backoff: Exponential backoff base in seconds (for retry).
        fallback: Fallback message (for skip action).
        handler: Escalation handler ``(tool_name, args, error) → bool``
            (for ask action). Returns True to retry.
    """

    action: str = "propagate"
    max_attempts: int = 1
    backoff: float = 0.0
    fallback: str = "Tool call failed and was skipped."
    handler: Callable[..., bool] | None = None


class ToolPolicy:
    """Per-tool error recovery policy.

    Each tool name maps to a ``ToolRule`` defining its recovery behavior.
    Unknown tools fall through to the default action.

    The policy compiles to a single ``after_tool`` callback that checks
    tool results for error indicators and applies the matching rule.
    """

    def __init__(self, *, default: str = "propagate") -> None:
        self._rules: dict[str, ToolRule] = {}
        self._default = default
        self._retry_state: dict[str, int] = {}
        self._event_bus: Any = None

    # -----------------------------------------------------------------
    # Fluent builder
    # -----------------------------------------------------------------

    def retry(
        self,
        tool_name: str,
        max_attempts: int = 2,
        backoff: float = 0.0,
    ) -> ToolPolicy:
        """Retry a tool on failure.

        Args:
            tool_name: Tool to apply retry to.
            max_attempts: Maximum retry attempts.
            backoff: Exponential backoff base (seconds). 0 = no delay.

        Returns:
            Self for chaining.
        """
        self._rules[tool_name] = ToolRule(
            action="retry",
            max_attempts=max_attempts,
            backoff=backoff,
        )
        return self

    def skip(
        self,
        tool_name: str,
        fallback: str = "Tool call failed and was skipped.",
    ) -> ToolPolicy:
        """Skip a tool on failure, returning a fallback message.

        Args:
            tool_name: Tool to skip on failure.
            fallback: Message returned instead of error.

        Returns:
            Self for chaining.
        """
        self._rules[tool_name] = ToolRule(action="skip", fallback=fallback)
        return self

    def ask(
        self,
        tool_name: str,
        handler: Callable[..., bool] | None = None,
    ) -> ToolPolicy:
        """Escalate a tool failure to a handler (e.g., user approval).

        Args:
            tool_name: Tool to escalate.
            handler: ``(tool_name, args, error) → bool``. Returns True
                to retry the tool.

        Returns:
            Self for chaining.
        """
        self._rules[tool_name] = ToolRule(action="ask", handler=handler)
        return self

    def propagate(self, tool_name: str) -> ToolPolicy:
        """Let a tool's error propagate unchanged.

        Args:
            tool_name: Tool to propagate errors for.

        Returns:
            Self for chaining.
        """
        self._rules[tool_name] = ToolRule(action="propagate")
        return self

    def default(self, action: str) -> ToolPolicy:
        """Set the default action for tools without explicit rules.

        Args:
            action: ``"retry"``, ``"skip"``, ``"ask"``, or ``"propagate"``.

        Returns:
            Self for chaining.
        """
        self._default = action
        return self

    def with_bus(self, bus: Any) -> ToolPolicy:
        """Wire an EventBus for error event emission.

        Args:
            bus: An EventBus instance.

        Returns:
            Self for chaining.
        """
        self._event_bus = bus
        return self

    # -----------------------------------------------------------------
    # Merge
    # -----------------------------------------------------------------

    def merge(self, other: ToolPolicy) -> ToolPolicy:
        """Merge another policy. ``other`` wins on conflicts.

        Args:
            other: Policy to merge from.

        Returns:
            New merged ToolPolicy.
        """
        merged = ToolPolicy(default=other._default or self._default)
        merged._rules.update(self._rules)
        merged._rules.update(other._rules)
        merged._event_bus = other._event_bus or self._event_bus
        return merged

    # -----------------------------------------------------------------
    # ADK callback
    # -----------------------------------------------------------------

    def after_tool_hook(self) -> Callable:
        """Create an ``after_tool`` callback implementing this policy.

        The callback inspects tool results for error indicators
        (``"Error:"`` prefix or ``{"error": ...}`` dict) and applies
        the matching rule.

        Returns:
            ADK-compatible after_tool callback.
        """
        policy = self

        def _after_tool(
            callback_context: Any,
            tool: Any,
            args: dict,
            tool_context: Any,
            tool_response: Any,
        ) -> Any:
            tool_name = getattr(tool, "name", str(tool))

            # Check for error indicators
            response_str = str(tool_response) if tool_response is not None else ""
            is_error = (
                response_str.startswith("Error:")
                or response_str.startswith("error:")
                or (isinstance(tool_response, dict) and "error" in tool_response)
            )

            if not is_error:
                policy._retry_state.pop(tool_name, None)
                return tool_response

            # Look up rule
            rule = policy._rules.get(tool_name)
            if rule is None:
                if policy._default == "skip":
                    return {"result": "Tool call failed and was skipped."}
                return tool_response  # propagate

            # Emit error event if bus is wired
            if policy._event_bus is not None:
                from adk_fluent._harness._events import ErrorOccurred

                policy._event_bus.emit(ErrorOccurred(tool_name=tool_name, error=response_str[:200]))

            if rule.action == "skip":
                return {"result": rule.fallback}

            if rule.action == "retry":
                retry_key = f"{tool_name}:{hash(str(args))}"
                attempts = policy._retry_state.get(retry_key, 0)
                if attempts < rule.max_attempts:
                    policy._retry_state[retry_key] = attempts + 1
                    if rule.backoff > 0:
                        delay = rule.backoff * (2**attempts)
                        time.sleep(min(delay, 30))
                    return tool_response  # propagate so LLM retries
                policy._retry_state.pop(retry_key, None)
                return tool_response

            if rule.action == "ask" and rule.handler is not None:
                try:
                    error = Exception(response_str)
                    should_retry = rule.handler(tool_name, args, error)
                    if should_retry:
                        return tool_response
                    return {"result": f"Tool '{tool_name}' failed. User chose to skip."}
                except Exception:
                    return tool_response

            return tool_response

        return _after_tool

    # -----------------------------------------------------------------
    # Bridge from legacy ErrorStrategy
    # -----------------------------------------------------------------

    @classmethod
    def from_strategy(cls, strategy: Any) -> ToolPolicy:
        """Create a ToolPolicy from a legacy ErrorStrategy.

        Args:
            strategy: An ErrorStrategy instance.

        Returns:
            Equivalent ToolPolicy.
        """
        policy = cls()
        for name in getattr(strategy, "retry", ()):
            policy.retry(name, max_attempts=1)
        for name in getattr(strategy, "skip", ()):
            policy.skip(name, fallback=getattr(strategy, "fallback_message", ""))
        for name in getattr(strategy, "ask", ()):
            policy.ask(name)
        return policy

    # -----------------------------------------------------------------
    # Introspection
    # -----------------------------------------------------------------

    def rule_for(self, tool_name: str) -> ToolRule:
        """Get the rule for a tool (or the default)."""
        return self._rules.get(tool_name, ToolRule(action=self._default))

    @property
    def size(self) -> int:
        """Number of explicit tool rules."""
        return len(self._rules)

    def __repr__(self) -> str:
        rules = ", ".join(f"{k}={v.action}" for k, v in self._rules.items())
        return f"ToolPolicy({rules}, default={self._default})"
