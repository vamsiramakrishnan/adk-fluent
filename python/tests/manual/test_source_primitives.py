"""Tests for Source factories and Inbox push-based source."""

import asyncio

import pytest

from adk_fluent.source import Inbox, Source

# ======================================================================
# Source.from_iter
# ======================================================================


class TestFromIter:
    @pytest.mark.asyncio
    async def test_from_iter_yields_all(self):
        """Wraps a sync iterable and yields all items."""
        items = ["a", "b", "c"]
        collected = []
        async for item in Source.from_iter(items):
            collected.append(item)
        assert collected == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_from_iter_empty(self):
        collected = []
        async for item in Source.from_iter([]):
            collected.append(item)
        assert collected == []


# ======================================================================
# Source.from_async (deprecated)
# ======================================================================


class TestFromAsync:
    @pytest.mark.asyncio
    async def test_from_async_deprecation_warning(self):
        """Source.from_async() emits DeprecationWarning."""

        async def gen():
            yield "x"

        with pytest.warns(DeprecationWarning, match="no-op"):
            collected = []
            async for item in Source.from_async(gen()):
                collected.append(item)
            assert collected == ["x"]


# ======================================================================
# Source.poll
# ======================================================================


class TestPoll:
    @pytest.mark.asyncio
    async def test_poll_yields_non_none(self):
        """poll skips None results and yields non-None as strings."""
        call_count = 0
        returns = [None, "first", None, "second"]

        def fn():
            nonlocal call_count
            idx = call_count
            call_count += 1
            if idx < len(returns):
                return returns[idx]
            return None

        collected = []
        async for item in Source.poll(fn, interval=0.01):
            collected.append(item)
            if len(collected) >= 2:
                break
        assert collected == ["first", "second"]


# ======================================================================
# Inbox
# ======================================================================


class TestInbox:
    @pytest.mark.asyncio
    async def test_inbox_push_close_iterate(self):
        """push, close, async iteration terminates."""
        inbox = Inbox()
        inbox.push("hello")
        inbox.push("world")
        inbox.close()

        collected = []
        async for item in inbox:
            collected.append(item)
        assert collected == ["hello", "world"]

    @pytest.mark.asyncio
    async def test_inbox_pending_count(self):
        """.pending reflects queue depth."""
        inbox = Inbox()
        assert inbox.pending == 0
        inbox.push("a")
        assert inbox.pending == 1
        inbox.push("b")
        assert inbox.pending == 2

    @pytest.mark.asyncio
    async def test_inbox_from_callback_factory(self):
        """Source.callback() creates an Inbox."""
        inbox = Source.callback()
        assert isinstance(inbox, Inbox)

    @pytest.mark.asyncio
    async def test_inbox_maxsize_raises_on_overflow(self):
        """Inbox with maxsize raises QueueFull when full."""
        inbox = Inbox(maxsize=1)
        inbox.push("a")
        with pytest.raises(asyncio.QueueFull):
            inbox.push("b")
