"""Tests for A2A Phase 2: State bridging and resilience middleware.

Tests verify:
1. RemoteAgent .sends()/.receives()/.persistent_context()/.context_key()
2. A2ARetryMiddleware
3. A2ACircuitBreakerMiddleware + A2ACircuitOpenError
4. A2ATimeoutMiddleware
5. M.a2a_retry(), M.a2a_circuit_breaker(), M.a2a_timeout() factory methods
"""

import asyncio
import time
import warnings

import pytest

from adk_fluent._middleware import M, MComposite
from adk_fluent.a2a import RemoteAgent
from adk_fluent.middleware import (
    A2ACircuitBreakerMiddleware,
    A2ACircuitOpenError,
    A2ARetryMiddleware,
    A2ATimeoutMiddleware,
)

# ======================================================================
# 1. RemoteAgent state bridging
# ======================================================================


class TestRemoteAgentSends:
    """Tests for .sends() state bridging."""

    def test_sends_stores_keys(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001").sends("draft", "context")
        assert builder._config["_sends_keys"] == ["draft", "context"]

    def test_sends_accumulates(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001").sends("a").sends("b", "c")
        assert builder._config["_sends_keys"] == ["a", "b", "c"]

    def test_sends_returns_self(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001")
            result = builder.sends("key")
        assert result is builder

    def test_sends_chainable(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = (
                RemoteAgent("helper", "http://h:8001")
                .sends("draft")
                .describe("A helper")
                .timeout(30)
            )
        assert builder._config["_sends_keys"] == ["draft"]
        assert builder._config["description"] == "A helper"
        assert builder._config["timeout"] == 30


class TestRemoteAgentReceives:
    """Tests for .receives() state bridging."""

    def test_receives_stores_keys(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001").receives("feedback", "score")
        assert builder._config["_receives_keys"] == ["feedback", "score"]

    def test_receives_accumulates(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001").receives("a").receives("b")
        assert builder._config["_receives_keys"] == ["a", "b"]

    def test_receives_returns_self(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001")
            result = builder.receives("key")
        assert result is builder


class TestRemoteAgentPersistentContext:
    """Tests for .persistent_context() contextId management."""

    def test_persistent_context_stores_flag(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001").persistent_context()
        assert builder._config["_persistent_context"] is True

    def test_persistent_context_disabled(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001").persistent_context(False)
        assert builder._config["_persistent_context"] is False

    def test_context_key_stores_custom_key(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = RemoteAgent("helper", "http://h:8001").context_key("my_ctx")
        assert builder._config["_context_key"] == "my_ctx"

    def test_persistent_context_chainable(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = (
                RemoteAgent("reviewer", "http://r:8001")
                .persistent_context()
                .context_key("reviewer_ctx")
                .sends("draft")
                .receives("feedback")
            )
        assert builder._config["_persistent_context"] is True
        assert builder._config["_context_key"] == "reviewer_ctx"
        assert builder._config["_sends_keys"] == ["draft"]
        assert builder._config["_receives_keys"] == ["feedback"]


class TestStateBridgeFull:
    """Integration test for sends + receives + persistent_context together."""

    def test_full_bridging_config(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = (
                RemoteAgent("reviewer", "http://reviewer:8001")
                .sends("draft", "context")
                .receives("feedback", "score")
                .persistent_context()
                .context_key("reviewer_ctx_id")
                .timeout(120)
                .describe("Code reviewer")
            )
        assert builder._config["_sends_keys"] == ["draft", "context"]
        assert builder._config["_receives_keys"] == ["feedback", "score"]
        assert builder._config["_persistent_context"] is True
        assert builder._config["_context_key"] == "reviewer_ctx_id"
        assert builder._config["timeout"] == 120
        assert builder._config["description"] == "Code reviewer"


# ======================================================================
# 2. A2ARetryMiddleware
# ======================================================================


class TestA2ARetryMiddleware:
    """Tests for A2ARetryMiddleware."""

    def test_creation_defaults(self):
        mw = A2ARetryMiddleware()
        assert mw.max_attempts == 3
        assert mw.backoff_base == 2.0
        assert mw.agents is None

    def test_creation_custom(self):
        mw = A2ARetryMiddleware(max_attempts=5, backoff_base=1.0, agents=("r1", "r2"))
        assert mw.max_attempts == 5
        assert mw.backoff_base == 1.0
        assert mw.agents == ("r1", "r2")

    def test_should_retry_connection_refused(self):
        mw = A2ARetryMiddleware()
        assert mw._should_retry(ConnectionError("Connection refused"))

    def test_should_retry_timeout(self):
        mw = A2ARetryMiddleware()
        assert mw._should_retry(TimeoutError("Request timed out"))

    def test_should_retry_500(self):
        mw = A2ARetryMiddleware()
        assert mw._should_retry(RuntimeError("HTTP 500 Internal Server Error"))

    def test_should_retry_failed_task(self):
        mw = A2ARetryMiddleware()
        assert mw._should_retry(RuntimeError("task_state_failed"))

    def test_should_not_retry_value_error(self):
        mw = A2ARetryMiddleware()
        assert not mw._should_retry(ValueError("Invalid argument"))

    @pytest.mark.asyncio
    async def test_on_tool_error_retryable(self):
        mw = A2ARetryMiddleware(max_attempts=3, backoff_base=0.01)
        error = ConnectionError("Connection refused")
        result = await mw.on_tool_error(None, "remote_agent", {}, error)
        assert result is None
        assert mw._attempts["remote_agent"] == 1

    @pytest.mark.asyncio
    async def test_on_tool_error_not_retryable(self):
        mw = A2ARetryMiddleware(max_attempts=3, backoff_base=0.01)
        error = ValueError("Invalid argument")
        result = await mw.on_tool_error(None, "remote_agent", {}, error)
        assert result is None
        assert mw._attempts.get("remote_agent") is None

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        called = []

        async def on_retry(ctx, name, attempt, error):
            called.append((name, attempt))

        mw = A2ARetryMiddleware(max_attempts=3, backoff_base=0.01, on_retry=on_retry)
        error = ConnectionError("Connection refused")
        await mw.on_tool_error(None, "r1", {}, error)
        assert called == [("r1", 1)]


# ======================================================================
# 3. A2ACircuitBreakerMiddleware
# ======================================================================


class TestA2ACircuitBreakerMiddleware:
    """Tests for A2ACircuitBreakerMiddleware."""

    def test_creation_defaults(self):
        mw = A2ACircuitBreakerMiddleware()
        assert mw._threshold == 5
        assert mw._reset_after == 60
        assert mw.agents is None

    def test_open_circuits_initially_empty(self):
        mw = A2ACircuitBreakerMiddleware()
        assert mw.open_circuits == {}

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        mw = A2ACircuitBreakerMiddleware(threshold=3, reset_after=60)
        for _ in range(3):
            await mw.on_tool_error(None, "remote", {}, RuntimeError("fail"))
        assert "remote" in mw.open_circuits

    @pytest.mark.asyncio
    async def test_circuit_rejects_when_open(self):
        mw = A2ACircuitBreakerMiddleware(threshold=2, reset_after=60)
        for _ in range(2):
            await mw.on_tool_error(None, "remote", {}, RuntimeError("fail"))
        with pytest.raises(A2ACircuitOpenError, match="circuit open"):
            await mw.before_agent(None, "remote")

    @pytest.mark.asyncio
    async def test_circuit_resets_after_success(self):
        mw = A2ACircuitBreakerMiddleware(threshold=2, reset_after=0.01)
        for _ in range(2):
            await mw.on_tool_error(None, "remote", {}, RuntimeError("fail"))
        # Wait for reset
        await asyncio.sleep(0.02)
        # Half-open: should allow probe
        await mw.before_agent(None, "remote")
        assert "remote" in mw._half_open
        # Success closes circuit
        await mw.after_agent(None, "remote")
        assert "remote" not in mw._half_open
        assert mw._failures.get("remote") == 0

    @pytest.mark.asyncio
    async def test_on_open_callback(self):
        called = []

        async def on_open(ctx, name):
            called.append(name)

        mw = A2ACircuitBreakerMiddleware(threshold=2, reset_after=60, on_open=on_open)
        for _ in range(2):
            await mw.on_tool_error(None, "remote", {}, RuntimeError("fail"))
        assert called == ["remote"]

    @pytest.mark.asyncio
    async def test_on_close_callback(self):
        called = []

        async def on_close(ctx, name):
            called.append(name)

        mw = A2ACircuitBreakerMiddleware(threshold=1, reset_after=0.01, on_close=on_close)
        await mw.on_tool_error(None, "remote", {}, RuntimeError("fail"))
        await asyncio.sleep(0.02)
        await mw.before_agent(None, "remote")
        await mw.after_agent(None, "remote")
        assert called == ["remote"]

    @pytest.mark.asyncio
    async def test_success_resets_failures(self):
        mw = A2ACircuitBreakerMiddleware(threshold=5)
        for _ in range(3):
            await mw.on_tool_error(None, "agent", {}, RuntimeError("fail"))
        assert mw._failures["agent"] == 3
        await mw.after_agent(None, "agent")
        assert mw._failures["agent"] == 0


# ======================================================================
# 4. A2ATimeoutMiddleware
# ======================================================================


class TestA2ATimeoutMiddleware:
    """Tests for A2ATimeoutMiddleware."""

    def test_creation_defaults(self):
        mw = A2ATimeoutMiddleware()
        assert mw._seconds == 30
        assert mw.agents is None

    def test_creation_custom(self):
        mw = A2ATimeoutMiddleware(seconds=120, agents="remote")
        assert mw._seconds == 120
        assert mw.agents == "remote"

    @pytest.mark.asyncio
    async def test_sets_deadline(self):
        mw = A2ATimeoutMiddleware(seconds=30)
        await mw.before_agent(None, "agent")
        assert "agent" in mw._deadlines
        assert mw._deadlines["agent"] > time.monotonic()

    @pytest.mark.asyncio
    async def test_cleans_up_deadline(self):
        mw = A2ATimeoutMiddleware(seconds=30)
        await mw.before_agent(None, "agent")
        await mw.after_agent(None, "agent")
        assert "agent" not in mw._deadlines

    @pytest.mark.asyncio
    async def test_raises_on_model_after_timeout(self):
        mw = A2ATimeoutMiddleware(seconds=0.01)
        await mw.before_agent(None, "agent")
        await asyncio.sleep(0.02)

        class FakeCtx:
            agent_name = "agent"

        with pytest.raises(TimeoutError, match="exceeded"):
            await mw.before_model(FakeCtx(), None)

    @pytest.mark.asyncio
    async def test_raises_on_tool_after_timeout(self):
        mw = A2ATimeoutMiddleware(seconds=0.01)
        await mw.before_agent(None, "agent")
        await asyncio.sleep(0.02)

        class FakeCtx:
            agent_name = "agent"

        with pytest.raises(TimeoutError, match="exceeded"):
            await mw.before_tool(FakeCtx(), "tool", {})

    @pytest.mark.asyncio
    async def test_no_raise_before_timeout(self):
        mw = A2ATimeoutMiddleware(seconds=30)
        await mw.before_agent(None, "agent")

        class FakeCtx:
            agent_name = "agent"

        result = await mw.before_model(FakeCtx(), None)
        assert result is None

    @pytest.mark.asyncio
    async def test_on_timeout_callback(self):
        called = []

        async def on_timeout(ctx, name, seconds):
            called.append((name, seconds))

        mw = A2ATimeoutMiddleware(seconds=0.01, on_timeout=on_timeout)
        await mw.before_agent(None, "agent")
        await asyncio.sleep(0.02)
        await mw.after_agent(None, "agent")
        assert called == [("agent", 0.01)]


# ======================================================================
# 5. M.a2a_* factory methods
# ======================================================================


class TestMFactories:
    """Tests for M.a2a_retry(), M.a2a_circuit_breaker(), M.a2a_timeout()."""

    def test_a2a_retry_returns_mcomposite(self):
        result = M.a2a_retry()
        assert isinstance(result, MComposite)
        assert len(result) == 1
        assert isinstance(result.to_stack()[0], A2ARetryMiddleware)

    def test_a2a_retry_with_params(self):
        result = M.a2a_retry(max_attempts=5, backoff=1.0)
        mw = result.to_stack()[0]
        assert mw.max_attempts == 5
        assert mw.backoff_base == 1.0

    def test_a2a_circuit_breaker_returns_mcomposite(self):
        result = M.a2a_circuit_breaker()
        assert isinstance(result, MComposite)
        assert len(result) == 1
        assert isinstance(result.to_stack()[0], A2ACircuitBreakerMiddleware)

    def test_a2a_circuit_breaker_with_params(self):
        result = M.a2a_circuit_breaker(threshold=10, reset_after=120)
        mw = result.to_stack()[0]
        assert mw._threshold == 10
        assert mw._reset_after == 120

    def test_a2a_timeout_returns_mcomposite(self):
        result = M.a2a_timeout()
        assert isinstance(result, MComposite)
        assert len(result) == 1
        assert isinstance(result.to_stack()[0], A2ATimeoutMiddleware)

    def test_a2a_timeout_with_params(self):
        result = M.a2a_timeout(seconds=120)
        mw = result.to_stack()[0]
        assert mw._seconds == 120

    def test_a2a_composition(self):
        """A2A middleware composes with | operator."""
        chain = M.a2a_retry() | M.a2a_circuit_breaker() | M.a2a_timeout()
        assert isinstance(chain, MComposite)
        assert len(chain) == 3

    def test_a2a_with_scope(self):
        """A2A middleware works with M.scope()."""
        scoped = M.scope("remote_agent", M.a2a_retry())
        assert isinstance(scoped, MComposite)
        assert len(scoped) == 1

    def test_a2a_mixed_with_generic(self):
        """A2A middleware mixes with generic middleware."""
        chain = M.a2a_retry() | M.log() | M.a2a_timeout()
        assert len(chain) == 3
