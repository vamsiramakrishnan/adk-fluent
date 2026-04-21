"""Tests for .run.map() — verify method exists (no LLM calls)."""

from adk_fluent.agent import Agent


class TestMap:
    def test_map_method_exists_and_callable(self):
        a = Agent("test")
        assert callable(a.run.map)
