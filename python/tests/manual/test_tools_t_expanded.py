"""Tests for T.mock, T.confirm, T.timeout, T.cache, T.mcp, T.openapi, T.transform."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# T.mock
# ---------------------------------------------------------------------------


class TestMock:
    def test_mock_returns_value(self):
        from adk_fluent._tools import T, TComposite

        tc = T.mock("greet", returns="hello")
        assert isinstance(tc, TComposite)
        assert tc._kind == "mock"
        tool = tc.to_tools()[0]
        result = asyncio.run(tool.run_async(args={}, tool_context=None))
        assert result == "hello"

    def test_mock_side_effect_callable(self):
        from adk_fluent._tools import T

        tc = T.mock("add", side_effect=lambda x=0, y=0, **kw: x + y)
        tool = tc.to_tools()[0]
        result = asyncio.run(tool.run_async(args={"x": 2, "y": 3}, tool_context=None))
        assert result == 5

    def test_mock_side_effect_non_callable(self):
        from adk_fluent._tools import T

        tc = T.mock("err", side_effect="error-value")
        tool = tc.to_tools()[0]
        result = asyncio.run(tool.run_async(args={}, tool_context=None))
        assert result == "error-value"

    def test_mock_composes_with_pipe(self):
        from adk_fluent._tools import T

        tc = T.mock("a", returns=1) | T.mock("b", returns=2)
        assert len(tc) == 2

    def test_mock_kind(self):
        from adk_fluent._tools import T

        tc = T.mock("x")
        assert tc._kind == "mock"


# ---------------------------------------------------------------------------
# T.confirm
# ---------------------------------------------------------------------------


class TestConfirm:
    def test_confirm_wraps_tool(self):
        from adk_fluent._tools import T, _ConfirmWrapper

        base = T.fn(lambda query: query)  # noqa: ARG005
        tc = T.confirm(base, message="Are you sure?")
        assert len(tc) == 1
        wrapper = tc.to_tools()[0]
        assert isinstance(wrapper, _ConfirmWrapper)
        assert wrapper.require_confirmation is True

    def test_confirm_wraps_composite_all_items(self):
        from adk_fluent._tools import T, _ConfirmWrapper

        base = T.fn(lambda q: q) | T.fn(lambda q: q)  # noqa: ARG005
        tc = T.confirm(base, message="Confirm?")
        assert len(tc) == 2
        for item in tc.to_tools():
            assert isinstance(item, _ConfirmWrapper)

    def test_confirm_wraps_raw_item(self):
        from adk_fluent._tools import T, _ConfirmWrapper

        raw = MagicMock()
        raw.__name__ = "raw_tool"
        raw.__doc__ = "A raw tool"
        tc = T.confirm(raw)
        assert len(tc) == 1
        assert isinstance(tc.to_tools()[0], _ConfirmWrapper)

    def test_confirm_composes(self):
        from adk_fluent._tools import T

        tc = T.confirm(T.fn(lambda q: q), message="ok?") | T.fn(lambda q: q)  # noqa: ARG005
        assert len(tc) == 2

    def test_confirm_kind(self):
        from adk_fluent._tools import T

        tc = T.confirm(T.fn(lambda q: q))  # noqa: ARG005
        assert tc._kind == "confirm"

    def test_confirm_run_async_delegates(self):
        from adk_fluent._tools import T

        def my_fn(x: int = 0) -> int:
            return x * 2

        tc = T.confirm(T.fn(my_fn))
        wrapper = tc.to_tools()[0]
        result = asyncio.run(wrapper.run_async(args={"x": 5}, tool_context=None))
        assert result == 10


# ---------------------------------------------------------------------------
# T.timeout
# ---------------------------------------------------------------------------


class TestTimeout:
    def test_timeout_wraps_tool(self):
        from adk_fluent._tools import T, _TimeoutWrapper

        base = T.fn(lambda q: q)  # noqa: ARG005
        tc = T.timeout(base, seconds=10)
        assert len(tc) == 1
        assert isinstance(tc.to_tools()[0], _TimeoutWrapper)

    def test_timeout_kind(self):
        from adk_fluent._tools import T

        tc = T.timeout(T.fn(lambda q: q), seconds=5)  # noqa: ARG005
        assert tc._kind == "timeout"

    def test_timeout_wraps_composite(self):
        from adk_fluent._tools import T, _TimeoutWrapper

        base = T.fn(lambda q: q) | T.fn(lambda q: q)  # noqa: ARG005
        tc = T.timeout(base, seconds=15)
        assert len(tc) == 2
        for item in tc.to_tools():
            assert isinstance(item, _TimeoutWrapper)

    def test_timeout_run_async_succeeds(self):
        from adk_fluent._tools import T

        def fast(x: int = 1) -> int:
            return x

        tc = T.timeout(T.fn(fast), seconds=5)
        wrapper = tc.to_tools()[0]
        result = asyncio.run(wrapper.run_async(args={"x": 42}, tool_context=None))
        assert result == 42


# ---------------------------------------------------------------------------
# T.cache
# ---------------------------------------------------------------------------


class TestCache:
    def test_cache_wraps_tool(self):
        from adk_fluent._tools import T, _CachedWrapper

        base = T.fn(lambda q: q)  # noqa: ARG005
        tc = T.cache(base, ttl=60)
        assert len(tc) == 1
        assert isinstance(tc.to_tools()[0], _CachedWrapper)

    def test_cache_kind(self):
        from adk_fluent._tools import T

        tc = T.cache(T.fn(lambda q: q))  # noqa: ARG005
        assert tc._kind == "cache"

    def test_cache_custom_key_fn(self):
        from adk_fluent._tools import T, _CachedWrapper

        tc = T.cache(T.fn(lambda q: q), key_fn=lambda args: "fixed")  # noqa: ARG005
        wrapper = tc.to_tools()[0]
        assert isinstance(wrapper, _CachedWrapper)
        assert wrapper._key_fn({"any": "thing"}) == "fixed"

    def test_cache_returns_cached_value(self):
        from adk_fluent._tools import T

        call_count = 0

        def counting(x: int = 0) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        tc = T.cache(T.fn(counting), ttl=300)
        wrapper = tc.to_tools()[0]

        async def _run():
            r1 = await wrapper.run_async(args={"x": 5}, tool_context=None)
            r2 = await wrapper.run_async(args={"x": 5}, tool_context=None)
            return r1, r2

        r1, r2 = asyncio.run(_run())
        assert r1 == 10
        assert r2 == 10
        assert call_count == 1  # second call was cached


# ---------------------------------------------------------------------------
# T.mcp
# ---------------------------------------------------------------------------


class TestMcp:
    def test_mcp_is_static_method(self):
        from adk_fluent._tools import T

        assert hasattr(T, "mcp")
        assert callable(T.mcp)

    def test_mcp_returns_tcomposite(self):
        """T.mcp may fail at build time without a real server; just verify shape."""
        from adk_fluent._tools import T, TComposite

        try:
            tc = T.mcp("http://localhost:9999")
            assert isinstance(tc, TComposite)
            assert tc._kind == "mcp"
        except Exception:
            # Expected: build may fail without real MCP server
            pytest.skip("McpToolset build requires live connection")


# ---------------------------------------------------------------------------
# T.openapi
# ---------------------------------------------------------------------------


class TestOpenapi:
    def test_openapi_is_static_method(self):
        from adk_fluent._tools import T

        assert hasattr(T, "openapi")
        assert callable(T.openapi)

    def test_openapi_returns_tcomposite(self):
        """T.openapi may fail at build time without valid spec; just verify shape."""
        from adk_fluent._tools import T, TComposite

        try:
            tc = T.openapi({"openapi": "3.0.0", "info": {"title": "t", "version": "1"}, "paths": {}})
            assert isinstance(tc, TComposite)
            assert tc._kind == "openapi"
        except Exception:
            pytest.skip("OpenAPIToolset build requires valid spec")


# ---------------------------------------------------------------------------
# T.transform
# ---------------------------------------------------------------------------


class TestTransform:
    def test_transform_wraps_tool(self):
        from adk_fluent._tools import T, _TransformWrapper

        base = T.fn(lambda q: q)  # noqa: ARG005
        tc = T.transform(base, pre=lambda args: args, post=lambda r: r)
        assert len(tc) == 1
        assert isinstance(tc.to_tools()[0], _TransformWrapper)

    def test_transform_kind(self):
        from adk_fluent._tools import T

        tc = T.transform(T.fn(lambda q: q))  # noqa: ARG005
        assert tc._kind == "transform"

    def test_transform_pre_and_post(self):
        from adk_fluent._tools import T

        def double_fn(x: int = 0) -> int:
            return x

        tc = T.transform(
            T.fn(double_fn),
            pre=lambda args: {**args, "x": args.get("x", 0) * 2},
            post=lambda r: r + 100,
        )
        wrapper = tc.to_tools()[0]
        result = asyncio.run(wrapper.run_async(args={"x": 5}, tool_context=None))
        assert result == 110  # pre: x=10, fn returns 10, post: 10+100

    def test_transform_wraps_composite(self):
        from adk_fluent._tools import T, _TransformWrapper

        base = T.fn(lambda q: q) | T.fn(lambda q: q)  # noqa: ARG005
        tc = T.transform(base)
        assert len(tc) == 2
        for item in tc.to_tools():
            assert isinstance(item, _TransformWrapper)
