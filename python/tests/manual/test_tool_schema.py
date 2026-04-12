"""Tests for ToolSchema — typed tool declarations."""

from __future__ import annotations

from typing import Annotated

from adk_fluent._schema_base import Confirms, Param, Reads, Timeout, Writes
from adk_fluent._tool_schema import ToolSchema


class SearchTools(ToolSchema):
    query: Annotated[str, Reads()]
    user_tier: Annotated[str, Reads(scope="user")]
    results: Annotated[list, Writes()]
    search_count: Annotated[int, Writes(scope="temp")]
    max_results: Annotated[int, Param()] = 10


class ConfirmableTool(ToolSchema):
    action: Annotated[str, Reads()]
    confirm: Annotated[bool, Confirms("Are you sure?")] = False
    limit: Annotated[float, Timeout(60)] = 60.0


class EmptyToolSchema(ToolSchema):
    pass


class TestToolSchemaFields:
    def test_reads_keys(self):
        assert SearchTools.reads_keys() == frozenset({"query", "user:user_tier"})

    def test_writes_keys(self):
        assert SearchTools.writes_keys() == frozenset({"results", "temp:search_count"})

    def test_param_names(self):
        assert SearchTools.param_names() == frozenset({"max_results"})

    def test_requires_confirmation(self):
        assert ConfirmableTool.requires_confirmation() is True
        assert SearchTools.requires_confirmation() is False

    def test_timeout_seconds(self):
        assert ConfirmableTool.timeout_seconds() == 60.0
        assert SearchTools.timeout_seconds() is None

    def test_empty_schema(self):
        assert EmptyToolSchema.reads_keys() == frozenset()
        assert EmptyToolSchema.writes_keys() == frozenset()
        assert EmptyToolSchema.param_names() == frozenset()

    def test_field_introspection(self):
        assert len(SearchTools._fields) == 5
        assert "query" in SearchTools._fields

    def test_dir_includes_fields(self):
        d = dir(SearchTools)
        assert "query" in d
        assert "results" in d


class TestToolSchemaBuilderIntegration:
    def test_tool_schema_on_agent(self):
        from adk_fluent import Agent

        a = Agent("search").tool_schema(SearchTools).instruct("Search")
        ir = a.to_ir()
        assert ir.tool_schema is SearchTools

    def test_tool_schema_adds_to_reads_keys(self):
        from adk_fluent import Agent

        a = Agent("search").tool_schema(SearchTools).instruct("Search")
        ir = a.to_ir()
        assert "query" in ir.reads_keys
        assert "user:user_tier" in ir.reads_keys

    def test_tool_schema_adds_to_writes_keys(self):
        from adk_fluent import Agent

        a = Agent("search").tool_schema(SearchTools).instruct("Search")
        ir = a.to_ir()
        assert "results" in ir.writes_keys
        assert "temp:search_count" in ir.writes_keys
