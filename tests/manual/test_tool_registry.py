"""Tests for ToolRegistry -- BM25-indexed tool catalog."""

from __future__ import annotations


def _make_fn(name: str, doc: str):
    """Create a callable with a given name and docstring."""

    def fn(**kwargs):
        pass

    fn.__name__ = name
    fn.__doc__ = doc
    return fn


class TestToolRegistry:
    def test_register_callable(self):
        from adk_fluent._tool_registry import ToolRegistry

        def search(query: str) -> str:
            """Search the web for information."""
            return query

        reg = ToolRegistry()
        reg.register(search)
        assert reg.get_tool("search") is not None

    def test_register_base_tool(self):
        from google.adk.tools.function_tool import FunctionTool

        from adk_fluent._tool_registry import ToolRegistry

        def my_fn(x: str) -> str:
            return x

        tool = FunctionTool(func=my_fn)
        reg = ToolRegistry()
        reg.register(tool)
        assert reg.get_tool("my_fn") is not None

    def test_register_all(self):
        from adk_fluent._tool_registry import ToolRegistry

        fn1 = _make_fn("search", "Search the web.")
        fn2 = _make_fn("email", "Send an email.")
        reg = ToolRegistry()
        reg.register_all(fn1, fn2)
        assert reg.get_tool("search") is not None
        assert reg.get_tool("email") is not None

    def test_search_substring_fallback(self):
        from adk_fluent._tool_registry import ToolRegistry

        fn1 = _make_fn("web_search", "Search the web for information.")
        fn2 = _make_fn("send_email", "Send an email message.")
        fn3 = _make_fn("calculator", "Perform math calculations.")
        reg = ToolRegistry()
        reg.register_all(fn1, fn2, fn3)
        results = reg.search("search web", top_k=2)
        assert len(results) <= 2
        assert any("web_search" in r["name"] for r in results)

    def test_from_tools_factory(self):
        from adk_fluent._tool_registry import ToolRegistry

        fn1 = _make_fn("a", "Tool A")
        fn2 = _make_fn("b", "Tool B")
        reg = ToolRegistry.from_tools(fn1, fn2)
        assert reg.get_tool("a") is not None
        assert reg.get_tool("b") is not None

    def test_get_tool_not_found(self):
        from adk_fluent._tool_registry import ToolRegistry

        reg = ToolRegistry()
        assert reg.get_tool("nonexistent") is None

    def test_search_empty_registry(self):
        from adk_fluent._tool_registry import ToolRegistry

        reg = ToolRegistry()
        results = reg.search("anything")
        assert results == []

    def test_search_returns_dicts(self):
        from adk_fluent._tool_registry import ToolRegistry

        fn = _make_fn("tool_a", "A useful tool.")
        reg = ToolRegistry.from_tools(fn)
        results = reg.search("useful", top_k=1)
        assert len(results) == 1
        assert "name" in results[0]
        assert "description" in results[0]


class TestSearchAwareAfterTool:
    def test_compress_large_result_small(self):
        from adk_fluent._tool_registry import compress_large_result

        small = "hello"
        assert compress_large_result(small, threshold=100) == small

    def test_compress_large_result_large(self):
        from adk_fluent._tool_registry import compress_large_result

        large = "x" * 200
        result = compress_large_result(large, threshold=100)
        assert len(result) < len(large)
        assert "file" in result.lower() or "result" in result.lower()

    def test_result_variator(self):
        from adk_fluent._tool_registry import _ResultVariator

        v = _ResultVariator()
        r1 = v.vary("result text", 0)
        r2 = v.vary("result text", 1)
        assert "result text" in r1
        assert "result text" in r2
        assert r1 != r2

    def test_result_variator_wraps_around(self):
        from adk_fluent._tool_registry import _ResultVariator

        v = _ResultVariator()
        r0 = v.vary("data", 0)
        r4 = v.vary("data", 4)
        assert r0 == r4  # wraps around after 4 prefixes
