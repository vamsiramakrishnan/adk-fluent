"""Tests for .debug() — builder mechanics only (no LLM calls)."""
from adk_fluent.agent import Agent


class TestDebug:
    def test_stores_flag(self):
        a = Agent("test").debug()
        assert a._config["_debug"] is True

    def test_returns_self(self):
        a = Agent("test")
        result = a.debug()
        assert result is a

    def test_debug_false(self):
        a = Agent("test").debug(False)
        assert a._config["_debug"] is False

    def test_chainable(self):
        a = Agent("test").model("gemini-2.5-flash").debug().instruct("Go")
        assert a._config["_debug"] is True
        assert a._config["model"] == "gemini-2.5-flash"
        assert a._config["instruction"] == "Go"

    def test_excluded_from_repr(self):
        a = Agent("test").debug()
        r = repr(a)
        assert "_debug" not in r

    def test_excluded_from_to_dict(self):
        a = Agent("test").debug()
        d = a.to_dict()
        assert "_debug" not in d["config"]
