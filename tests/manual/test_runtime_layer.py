"""Tests for the runtime layer (Phase 2 of five-layer decoupling)."""

import asyncio

import pytest

from adk_fluent._ir import AgentEvent
from adk_fluent.runtime_default import DefaultRuntime
from adk_fluent.runtime_protocol import ExecutionResult, SessionHandle


# ======================================================================
# SessionHandle
# ======================================================================


class TestSessionHandle:
    def test_defaults(self):
        session = SessionHandle(session_id="test-1")
        assert session.session_id == "test-1"
        assert session.user_id == "default"
        assert session.state == {}
        assert session.app_name == "adk_fluent_app"

    def test_with_state(self):
        session = SessionHandle(
            session_id="test-2",
            state={"key": "value"},
        )
        assert session.state == {"key": "value"}


# ======================================================================
# ExecutionResult
# ======================================================================


class TestExecutionResult:
    def test_basic(self):
        result = ExecutionResult(
            text="Hello",
            events=[],
            state={},
            session_id="s1",
        )
        assert result.text == "Hello"
        assert result.events == []
        assert result.metadata == {}
        assert result.parsed is None

    def test_with_parsed(self):
        result = ExecutionResult(
            text='{"name": "test"}',
            events=[],
            state={},
            session_id="s1",
            parsed={"name": "test"},
        )
        assert result.parsed == {"name": "test"}


# ======================================================================
# Fake backend for testing
# ======================================================================


class FakeBackend:
    """Minimal backend for testing DefaultRuntime."""

    name = "fake"

    def __init__(self, responses: list[str] | None = None):
        self._responses = responses or ["Hello from fake backend"]
        self._run_calls: list[dict] = []

    def compile(self, node, config=None):
        return "fake_compiled"

    async def run(self, compiled, prompt, **kwargs):
        self._run_calls.append({"compiled": compiled, "prompt": prompt, **kwargs})
        events = []
        for i, text in enumerate(self._responses):
            is_final = i == len(self._responses) - 1
            events.append(
                AgentEvent(
                    author="fake",
                    content=text,
                    is_final=is_final,
                )
            )
        return events

    async def stream(self, compiled, prompt, **kwargs):
        events = await self.run(compiled, prompt, **kwargs)
        for event in events:
            yield event


