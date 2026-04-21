"""Tests for .run.map() and .run.map_async() — verify methods exist (no LLM calls)."""

from adk_fluent.agent import Agent


class TestMap:
    def test_map_method_exists_and_callable(self):
        a = Agent("test")
        assert callable(a.run.map)

    def test_map_async_method_exists(self):
        a = Agent("test")
        assert callable(a.run.map_async)
