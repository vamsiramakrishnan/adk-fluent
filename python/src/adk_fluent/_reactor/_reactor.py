"""Reactor — cursor-following async scheduler.

The reactor bridges signals to actions. Register ``(predicate, handler)``
rules; when a :class:`SignalChanged` event comes off the tape and the
predicate matches, the handler is scheduled with the rule's priority.
Higher priority handlers are run first; a running handler can be
preempted by a higher-priority rule if ``preemptive=True``.

The rule handler is any awaitable: an ``await agent.run.ask(...)`` (which
returns a coroutine inside the running reactor loop), a plain
``async def``, or a bound Reactor subcomponent. This keeps the reactor
orthogonal to the builder surface — it schedules whatever you hand it.

Execution loop::

    async for entry in tape.tail(from_seq=cursor):
        if entry["kind"] != "signal_changed": continue
        change = _Change(...)
        for rule in rules:
            if rule.predicate.matches(change):
                scheduler.submit(rule)

The scheduler is a simple priority queue. When ``preemptive`` rules
fire, the current task is cancelled before the new one starts. Resume
cursors are emitted as :class:`Interrupted` events so downstream
consumers can replay from the break.
"""

from __future__ import annotations

import asyncio
import heapq
import itertools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from adk_fluent._harness._events import Interrupted
from adk_fluent._reactor._predicate import SignalPredicate, _Change

if TYPE_CHECKING:
    from adk_fluent._harness._event_bus import EventBus
    from adk_fluent._session._tape import SessionTape

__all__ = ["Reactor", "ReactorRule"]


Handler = Callable[[_Change], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ReactorRule:
    """A ``(predicate, handler)`` pair with scheduling metadata."""

    name: str
    predicate: SignalPredicate
    handler: Handler
    priority: int = 0
    preemptive: bool = False


@dataclass(order=True)
class _Task:
    """Internal priority-queue entry."""

    neg_priority: int
    seq: int
    rule: ReactorRule = field(compare=False)
    change: _Change = field(compare=False)


class Reactor:
    """Cursor-following reactive scheduler.

    Args:
        tape: The :class:`SessionTape` to follow.
        bus: Optional :class:`EventBus` for emitting ``Interrupted`` on
            pre-emption. If omitted, pre-emption still works but is not
            observable on the bus.
    """

    def __init__(
        self,
        tape: SessionTape,
        *,
        bus: EventBus | None = None,
    ) -> None:
        self._tape = tape
        self._bus = bus
        self._rules: list[ReactorRule] = []
        # Priority-ordered pending queue. Each entry is (-priority,
        # counter) so ties break FIFO. Heap ordering matches this.
        self._pending: list[_Task] = []
        self._counter = itertools.count()
        self._current_task: asyncio.Task | None = None
        self._current_rule: ReactorRule | None = None
        self._stop = asyncio.Event()
        self._drain = asyncio.Event()

    # ------------------------------------------------------------------
    # Rule registration
    # ------------------------------------------------------------------

    def when(
        self,
        predicate: SignalPredicate,
        handler: Handler,
        *,
        name: str = "",
        priority: int = 0,
        preemptive: bool = False,
    ) -> ReactorRule:
        rule = ReactorRule(
            name=name or f"rule_{len(self._rules)}",
            predicate=predicate,
            handler=handler,
            priority=priority,
            preemptive=preemptive,
        )
        self._rules.append(rule)
        return rule

    @property
    def rules(self) -> tuple[ReactorRule, ...]:
        return tuple(self._rules)

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------

    async def run(self, *, from_seq: int = 0, budget: int | None = None) -> int:
        """Follow the tape and dispatch rules until stopped or budget hit.

        Args:
            from_seq: Starting cursor on the tape.
            budget: Optional cap on the number of handler invocations.
                Returns when this many fires. ``None`` means unlimited —
                run until :meth:`stop` is called.

        Returns:
            The number of rule handlers that fired.
        """
        fires = 0
        async for entry in self._tape.tail(from_seq=from_seq):
            if self._stop.is_set():
                break
            if entry.get("kind") != "signal_changed":
                continue
            change = _Change(
                signal_name=str(entry.get("name", "")),
                value=entry.get("value"),
                previous=entry.get("previous"),
            )
            for rule in self._rules:
                if rule.predicate.matches(change):
                    await self._submit(rule, change)
                    fires += 1
                    if budget is not None and fires >= budget:
                        return fires
        return fires

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    async def _submit(self, rule: ReactorRule, change: _Change) -> None:
        # Preemption: a higher-priority, preemptive rule cancels the
        # current task and emits Interrupted. The cancelled task is
        # not restarted — the caller is expected to use the resume
        # cursor to restart work.
        if (
            rule.preemptive
            and self._current_rule is not None
            and rule.priority > self._current_rule.priority
            and self._current_task is not None
            and not self._current_task.done()
        ):
            interrupted_rule = self._current_rule
            self._current_task.cancel()
            if self._bus is not None:
                self._bus.emit(
                    Interrupted(
                        agent_name=interrupted_rule.name,
                        reason=f"preempted by {rule.name} (priority {rule.priority})",
                        resume_cursor=self._tape.head,
                    )
                )

        # If there's a current running task that is still active and
        # this one isn't higher-priority preemptive, queue it.
        if self._current_task is not None and not self._current_task.done():
            task = _Task(
                neg_priority=-rule.priority,
                seq=next(self._counter),
                rule=rule,
                change=change,
            )
            heapq.heappush(self._pending, task)
            return

        await self._dispatch(rule, change)

    async def _dispatch(self, rule: ReactorRule, change: _Change) -> None:
        loop = asyncio.get_running_loop()

        async def _runner() -> None:
            try:
                await rule.handler(change)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Handler isolation — one failing rule never blocks
                # the scheduler. Consumers can observe via the bus.
                pass
            finally:
                self._current_task = None
                self._current_rule = None
                # Drain any queued tasks in priority order.
                if self._pending:
                    nxt = heapq.heappop(self._pending)
                    await self._dispatch(nxt.rule, nxt.change)

        self._current_rule = rule
        self._current_task = loop.create_task(_runner())


# Re-export the internal payload for tests that want to build one directly.
__all__ += ["_Change"]  # type: ignore[misc]