class FakeStateStore:
    """In-memory state store for testing."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}
        self._counter = 0

    async def create(self, namespace, **initial):
        self._counter += 1
        sid = f"store_{self._counter}"
        self._sessions[sid] = dict(initial)
        return sid

    async def load(self, session_id):
        return dict(self._sessions.get(session_id, {}))

    async def save(self, session_id, state):
        self._sessions[session_id] = dict(state)


class TrackingMiddleware:
    """Middleware that tracks which hooks were called."""

    def __init__(self):
        self.calls: list[str] = []

    async def before_run(self, ctx):
        self.calls.append("before_run")

    async def after_run(self, ctx):
        self.calls.append("after_run")


# ======================================================================
# DefaultRuntime
# ======================================================================


class TestDefaultRuntime:
    def test_execute_basic(self):
        """Basic execute() returns an ExecutionResult."""
        backend = FakeBackend(responses=["Hello world"])
        runtime = DefaultRuntime()

        result = asyncio.run(
            runtime.execute("fake_compiled", "Hi", backend=backend)
        )

        assert isinstance(result, ExecutionResult)
        assert result.text == "Hello world"
        assert len(result.events) == 1
        assert result.session_id.startswith("session_")

    def test_execute_with_compilation_result(self):
        """execute() with a CompilationResult auto-resolves backend."""
        from adk_fluent.compile import CompilationResult, EngineCapabilities

        # Register fake backend
        from adk_fluent.backends import _REGISTRY, register_backend

        backend = FakeBackend(responses=["Compiled result"])
        register_backend("fake_test", lambda **kw: backend)

        try:
            compiled = CompilationResult(
                ir=None,
                runnable="fake_compiled",
                backend_name="fake_test",
                capabilities=EngineCapabilities(),
            )
            runtime = DefaultRuntime()
            result = asyncio.run(runtime.execute(compiled, "Hi"))

            assert result.text == "Compiled result"
        finally:
            _REGISTRY.pop("fake_test", None)

    def test_execute_passes_session(self):
        """execute() creates and passes a session to the backend."""
        backend = FakeBackend()
        runtime = DefaultRuntime()

        result = asyncio.run(
            runtime.execute("fake_compiled", "Hi", backend=backend)
        )

        assert backend._run_calls[0]["session"].session_id.startswith("session_")

    def test_execute_with_state_store(self):
        """execute() uses StateStore when provided."""
        backend = FakeBackend()
        store = FakeStateStore()
        runtime = DefaultRuntime(state_store=store)

        result = asyncio.run(
            runtime.execute("fake_compiled", "Hi", backend=backend)
        )

        # Session should have been created via store
        assert result.session_id.startswith("store_")

    def test_execute_state_persistence(self):
        """State deltas from events are persisted to StateStore."""
        events_with_state = [
            AgentEvent(author="a", content="Done", is_final=True, state_delta={"key": "value"}),
        ]

        class StatefulBackend(FakeBackend):
            async def run(self, compiled, prompt, **kwargs):
                return events_with_state

        backend = StatefulBackend()
        store = FakeStateStore()
        runtime = DefaultRuntime(state_store=store)

        result = asyncio.run(
            runtime.execute("fake_compiled", "Hi", backend=backend)
        )

        # State should be persisted
        assert asyncio.run(store.load(result.session_id)) == {"key": "value"}

    def test_middleware_hooks_called(self):
        """Middleware before_run and after_run hooks are called."""
        backend = FakeBackend()
        mw = TrackingMiddleware()
        runtime = DefaultRuntime(middleware=[mw])

        asyncio.run(runtime.execute("fake_compiled", "Hi", backend=backend))

        assert mw.calls == ["before_run", "after_run"]

    def test_multiple_middleware_order(self):
        """Multiple middleware are called in order."""
        backend = FakeBackend()
        mw1 = TrackingMiddleware()
        mw2 = TrackingMiddleware()
        runtime = DefaultRuntime(middleware=[mw1, mw2])

        asyncio.run(runtime.execute("fake_compiled", "Hi", backend=backend))

        assert mw1.calls == ["before_run", "after_run"]
        assert mw2.calls == ["before_run", "after_run"]

    def test_execute_metadata_has_elapsed(self):
        """Execution result metadata includes elapsed time."""
        backend = FakeBackend()
        runtime = DefaultRuntime()

        result = asyncio.run(
            runtime.execute("fake_compiled", "Hi", backend=backend)
        )

        assert "elapsed_seconds" in result.metadata
        assert result.metadata["elapsed_seconds"] >= 0

    def test_execute_without_backend_raises(self):
        """Passing a raw runnable without backend= raises ValueError."""
        runtime = DefaultRuntime()

        with pytest.raises(ValueError, match="must provide a backend"):
            asyncio.run(runtime.execute("raw_runnable", "Hi"))

    def test_execute_stream(self):
        """execute_stream() yields events."""
        backend = FakeBackend(responses=["chunk1", "chunk2", "final"])
        runtime = DefaultRuntime()

        async def collect():
            events = []
            async for event in runtime.execute_stream(
                "fake_compiled", "Hi", backend=backend
            ):
                events.append(event)
            return events

        events = asyncio.run(collect())
        assert len(events) == 3
        assert events[0].content == "chunk1"
        assert events[2].content == "final"
        assert events[2].is_final is True

    def test_session_counter_increments(self):
        """Each execution gets a unique session ID."""
        backend = FakeBackend()
        runtime = DefaultRuntime()

        r1 = asyncio.run(runtime.execute("fake_compiled", "Hi", backend=backend))
        r2 = asyncio.run(runtime.execute("fake_compiled", "Hi", backend=backend))

        assert r1.session_id != r2.session_id

    def test_execute_with_explicit_session_id(self):
        """Explicit session_id is used when provided."""
        backend = FakeBackend()
        runtime = DefaultRuntime()

        result = asyncio.run(
            runtime.execute("fake_compiled", "Hi", backend=backend, session_id="my-session")
        )

        assert result.session_id == "my-session"
