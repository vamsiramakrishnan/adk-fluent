"""Benchmark: context providers (session event index hot path).

Providers like ``C.window(n)``, ``C.user_only()``, ``C.from_agents(...)``
all begin with ``events = list(ctx.session.events)`` plus an O(N) scan.
Wave 2 caches a per-session ``SessionEventIndex`` so a composite like
``C.none() + C.from_state('x') + C.window(5)`` only materializes and
scans the event list once per turn instead of once per provider.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from adk_fluent._context_providers import (
    _make_exclude_agents_provider,
    _make_from_agents_provider,
    _make_user_only_provider,
    _make_window_provider,
)
from adk_fluent._session_index import get_session_index
from tests.bench._common import bench, report_header


class _FakePart:
    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeContent:
    __slots__ = ("parts",)

    def __init__(self, text: str) -> None:
        self.parts = [_FakePart(text)]


class _FakeEvent:
    __slots__ = ("author", "content")

    def __init__(self, author: str, text: str) -> None:
        self.author = author
        self.content = _FakeContent(text)


class _FakeSession:
    """Weakref-able session stand-in with a mutable events list."""

    def __init__(self, events: list) -> None:
        self.events = events


def _build_session(turns: int) -> _FakeSession:
    events: list = []
    for i in range(turns):
        events.append(_FakeEvent("user", f"user question {i}"))
        events.append(_FakeEvent("assistant", f"assistant reply {i} " * 5))
        events.append(_FakeEvent("tool", f"tool output {i}"))
    return _FakeSession(events)


def main() -> None:
    report_header("Context provider benchmarks")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for turns in (8, 64, 256):
        session = _build_session(turns)
        ctx = SimpleNamespace(session=session, state={})

        window = _make_window_provider(5)
        user_only = _make_user_only_provider()
        from_agents = _make_from_agents_provider(("assistant",))
        exclude = _make_exclude_agents_provider(("tool",))

        # Prime the session-level index cache so first-call allocation is
        # excluded from steady-state numbers.
        loop.run_until_complete(window(ctx))

        bench(
            f"window(5) [turns={turns}]",
            lambda w=window, c=ctx: loop.run_until_complete(w(c)),
            iters=20_000,
        )
        bench(
            f"user_only() [turns={turns}]",
            lambda u=user_only, c=ctx: loop.run_until_complete(u(c)),
            iters=20_000,
        )
        bench(
            f"from_agents('assistant') [turns={turns}]",
            lambda f=from_agents, c=ctx: loop.run_until_complete(f(c)),
            iters=20_000,
        )
        bench(
            f"exclude_agents('tool') [turns={turns}]",
            lambda e=exclude, c=ctx: loop.run_until_complete(e(c)),
            iters=20_000,
        )

    # Simulate a composite: 3 providers sharing one session → index
    # materialization should happen exactly once.
    session = _build_session(64)
    ctx = SimpleNamespace(session=session, state={})
    window = _make_window_provider(5)
    user_only = _make_user_only_provider()
    from_agents = _make_from_agents_provider(("assistant",))

    async def composite_turn() -> None:
        await window(ctx)
        await user_only(ctx)
        await from_agents(ctx)

    bench(
        "composite 3 providers [turns=64]",
        lambda: loop.run_until_complete(composite_turn()),
        iters=20_000,
    )

    # Sanity: sync() overhead when only length grew by 1.
    def incremental_append() -> None:
        session.events.append(_FakeEvent("assistant", "one more reply"))
        get_session_index(session)

    bench(
        "index.sync (append 1 event)",
        incremental_append,
        iters=20_000,
    )

    loop.close()


if __name__ == "__main__":
    main()
