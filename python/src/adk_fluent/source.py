"""Stream source factories for continuous agent execution.

Each factory returns an ``AsyncIterator[str]``. No custom base class —
Python's ``AsyncIterator`` protocol IS the abstraction.

The only concrete class is ``Inbox``, a thin wrapper around
``asyncio.Queue`` for push-based sources (webhooks, external callers).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import Any

__all__ = ["Source", "Inbox"]

_SENTINEL = object()


class Source:
    """Factory namespace for stream sources.

    All factory methods return ``AsyncIterator[str]`` — the stdlib
    protocol for async streams.  No inheritance hierarchy, no framework.

    Usage::

        # Async generator (wraps any queue/stream)
        source = Source.from_async(my_async_gen())

        # Sync iterable (files, lists)
        source = Source.from_iter(open("events.jsonl"))

        # Polling function
        source = Source.poll(check_new_orders, interval=5)

        # Push-based (webhooks)
        inbox = Source.callback()
        inbox.push("new order data")
    """

    @staticmethod
    async def from_async(agen: AsyncIterator[str]) -> AsyncIterator[str]:
        """Pass through an existing async iterator.

        .. deprecated::
            ``Source.from_async()`` is a no-op wrapper that re-yields an async
            iterator unchanged. Pass your async iterator directly to
            ``StreamRunner.source()`` instead.
        """
        import warnings

        warnings.warn(
            "Source.from_async() is a no-op. Pass your async iterator directly to StreamRunner.source().",
            DeprecationWarning,
            stacklevel=2,
        )
        async for item in agen:
            yield item

    @staticmethod
    async def from_iter(iterable: Iterable[str]) -> AsyncIterator[str]:
        """Wrap a sync iterable (file handle, list, generator) as async.

        Each item is yielded without blocking the event loop.
        """
        for item in iterable:
            yield item

    @staticmethod
    async def poll(
        fn: Callable[[], Any | Awaitable[Any]],
        interval: float = 1.0,
    ) -> AsyncIterator[str]:
        """Call *fn()* every *interval* seconds. Yield non-None results.

        Supports both sync and async callables. ``None`` returns are
        silently skipped (treated as "no new data").
        """
        while True:
            result = fn()
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                result = await result
            if result is not None:
                yield str(result)
            await asyncio.sleep(interval)

    @staticmethod
    def callback(maxsize: int = 0) -> Inbox:
        """Create a push-based source backed by ``asyncio.Queue``.

        Returns an :class:`Inbox` with ``.push()`` for external callers
        and ``async for`` for the consumer.
        """
        return Inbox(maxsize=maxsize)


class Inbox:
    """Push-based async source wrapping ``asyncio.Queue``.

    External code (webhooks, message handlers) calls ``.push()`` to
    inject items.  The consumer reads via ``async for item in inbox:``.

    Supports optional backpressure via *maxsize*: when the queue is
    full, ``.push()`` raises ``asyncio.QueueFull`` and
    ``.push_async()`` blocks until space is available.
    """

    def __init__(self, maxsize: int = 0):
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=maxsize)

    def push(self, item: str) -> None:
        """Push an item (non-blocking).

        Raises ``asyncio.QueueFull`` if *maxsize* is set and the
        queue is at capacity.
        """
        self._queue.put_nowait(item)

    async def push_async(self, item: str) -> None:
        """Push an item (async, blocks if queue is at *maxsize*)."""
        await self._queue.put(item)

    def close(self) -> None:
        """Signal that no more items will be pushed.

        The consumer's ``async for`` loop will terminate after
        draining any remaining items.
        """
        self._queue.put_nowait(_SENTINEL)

    @property
    def pending(self) -> int:
        """Number of items currently in the queue."""
        return self._queue.qsize()

    def __aiter__(self) -> Inbox:
        return self

    async def __anext__(self) -> str:
        item = await self._queue.get()
        if item is _SENTINEL:
            raise StopAsyncIteration
        return item
