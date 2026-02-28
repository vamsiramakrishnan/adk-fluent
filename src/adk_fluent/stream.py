"""Continuous stream execution engine.

Bridges ``AsyncIterator[str]`` sources to ADK's ``runner.run_async()``.
Built entirely on stdlib: ``asyncio.Semaphore``, ``asyncio.Event``,
``asyncio.create_task``, ``signal``.

Usage::

    from adk_fluent import Agent, Source, StreamRunner

    processor = Agent("order_processor").model("gemini-2.5-flash").instruct("...")

    runner = (
        StreamRunner(processor)
        .source(Source.from_async(order_stream()))
        .concurrency(10)
        .session_strategy("per_item")
        .on_result(lambda item, result: db.save(result))
        .on_error(lambda item, exc: dlq.push(item))
    )
    await runner.start()
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = ["StreamRunner", "StreamStats"]


@dataclass
class StreamStats:
    """Live execution counters.

    Just a dataclass with properties — not a metrics framework.
    Read ``.throughput`` and ``.elapsed`` for observability.
    """

    processed: int = 0
    errors: int = 0
    in_flight: int = 0
    start_time: float = field(default_factory=time.monotonic)

    @property
    def elapsed(self) -> float:
        """Seconds since start."""
        return time.monotonic() - self.start_time

    @property
    def throughput(self) -> float:
        """Items processed per second."""
        return self.processed / max(self.elapsed, 0.001)


class StreamRunner:
    """Production continuous execution engine.

    Reads from an ``AsyncIterator[str]`` source, processes each item
    through an ADK agent, and handles results/errors via callbacks.

    All concurrency is powered by stdlib ``asyncio.Semaphore`` and
    ``asyncio.create_task``.  Graceful shutdown uses stdlib ``signal``
    and ``asyncio.Event``.

    Parameters
    ----------
    builder
        An adk-fluent builder (Agent, Pipeline, etc.) to execute
        against each stream item.
    """

    def __init__(self, builder: Any):
        self._builder = builder
        self._source: AsyncIterator[str] | None = None
        self._concurrency: int = 1
        self._session_strategy: str = "per_item"
        self._session_key_fn: Callable[[str], str] | None = None
        self._on_result: Callable[[str, str], Any] | None = None
        self._on_error: Callable[[str, Exception], Any] | None = None
        self._shutdown_timeout: float = 30.0
        self._stop_event: asyncio.Event = asyncio.Event()
        self.stats: StreamStats = StreamStats()
        # Session caches for "shared" and "keyed" strategies
        self._shared_session: Any = None
        self._keyed_sessions: dict[str, Any] = {}
        self._task_budget: int = 50
        self._middlewares: list[Any] = []

    # ------------------------------------------------------------------
    # Fluent configuration (each returns self for chaining)
    # ------------------------------------------------------------------

    def source(self, src: AsyncIterator[str]) -> StreamRunner:
        """Set the stream source (any ``AsyncIterator[str]``)."""
        self._source = src
        return self

    def concurrency(self, n: int) -> StreamRunner:
        """Max concurrent agent executions (default 1)."""
        self._concurrency = n
        return self

    def session_strategy(self, strategy: str) -> StreamRunner:
        """Session management strategy.

        - ``"per_item"`` (default): Fresh session per stream item (stateless).
        - ``"shared"``: Single persistent session (stateful, sequential context).
        - ``"keyed"``: Session per key extracted by ``.session_key(fn)``.
        """
        self._session_strategy = strategy
        return self

    def session_key(self, fn: Callable[[str], str]) -> StreamRunner:
        """Extract a session key from each stream item.

        Implies ``session_strategy("keyed")``.  Items with the same
        key share a session, enabling stateful per-entity processing.
        """
        self._session_key_fn = fn
        self._session_strategy = "keyed"
        return self

    def on_result(self, fn: Callable[[str, str], Any]) -> StreamRunner:
        """Callback for successful processing: ``fn(input_item, result_text)``."""
        self._on_result = fn
        return self

    def on_error(self, fn: Callable[[str, Exception], Any]) -> StreamRunner:
        """Callback for failed processing: ``fn(input_item, exception)``.

        This IS the dead-letter queue — route failures wherever you want.
        """
        self._on_error = fn
        return self

    def task_budget(self, n: int) -> StreamRunner:
        """Max concurrent dispatch tasks across all stream items (default 50)."""
        self._task_budget = n
        return self

    def middleware(self, mw: Any) -> StreamRunner:
        """Add middleware for stream execution observability."""
        self._middlewares.append(mw)
        return self

    def graceful_shutdown(self, timeout: float = 30) -> StreamRunner:
        """Max seconds to wait for in-flight items during shutdown."""
        self._shutdown_timeout = timeout
        return self

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Run the main processing loop until the source is exhausted or stop() is called.

        Reads items from the source, processes each through the agent
        with bounded concurrency, and invokes result/error callbacks.
        """
        if self._source is None:
            raise ValueError("No source configured. Call .source() before .start().")

        from google.adk.runners import InMemoryRunner
        from google.genai import types

        from adk_fluent._base import _global_task_budget

        agent = self._builder.build()
        app_name = f"_stream_{agent.name}"

        # Collect middleware from StreamRunner and builder
        all_mw: list[Any] = list(self._middlewares)
        builder_mw = getattr(self._builder, "_middlewares", [])
        if builder_mw:
            all_mw.extend(builder_mw)

        runner = InMemoryRunner(agent=agent, app_name=app_name)

        # Set global task budget for all dispatch agents within this stream
        _global_task_budget.set(asyncio.Semaphore(self._task_budget))

        # stdlib: Semaphore for concurrency, Event for shutdown
        sem = asyncio.Semaphore(self._concurrency)
        tasks: set[asyncio.Task[None]] = set()
        self.stats = StreamStats()

        # stdlib: signal handling for graceful shutdown
        loop = asyncio.get_running_loop()
        original_handlers: dict[int, Any] = {}
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError, OSError):
                original_handlers[sig] = loop.add_signal_handler(sig, self._stop_event.set)

        try:

            async def _process(item: str) -> None:
                from adk_fluent._base import _execution_mode

                _execution_mode.set("stream")
                async with sem:
                    self.stats.in_flight += 1
                    result_text: str | None = None
                    error: Exception | None = None
                    try:
                        session = await self._resolve_session(runner, app_name, item)
                        content = types.Content(role="user", parts=[types.Part(text=item)])
                        last_text = ""
                        async for event in runner.run_async(
                            user_id="_stream",
                            session_id=session.id,
                            new_message=content,
                        ):
                            if event.content and event.content.parts:
                                for part in event.content.parts:
                                    if part.text:
                                        last_text = part.text
                        self.stats.processed += 1
                        result_text = last_text
                        if self._on_result:
                            self._on_result(item, last_text)
                    except Exception as exc:
                        self.stats.errors += 1
                        error = exc
                        if self._on_error:
                            self._on_error(item, exc)
                    finally:
                        self.stats.in_flight -= 1
                        # Fire on_stream_item middleware hook
                        for mw in all_mw:
                            hook = getattr(mw, "on_stream_item", None)
                            if hook:
                                await hook(None, item, result_text, error)

            # Main loop: read source, dispatch tasks with bounded concurrency
            async for item in self._source:
                if self._stop_event.is_set():
                    break
                task = asyncio.create_task(_process(item))
                tasks.add(task)
                task.add_done_callback(tasks.discard)

            # Drain in-flight tasks
            if tasks:
                await asyncio.wait(tasks, timeout=self._shutdown_timeout)
                # Cancel any remaining tasks after timeout
                for task in tasks:
                    if not task.done():
                        task.cancel()

        finally:
            # Restore original signal handlers
            for sig in original_handlers:
                with contextlib.suppress(NotImplementedError, OSError):
                    loop.remove_signal_handler(sig)

    async def stop(self) -> None:
        """Signal the runner to stop accepting new items.

        In-flight items will be drained up to the graceful shutdown timeout.
        """
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Session resolution
    # ------------------------------------------------------------------

    async def _resolve_session(self, runner: Any, app_name: str, item: str) -> Any:
        """Resolve the ADK session based on the configured strategy."""
        if self._session_strategy == "shared":
            if self._shared_session is None:
                self._shared_session = await runner.session_service.create_session(app_name=app_name, user_id="_stream")
            return self._shared_session

        if self._session_strategy == "keyed" and self._session_key_fn:
            key = self._session_key_fn(item)
            if key not in self._keyed_sessions:
                self._keyed_sessions[key] = await runner.session_service.create_session(
                    app_name=app_name, user_id=f"_stream_{key}"
                )
            return self._keyed_sessions[key]

        # Default: per_item — fresh session each time
        return await runner.session_service.create_session(app_name=app_name, user_id="_stream")
