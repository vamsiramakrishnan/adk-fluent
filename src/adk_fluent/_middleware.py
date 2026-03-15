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

    # ------------------------------------------------------------------
    # Expanded built-in middleware factories
    # ------------------------------------------------------------------

    @staticmethod
    def circuit_breaker(threshold: int = 5, reset_after: float = 60) -> MComposite:
        """Circuit breaker — trips open after N consecutive model errors."""
        from adk_fluent.middleware import CircuitBreakerMiddleware

        return MComposite(
            [CircuitBreakerMiddleware(threshold=threshold, reset_after=reset_after)],
            kind="circuit_breaker",
        )

    @staticmethod
    def timeout(seconds: float = 30) -> MComposite:
        """Per-agent execution timeout."""
        from adk_fluent.middleware import TimeoutMiddleware

        return MComposite([TimeoutMiddleware(seconds=seconds)], kind="timeout")

    @staticmethod
    def cache(ttl: float = 300, key_fn: Any = None) -> MComposite:
        """Cache LLM responses keyed by request content."""
        from adk_fluent.middleware import ModelCacheMiddleware

        return MComposite([ModelCacheMiddleware(ttl=ttl, key_fn=key_fn)], kind="cache")

    @staticmethod
    def fallback_model(model: str = "gemini-2.0-flash") -> MComposite:
        """Auto-downgrade to fallback model on primary model failure."""
        from adk_fluent.middleware import FallbackModelMiddleware

        return MComposite([FallbackModelMiddleware(fallback_model=model)], kind="fallback_model")

    @staticmethod
    def dedup(window: int = 10) -> MComposite:
        """Suppress duplicate model calls within a sliding window."""
        from adk_fluent.middleware import DedupMiddleware

        return MComposite([DedupMiddleware(window=window)], kind="dedup")

    @staticmethod
    def sample(rate: float, mw: MComposite | Any) -> MComposite:
        """Probabilistic middleware — fires inner middleware only N% of the time."""
        from adk_fluent.middleware import _SampledMiddleware

        stack = mw.to_stack() if isinstance(mw, MComposite) else [mw]
        wrapped = [_SampledMiddleware(rate, m) for m in stack]
        return MComposite(wrapped)

    @staticmethod
    def trace(exporter: Any = None) -> MComposite:
        """OpenTelemetry span export (no-op if opentelemetry not installed)."""
        from adk_fluent.middleware import TraceMiddleware

        return MComposite([TraceMiddleware(exporter=exporter)], kind="trace")

    @staticmethod
    def metrics(collector: Any = None) -> MComposite:
        """Metrics collection (no-op if no collector provided)."""
        from adk_fluent.middleware import MetricsMiddleware

        return MComposite([MetricsMiddleware(collector=collector)], kind="metrics")

    # --- A2A-specific middleware ---

    @staticmethod
    def a2a_retry(
        max_attempts: int = 3,
        backoff: float = 2.0,
        *,
        agents: str | tuple[str, ...] | None = None,
        on_retry: Callable | None = None,
    ) -> MComposite:
        """A2A-specific retry middleware for remote agent failures.

        Handles HTTP transport errors, A2A task FAILED/REJECTED states,
        and network-level transient failures. Uses exponential backoff.

        Args:
            max_attempts: Maximum number of retry attempts (default 3).
            backoff: Base delay in seconds for exponential backoff (default 2.0).
            agents: Scope to specific agent names (default: all agents).
            on_retry: Optional callback ``(ctx, agent_name, attempt, error)``
                      called before each retry.

        Usage::

            pipeline.middleware(M.a2a_retry(max_attempts=3, backoff=2.0))
            pipeline.middleware(M.scope("remote_*", M.a2a_retry()))
        """
        from adk_fluent.middleware import A2ARetryMiddleware

        return MComposite(
            [A2ARetryMiddleware(max_attempts=max_attempts, backoff_base=backoff, agents=agents, on_retry=on_retry)],
            kind="a2a_retry",
        )

    @staticmethod
    def a2a_circuit_breaker(
        threshold: int = 5,
        reset_after: float = 60,
        *,
        agents: str | tuple[str, ...] | None = None,
        on_open: Callable | None = None,
        on_close: Callable | None = None,
    ) -> MComposite:
        """Circuit breaker for A2A remote agents.

        Opens after ``threshold`` consecutive failures. Stays open for
        ``reset_after`` seconds, then allows a single probe call.

        Args:
            threshold: Number of failures before opening (default 5).
            reset_after: Seconds to stay open before half-open probe (default 60).
            agents: Scope to specific agent names (default: all agents).
            on_open: Callback ``(ctx, agent_name)`` when circuit opens.
            on_close: Callback ``(ctx, agent_name)`` when circuit closes.

        Usage::

            pipeline.middleware(M.a2a_circuit_breaker(threshold=5, reset_after=60))
        """
        from adk_fluent.middleware import A2ACircuitBreakerMiddleware

        return MComposite(
            [
                A2ACircuitBreakerMiddleware(
                    threshold=threshold, reset_after=reset_after, agents=agents, on_open=on_open, on_close=on_close
                )
            ],
            kind="a2a_circuit_breaker",
        )

    @staticmethod
    def a2a_timeout(
        seconds: float = 30,
        *,
        agents: str | tuple[str, ...] | None = None,
        on_timeout: Callable | None = None,
    ) -> MComposite:
        """Per-delegation timeout for A2A remote agent calls.

        Enforces wall-clock time limits on entire agent invocations.
        Critical for remote A2A calls with network latency + remote LLM
        processing.

        Args:
            seconds: Maximum seconds for the agent invocation (default 30).
            agents: Scope to specific agent names (default: all agents).
            on_timeout: Callback ``(ctx, agent_name, seconds)`` on timeout.

        Usage::

            pipeline.middleware(M.a2a_timeout(seconds=30))
            pipeline.middleware(M.scope("slow_agent", M.a2a_timeout(120)))
        """
        from adk_fluent.middleware import A2ATimeoutMiddleware

        return MComposite(
            [A2ATimeoutMiddleware(seconds=seconds, agents=agents, on_timeout=on_timeout)],
            kind="a2a_timeout",
        )
