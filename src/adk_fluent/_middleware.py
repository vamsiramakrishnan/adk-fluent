"""M module -- fluent middleware composition surface.

Consistent with P (prompts), C (context), S (state transforms).
M is an expression DSL for *how* to observe and control execution.

Custom middleware remains class-based (the ``Middleware`` protocol is
the mechanism). ``M`` is the DX surface -- it wraps protocol instances
in a composable chain and provides factories for built-ins.

Usage::

    from adk_fluent import M

    # Built-in composition
    pipeline.middleware(M.retry(3) | M.log() | M.topology_log())

    # Scoped middleware
    pipeline.middleware(M.scope("analyst", M.cost()))

    # Conditional
    pipeline.middleware(M.when("stream", M.latency()))

    # Single-hook shortcut
    pipeline.middleware(M.on_loop(lambda ctx, name, i: print(f"Loop {name} #{i}")))

    # Mix with custom classes
    pipeline.middleware(M.retry(3) | MyAudit() | M.dispatch_log())
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["M", "MComposite"]


class MComposite:
    """Composable middleware chain. The result of any ``M.xxx()`` call.

    Supports ``|`` for composition::

        M.retry(3) | M.log() | MyMiddleware()
    """

    def __init__(self, stack: list[Any] | None = None, *, kind: str = "middleware_chain"):
        self._stack: list[Any] = list(stack or [])
        self.__kind = kind

    # ------------------------------------------------------------------
    # NamespaceSpec protocol
    # ------------------------------------------------------------------

    @property
    def _kind(self) -> str:
        """Discriminator tag for IR serialization."""
        return self.__kind

    def _as_list(self) -> tuple[Any, ...]:
        """Flatten for composite building."""
        return tuple(self._stack)

    @property
    def _reads_keys(self) -> frozenset[str] | None:
        """Middleware is opaque to state — always returns ``None``."""
        return None

    @property
    def _writes_keys(self) -> frozenset[str] | None:
        """Middleware is opaque to state — always returns ``None``."""
        return None

    # ------------------------------------------------------------------
    # Composition: | (chain)
    # ------------------------------------------------------------------

    def __or__(self, other: MComposite | Any) -> MComposite:
        """M.retry(3) | M.log() | MyMiddleware()"""
        if isinstance(other, MComposite):
            return MComposite(self._stack + other._stack)
        return MComposite(self._stack + [other])

    def __ror__(self, other: Any) -> MComposite:
        """MyMiddleware() | M.retry(3)"""
        if isinstance(other, MComposite):
            return MComposite(other._stack + self._stack)
        return MComposite([other] + self._stack)

    def to_stack(self) -> list[Any]:
        """Flatten to list of protocol-level middleware instances."""
        return list(self._stack)

    def __repr__(self) -> str:
        names = [type(m).__name__ for m in self._stack]
        return f"MComposite([{', '.join(names)}])"

    def __len__(self) -> int:
        return len(self._stack)


class M:
    """Fluent middleware composition. Consistent with P, C, S modules.

    Factory methods return ``MComposite`` instances that compose with ``|``.
    """

    # --- Built-in factories ---

    @staticmethod
    def retry(max_attempts: int = 3, backoff: float = 1.0) -> MComposite:
        """Retry middleware with exponential backoff."""
        from adk_fluent.middleware import RetryMiddleware

        return MComposite([RetryMiddleware(max_attempts=max_attempts, backoff_base=backoff)], kind="retry")

    @staticmethod
    def log() -> MComposite:
        """Structured event logging middleware."""
        from adk_fluent.middleware import StructuredLogMiddleware

        return MComposite([StructuredLogMiddleware()], kind="log")

    @staticmethod
    def cost() -> MComposite:
        """Token usage tracking middleware."""
        from adk_fluent.middleware import CostTracker

        return MComposite([CostTracker()], kind="cost")

    @staticmethod
    def latency() -> MComposite:
        """Per-agent latency tracking middleware."""
        from adk_fluent.middleware import LatencyMiddleware

        return MComposite([LatencyMiddleware()], kind="latency")

    @staticmethod
    def topology_log() -> MComposite:
        """Topology event logging (loops, fanout, routes, fallbacks, timeouts)."""
        from adk_fluent.middleware import TopologyLogMiddleware

        return MComposite([TopologyLogMiddleware()], kind="topology_log")

    @staticmethod
    def dispatch_log() -> MComposite:
        """Dispatch/join lifecycle logging."""
        from adk_fluent.middleware import DispatchLogMiddleware

        return MComposite([DispatchLogMiddleware()], kind="dispatch_log")

    # --- Composition operators ---

    @staticmethod
    def scope(agents: str | tuple[str, ...], mw: MComposite | Any) -> MComposite:
        """Restrict middleware to specific agents.

        Usage::

            M.scope("writer", M.cost())
            M.scope(("writer", "reviewer"), M.log())
        """
        from adk_fluent.middleware import _ScopedMiddleware

        stack = mw.to_stack() if isinstance(mw, MComposite) else [mw]
        scoped = [_ScopedMiddleware(agents, m) for m in stack]
        return MComposite(scoped)

    @staticmethod
    def when(condition: str | Callable[[], bool] | type, mw: MComposite | Any) -> MComposite:
        """Conditionally apply middleware.

        ``condition`` can be:
            - String shortcut: ``"stream"``, ``"dispatched"``, ``"pipeline"``
              matching ExecutionMode.
            - Callable returning bool, evaluated at hook invocation time.
            - ``PredicateSchema`` subclass, evaluated against session state
              at hook invocation time.

        Usage::

            M.when("stream", M.latency())
            M.when(lambda: is_debug(), M.log())
            M.when(PremiumOnly, M.scope("writer", M.cost()))
        """
        from adk_fluent.middleware import _ConditionalMiddleware

        stack = mw.to_stack() if isinstance(mw, MComposite) else [mw]
        wrapped = [_ConditionalMiddleware(condition, m) for m in stack]
        return MComposite(wrapped)

    # --- Single-hook shortcuts ---

    @staticmethod
    def before_agent(fn: Callable) -> MComposite:
        """Single-hook middleware: fires before each agent."""
        from adk_fluent.middleware import _SingleHookMiddleware

        return MComposite([_SingleHookMiddleware("before_agent", fn)])

    @staticmethod
    def after_agent(fn: Callable) -> MComposite:
        """Single-hook middleware: fires after each agent."""
        from adk_fluent.middleware import _SingleHookMiddleware

        return MComposite([_SingleHookMiddleware("after_agent", fn)])

    @staticmethod
    def before_model(fn: Callable) -> MComposite:
        """Single-hook middleware: fires before each LLM request."""
        from adk_fluent.middleware import _SingleHookMiddleware

        return MComposite([_SingleHookMiddleware("before_model", fn)])

    @staticmethod
    def after_model(fn: Callable) -> MComposite:
        """Single-hook middleware: fires after each LLM response."""
        from adk_fluent.middleware import _SingleHookMiddleware

        return MComposite([_SingleHookMiddleware("after_model", fn)])

    @staticmethod
    def on_loop(fn: Callable) -> MComposite:
        """Single-hook middleware: fires at each loop iteration."""
        from adk_fluent.middleware import _SingleHookMiddleware

        return MComposite([_SingleHookMiddleware("on_loop_iteration", fn)])

    @staticmethod
    def on_timeout(fn: Callable) -> MComposite:
        """Single-hook middleware: fires when a timeout completes/expires."""
        from adk_fluent.middleware import _SingleHookMiddleware

        return MComposite([_SingleHookMiddleware("on_timeout", fn)])

    @staticmethod
    def on_route(fn: Callable) -> MComposite:
        """Single-hook middleware: fires when a route selects an agent."""
        from adk_fluent.middleware import _SingleHookMiddleware

        return MComposite([_SingleHookMiddleware("on_route_selected", fn)])

    @staticmethod
    def on_fallback(fn: Callable) -> MComposite:
        """Single-hook middleware: fires at each fallback attempt."""
        from adk_fluent.middleware import _SingleHookMiddleware

        return MComposite([_SingleHookMiddleware("on_fallback_attempt", fn)])
