"""Tests for built-in middleware implementations."""

import asyncio

from adk_fluent.middleware import RetryMiddleware, StructuredLogMiddleware


def test_retry_middleware_is_middleware():
    from adk_fluent.middleware import Middleware

    assert isinstance(RetryMiddleware(), Middleware)


def test_retry_middleware_defaults():
    mw = RetryMiddleware()
    assert mw.max_attempts == 3
    assert mw.backoff_base == 1.0


def test_retry_middleware_custom_config():
    mw = RetryMiddleware(max_attempts=5, backoff_base=0.5)
    assert mw.max_attempts == 5
    assert mw.backoff_base == 0.5


def test_retry_middleware_on_model_error_returns_none():
    mw = RetryMiddleware(max_attempts=3, backoff_base=0.0)

    async def run():
        return await mw.on_model_error(ctx=None, request=None, error=ValueError("test"))

    assert asyncio.run(run()) is None


def test_retry_middleware_on_tool_error_returns_none():
    mw = RetryMiddleware(max_attempts=3, backoff_base=0.0)

    async def run():
        return await mw.on_tool_error(ctx=None, tool_name="search", args={}, error=ValueError("test"))

    assert asyncio.run(run()) is None


def test_structured_log_is_middleware():
    from adk_fluent.middleware import Middleware

    assert isinstance(StructuredLogMiddleware(), Middleware)


def test_structured_log_captures_events():
    mw = StructuredLogMiddleware()

    async def run():
        await mw.before_model(ctx=None, request="test_request")
        await mw.after_model(ctx=None, response="test_response")
        await mw.before_agent(ctx=None, agent_name="agent1")
        await mw.after_agent(ctx=None, agent_name="agent1")

    asyncio.run(run())
    assert len(mw.log) == 4
    assert mw.log[0]["event"] == "before_model"
    assert mw.log[2]["agent_name"] == "agent1"


def test_structured_log_never_short_circuits():
    mw = StructuredLogMiddleware()

    async def run():
        r1 = await mw.before_model(ctx=None, request="req")
        r2 = await mw.after_model(ctx=None, response="resp")
        r3 = await mw.before_tool(ctx=None, tool_name="t", args={})
        r4 = await mw.after_tool(ctx=None, tool_name="t", args={}, result={})
        return [r1, r2, r3, r4]

    assert all(r is None for r in asyncio.run(run()))


def test_middleware_importable_from_top_level():
    from adk_fluent import Middleware, RetryMiddleware, StructuredLogMiddleware

    assert Middleware is not None
    assert RetryMiddleware is not None
    assert StructuredLogMiddleware is not None
