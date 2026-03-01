"""Tests for TComposite — composable tool chain."""

from __future__ import annotations


class TestTComposite:
    def test_init_empty(self):
        from adk_fluent._tools import TComposite

        tc = TComposite()
        assert len(tc) == 0
        assert tc.to_tools() == []

    def test_init_with_items(self):
        from adk_fluent._tools import TComposite

        tc = TComposite(["a", "b"])
        assert len(tc) == 2
        assert tc.to_tools() == ["a", "b"]

    def test_or_two_composites(self):
        from adk_fluent._tools import TComposite

        a = TComposite(["x"])
        b = TComposite(["y"])
        c = a | b
        assert len(c) == 2
        assert c.to_tools() == ["x", "y"]

    def test_or_composite_and_raw(self):
        from adk_fluent._tools import TComposite

        a = TComposite(["x"])
        c = a | "y"
        assert len(c) == 2
        assert c.to_tools() == ["x", "y"]

    def test_ror_raw_and_composite(self):
        from adk_fluent._tools import TComposite

        b = TComposite(["y"])
        c = "x" | b
        assert len(c) == 2
        assert c.to_tools() == ["x", "y"]

    def test_repr(self):
        from adk_fluent._tools import TComposite

        tc = TComposite(["a", "b"])
        r = repr(tc)
        assert "TComposite" in r
        assert "str" in r

    def test_chain_three(self):
        from adk_fluent._tools import TComposite

        a = TComposite(["x"])
        b = TComposite(["y"])
        c = TComposite(["z"])
        result = a | b | c
        assert len(result) == 3
        assert result.to_tools() == ["x", "y", "z"]

    def test_to_tools_returns_copy(self):
        from adk_fluent._tools import TComposite

        tc = TComposite(["x"])
        tools = tc.to_tools()
        tools.append("extra")
        assert len(tc) == 1  # original unchanged


class TestTFactory:
    def test_fn_wraps_callable(self):
        from adk_fluent._tools import T

        def my_tool(query: str) -> str:
            return query

        tc = T.fn(my_tool)
        assert len(tc) == 1
        tools = tc.to_tools()
        assert len(tools) == 1
        from google.adk.tools.function_tool import FunctionTool

        assert isinstance(tools[0], FunctionTool)

    def test_fn_with_confirm(self):
        from adk_fluent._tools import T

        def risky(action: str) -> str:
            return action

        tc = T.fn(risky, confirm=True)
        tools = tc.to_tools()
        from google.adk.tools.function_tool import FunctionTool

        assert isinstance(tools[0], FunctionTool)

    def test_fn_passthrough_base_tool(self):
        from unittest.mock import MagicMock

        from google.adk.tools.base_tool import BaseTool

        from adk_fluent._tools import T

        mock_tool = MagicMock(spec=BaseTool)
        tc = T.fn(mock_tool)
        tools = tc.to_tools()
        assert tools[0] is mock_tool

    def test_agent_wraps_builder(self):
        from adk_fluent import Agent
        from adk_fluent._tools import T

        a = Agent("helper").instruct("Help")
        tc = T.agent(a)
        assert len(tc) == 1
        from google.adk.tools.agent_tool import AgentTool

        assert isinstance(tc.to_tools()[0], AgentTool)

    def test_toolset_wraps(self):
        from unittest.mock import MagicMock

        from google.adk.tools.base_toolset import BaseToolset

        from adk_fluent._tools import T

        mock_ts = MagicMock(spec=BaseToolset)
        tc = T.toolset(mock_ts)
        assert len(tc) == 1
        assert tc.to_tools()[0] is mock_ts

    def test_google_search(self):
        from adk_fluent._tools import T

        tc = T.google_search()
        assert len(tc) == 1

    def test_schema_attaches(self):
        from adk_fluent._tools import T, _SchemaMarker

        class FakeSchema:
            pass

        tc = T.schema(FakeSchema)
        assert len(tc) == 1
        item = tc.to_tools()[0]
        assert isinstance(item, _SchemaMarker)
        assert item._schema_cls is FakeSchema

    def test_compose_fn_and_google_search(self):
        from adk_fluent._tools import T

        def my_tool(q: str) -> str:
            return q

        tc = T.fn(my_tool) | T.google_search()
        assert len(tc) == 2


class TestTBuilderIntegration:
    def test_tools_accepts_tcomposite(self):
        from adk_fluent import Agent
        from adk_fluent._tools import T

        def search(query: str) -> str:
            return query

        a = Agent("helper").tools(T.fn(search))
        ir = a.to_ir()
        assert len(ir.tools) >= 1

    def test_tools_accepts_list(self):
        """Existing behavior: .tools([list]) still works."""
        from adk_fluent import Agent

        def search(query: str) -> str:
            return query

        a = Agent("helper").tools([search])
        ir = a.to_ir()
        assert len(ir.tools) >= 1

    def test_tools_tcomposite_with_schema_extracts(self):
        from adk_fluent import Agent
        from adk_fluent._tools import T, _SchemaMarker

        class FakeSchema:
            pass

        def search(query: str) -> str:
            return query

        a = Agent("helper").tools(T.fn(search) | T.schema(FakeSchema))
        ir = a.to_ir()
        assert ir.tool_schema is FakeSchema
        # Schema marker should NOT be in tools list
        for tool in ir.tools:
            assert not isinstance(tool, _SchemaMarker)

    def test_tool_and_tools_combine(self):
        """T.fn() via .tools() and .tool() via individual add both contribute."""
        from adk_fluent import Agent
        from adk_fluent._tools import T

        def search(query: str) -> str:
            return query

        def email(to: str) -> str:
            return to

        a = Agent("helper").tool(search).tools(T.fn(email))
        ir = a.to_ir()
        assert len(ir.tools) >= 2


class TestTSearch:
    def test_t_search_returns_tcomposite(self):
        from adk_fluent._tool_registry import ToolRegistry
        from adk_fluent._tools import T, TComposite

        def search(query: str) -> str:
            """Search."""
            return query

        registry = ToolRegistry.from_tools(search)
        tc = T.search(registry)
        assert isinstance(tc, TComposite)
        assert len(tc) == 1

    def test_t_search_contains_search_toolset(self):
        from adk_fluent._tool_registry import SearchToolset, ToolRegistry
        from adk_fluent._tools import T

        def search(query: str) -> str:
            """Search."""
            return query

        registry = ToolRegistry.from_tools(search)
        tc = T.search(registry)
        tools = tc.to_tools()
        assert isinstance(tools[0], SearchToolset)


class TestTExports:
    def test_import_from_adk_fluent(self):
        from adk_fluent import T, TComposite

        assert T is not None
        assert TComposite is not None

    def test_import_from_prelude(self):
        from adk_fluent.prelude import T, TComposite

        assert T is not None
        assert TComposite is not None

    def test_import_registry_from_adk_fluent(self):
        from adk_fluent import ToolRegistry

        assert ToolRegistry is not None

    def test_import_search_toolset(self):
        from adk_fluent import SearchToolset

        assert SearchToolset is not None

    def test_import_search_aware_after_tool(self):
        from adk_fluent import search_aware_after_tool

        assert search_aware_after_tool is not None
