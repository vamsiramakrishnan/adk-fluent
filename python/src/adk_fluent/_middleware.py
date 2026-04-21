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

from adk_fluent._composite import Composite

__all__ = ["M", "MComposite"]


class MComposite(Composite, kind="middleware_chain"):
    """Composable middleware chain. The result of any ``M.xxx()`` call.

    Supports ``|`` for composition, and ``>>`` to attach to a builder::

        agent = M.retry(3) | M.log() >> Agent("x", "gemini-2.5-flash")
        # equivalent to: Agent(...).middleware(M.retry(3) | M.log())
    """

    _builder_attach_method = "middleware"

    def to_stack(self) -> list[Any]:
        """Flatten to list of protocol-level middleware instances."""
        return list(self._items)


class M:
    """Fluent middleware composition. Consistent with P, C, S modules.

    Operators (see ``shared/parity.toml`` for the cross-language contract)::

        a | b   → chain: middleware stack is applied outer→inner, so
                  ``M.retry() | M.log()`` runs retry's before-hook first,
                  then log's. No union semantics; ``|`` is concatenation.
                  TS: ``a.pipe(b)`` (no ``.union()`` — chain is the only verb).
        a >> Builder  → attach: ``builder.middleware(a)``.
                        TS: ``a.attachTo(builder)``.

    Factory methods return ``MComposite`` instances.
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
        """Probabilistic middleware — fires inner middleware only N% of the time.

        Note: this is *sampling*, not rate limiting. For a real token-bucket
        rate ceiling on model calls, use :meth:`rate_limit` instead.
        """
        from adk_fluent.middleware import _SampledMiddleware

        stack = mw.to_stack() if isinstance(mw, MComposite) else [mw]
        wrapped = [_SampledMiddleware(rate, m) for m in stack]
        return MComposite(wrapped)

    @staticmethod
    def rate_limit(rate: float, *, time_period: float = 1.0) -> MComposite:
        """Token-bucket rate limiter for model calls (via ``aiolimiter``).

        Blocks in ``before_model`` until a token is available from a leaky
        bucket of capacity ``rate`` refilled over ``time_period`` seconds.
        Use this for enforcing a true throughput ceiling (e.g., "≤ 10 model
        calls per second"). Contrast with :meth:`sample`, which is
        probabilistic dropping — not a real limiter.

        Args:
            rate: Maximum number of calls allowed per ``time_period`` seconds.
            time_period: Window size in seconds (default 1.0).

        Requires ``pip install adk-fluent[ratelimit]``.

        Usage::

            pipeline.middleware(M.rate_limit(10))                  # 10/sec
            pipeline.middleware(M.rate_limit(60, time_period=60))  # 60/min
        """
        from adk_fluent.middleware import RateLimitMiddleware

        return MComposite([RateLimitMiddleware(rate=rate, time_period=time_period)], kind="rate_limit")

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

    @staticmethod
    def a2ui_log(
        *,
        level: str = "info",
        agents: list[str] | None = None,
    ) -> MComposite:
        """Log A2UI surface operations (createSurface, updateComponents, etc.).

        Attaches an after_model callback that inspects tool calls for A2UI
        operations and logs them at the specified level.

        Args:
            level: Log level — ``"info"`` or ``"debug"``.
            agents: Optional list of agent names to scope the logging to.

        Usage::

            agent.middleware(M.a2ui_log())
            pipeline.middleware(M.a2ui_log(level="debug"))
        """
        import logging

        from adk_fluent.middleware import _SingleHookMiddleware

        logger = logging.getLogger("adk_fluent.a2ui")

        async def _log_a2ui(callback_context: Any) -> None:
            response = getattr(callback_context, "response", None)
            if response is None:
                return
            # Inspect function calls for A2UI operations
            a2ui_ops = ["createSurface", "updateComponents", "updateDataModel", "deleteSurface"]
            for part in getattr(response, "parts", []):
                fc = getattr(part, "function_call", None)
                if fc is None:
                    continue
                name = getattr(fc, "name", "")
                if any(op in name for op in a2ui_ops):
                    log_fn = getattr(logger, level, logger.info)
                    agent_name = getattr(callback_context, "agent_name", "?")
                    log_fn(f"[A2UI] {agent_name}: {name}")

        mw = _SingleHookMiddleware("after_model_callback", _log_a2ui)
        return MComposite([mw], kind="a2ui_log")
