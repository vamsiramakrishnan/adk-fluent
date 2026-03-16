"""Tests for the compute layer (Phase 4 of five-layer decoupling)."""

import asyncio

import pytest

from adk_fluent.compute import (
    ComputeConfig,
    InMemoryArtifactStore,
    InMemoryStateStore,
)
from adk_fluent.compute._protocol import (
    ArtifactStore,
    GenerateConfig,
    GenerateResult,
    Message,
    ModelProvider,
    StateStore,
    ToolDef,
    ToolRuntime,
)
from adk_fluent.compute.memory import LocalToolRuntime


# ======================================================================
# Data types
# ======================================================================


class TestMessage:
    def test_basic(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls == []

    def test_with_tool_calls(self):
        msg = Message(
            role="assistant",
            content="",
            tool_calls=[{"name": "search", "args": {"q": "test"}}],
        )
        assert len(msg.tool_calls) == 1


class TestGenerateResult:
    def test_no_tool_calls(self):
        result = GenerateResult(text="Hello")
        assert result.has_tool_calls is False
        assert result.finish_reason == "stop"

    def test_with_tool_calls(self):
        result = GenerateResult(
            text="",
            tool_calls=[{"name": "search", "args": {}}],
        )
        assert result.has_tool_calls is True


# ======================================================================
# InMemoryStateStore
# ======================================================================


class TestInMemoryStateStore:
    def test_create_and_load(self):
        async def _test():
            store = InMemoryStateStore()
            sid = await store.create("test-ns", key="value")
            state = await store.load(sid)
            assert state == {"key": "value"}

        asyncio.run(_test())

    def test_save_and_load(self):
        async def _test():
            store = InMemoryStateStore()
            sid = await store.create("test-ns")
            await store.save(sid, {"updated": True})
            state = await store.load(sid)
            assert state == {"updated": True}

        asyncio.run(_test())

    def test_load_nonexistent_returns_empty(self):
        async def _test():
            store = InMemoryStateStore()
            state = await store.load("nonexistent")
            assert state == {}

        asyncio.run(_test())

    def test_delete(self):
        async def _test():
            store = InMemoryStateStore()
            sid = await store.create("test-ns")
            await store.delete(sid)
            state = await store.load(sid)
            assert state == {}

        asyncio.run(_test())

    def test_list_sessions(self):
        async def _test():
            store = InMemoryStateStore()
            s1 = await store.create("ns1")
            s2 = await store.create("ns1")
            s3 = await store.create("ns2")
            assert len(await store.list_sessions("ns1")) == 2
            assert len(await store.list_sessions("ns2")) == 1
            assert len(await store.list_sessions("ns3")) == 0

        asyncio.run(_test())

    def test_unique_session_ids(self):
        async def _test():
            store = InMemoryStateStore()
            ids = set()
            for _ in range(10):
                sid = await store.create("test")
                ids.add(sid)
            assert len(ids) == 10

        asyncio.run(_test())

    def test_satisfies_protocol(self):
        assert isinstance(InMemoryStateStore(), StateStore)


# ======================================================================
# InMemoryArtifactStore
# ======================================================================


class TestInMemoryArtifactStore:
    def test_save_and_load(self):
        async def _test():
            store = InMemoryArtifactStore()
            version = await store.save("doc.txt", b"Hello")
            assert version == 0
            data = await store.load("doc.txt")
            assert data == b"Hello"

        asyncio.run(_test())

    def test_versioning(self):
        async def _test():
            store = InMemoryArtifactStore()
            v0 = await store.save("doc.txt", b"v1")
            v1 = await store.save("doc.txt", b"v2")
            assert v0 == 0
            assert v1 == 1

            assert await store.load("doc.txt", version=0) == b"v1"
            assert await store.load("doc.txt", version=1) == b"v2"
            assert await store.load("doc.txt") == b"v2"  # Latest

        asyncio.run(_test())

    def test_list_versions(self):
        async def _test():
            store = InMemoryArtifactStore()
            await store.save("doc.txt", b"v1")
            await store.save("doc.txt", b"v2")
            versions = await store.list_versions("doc.txt")
            assert versions == [0, 1]

        asyncio.run(_test())

    def test_load_nonexistent_raises(self):
        async def _test():
            store = InMemoryArtifactStore()
            with pytest.raises(KeyError):
                await store.load("nonexistent")

        asyncio.run(_test())

    def test_delete_all(self):
        async def _test():
            store = InMemoryArtifactStore()
            await store.save("doc.txt", b"data")
            await store.delete("doc.txt")
            with pytest.raises(KeyError):
                await store.load("doc.txt")

        asyncio.run(_test())

    def test_satisfies_protocol(self):
        assert isinstance(InMemoryArtifactStore(), ArtifactStore)


# ======================================================================
# LocalToolRuntime
# ======================================================================


class TestLocalToolRuntime:
    def test_sync_function(self):
        async def _test():
            runtime = LocalToolRuntime()

            def add(a: int, b: int) -> int:
                return a + b

            result = await runtime.execute("add", add, {"a": 2, "b": 3})
            assert result == 5

        asyncio.run(_test())

    def test_async_function(self):
        async def _test():
            runtime = LocalToolRuntime()

            async def async_add(a: int, b: int) -> int:
                return a + b

            result = await runtime.execute("async_add", async_add, {"a": 2, "b": 3})
            assert result == 5

        asyncio.run(_test())

    def test_satisfies_protocol(self):
        assert isinstance(LocalToolRuntime(), ToolRuntime)


# ======================================================================
# ComputeConfig
# ======================================================================


class TestComputeConfig:
    def test_defaults(self):
        config = ComputeConfig()
        assert config.model_provider is None
        assert config.state_store is None
        assert config.tool_runtime is None
        assert config.artifact_store is None

    def test_with_stores(self):
        config = ComputeConfig(
            state_store=InMemoryStateStore(),
            artifact_store=InMemoryArtifactStore(),
        )
        assert config.state_store is not None
        assert config.artifact_store is not None

    def test_model_provider_string(self):
        """Model provider can be a string (resolved by backend)."""
        config = ComputeConfig(model_provider="gemini-2.5-flash")
        assert config.model_provider == "gemini-2.5-flash"
