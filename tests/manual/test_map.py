"""Tests for .map() and .map_async() — verify methods exist (no LLM calls)."""
from adk_fluent.agent import Agent


class TestMap:
    def test_map_method_exists_and_callable(self):
        a = Agent("test")
        assert hasattr(a, "map")
        assert callable(a.map)

    def test_map_async_method_exists(self):
        a = Agent("test")
        assert hasattr(a, "map_async")
        assert callable(a.map_async)
