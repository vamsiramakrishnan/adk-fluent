"""Tests for .output() — structured output builder mechanics (no LLM calls)."""

from adk_fluent.agent import Agent


class FakeSchema:
    """Stand-in for a Pydantic model class."""

    pass


class TestOutput:
    def test_stores_schema_in_config(self):
        a = Agent("test").output(FakeSchema)
        assert a._config["_output_schema"] is FakeSchema

    def test_returns_self(self):
        a = Agent("test")
        result = a.output(FakeSchema)
        assert result is a

    def test_chainable(self):
        a = Agent("test").model("gemini-2.5-flash").output(FakeSchema).instruct("Go")
        assert a._config["_output_schema"] is FakeSchema
        assert a._config["model"] == "gemini-2.5-flash"
        assert a._config["instruction"] == "Go"

    def test_excluded_from_to_dict(self):
        a = Agent("test").output(FakeSchema)
        d = a.to_dict()
        # Internal _ fields should be excluded from config
        assert "_output_schema" not in d["config"]

    def test_excluded_from_repr(self):
        a = Agent("test").output(FakeSchema)
        r = repr(a)
        assert "_output_schema" not in r
        assert "FakeSchema" not in r
