"""ReactorPlugin — ADK plugin wrapping a compiled :class:`Reactor`.

Owns the reactor lifecycle: starts it as a background task when the
session begins and stops it when the session ends. Drops into any
``App`` / ``Runner`` via ``.plugin(ReactorPlugin(reactor))``.

The plugin is deliberately thin — ``R.compile(*builders, tape=..., bus=...)``
already produces a fully wired :class:`Reactor`. This class just owns
the asyncio task so callers never need to ``await reactor.run()`` by
hand.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from adk_fluent._reactor._reactor import Reactor


__all__ = ["ReactorPlugin"]


class ReactorPlugin:
    """Run a :class:`Reactor` alongside an ADK session.

    Args:
        reactor: A compiled reactor (typically from :meth:`R.compile`).
        from_seq: Optional starting cursor on the tape. Default ``0``
            so the reactor sees the full history on resume.
        budget: Optional cap on number of rule fires before the
            reactor task exits. ``None`` means unlimited.

    The plugin uses the duck-typed ADK plugin protocol — it exposes
    ``on_session_start`` / ``on_session_end`` callbacks that the
    runner invokes during lifecycle. A hard dependency on
    ``google.adk.plugins.base_plugin.BasePlugin`` is avoided so this
    class keeps working if ADK's plugin protocol shifts.
    """

    name = "reactor"

    def __init__(
        self,
        reactor: Reactor,
        *,
        from_seq: int = 0,
        budget: int | None = None,
    ) -> None:
        self._reactor = reactor
        self._from_seq = from_seq
        self._budget = budget
        self._task: asyncio.Task | None = None

    @property
    def reactor(self) -> Reactor:
        return self._reactor

    # ------------------------------------------------------------------
    # ADK lifecycle hooks
    # ------------------------------------------------------------------

    async def on_session_start(self, *_args: Any, **_kwargs: Any) -> None:
        """Kick the reactor into a background task when a session opens."""
        if self._task is not None and not self._task.done():
            return
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(
            self._reactor.run(from_seq=self._from_seq, budget=self._budget),
            name="adk-fluent.reactor",
        )

    async def on_session_end(self, *_args: Any, **_kwargs: Any) -> None:
        """Stop the reactor and await task cleanup on session close."""
        self._reactor.stop()
        task = self._task
        self._task = None
        if task is None:
            return
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(task, timeout=0.5)

    # ------------------------------------------------------------------
    # Manual control (useful when running outside an ADK Runner)
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Alias for :meth:`on_session_start` with manual lifecycle control."""
        await self.on_session_start()

    async def stop(self) -> None:
        """Alias for :meth:`on_session_end`."""
        await self.on_session_end()
