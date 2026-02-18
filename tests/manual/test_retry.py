"""Tests for .retry() and .fallback() — builder mechanics only (no LLM calls)."""

from adk_fluent.agent import Agent


class TestRetry:
    def test_stores_config_with_defaults(self):
        a = Agent("test").retry()
        assert a._config["_retry"] == {"max_attempts": 3, "backoff": 1.0}

    def test_returns_self(self):
        a = Agent("test")
        result = a.retry()
        assert result is a

    def test_custom_values(self):
        a = Agent("test").retry(max_attempts=5, backoff=2.0)
        assert a._config["_retry"]["max_attempts"] == 5
        assert a._config["_retry"]["backoff"] == 2.0

    def test_chainable(self):
        a = Agent("test").model("gemini-2.5-flash").retry(max_attempts=2).instruct("Go")
        assert a._config["_retry"]["max_attempts"] == 2
        assert a._config["model"] == "gemini-2.5-flash"
        assert a._config["instruction"] == "Go"


class TestFallback:
    def test_stores_model_name(self):
        a = Agent("test").fallback("gpt-4o")
        assert a._config["_fallbacks"] == ["gpt-4o"]

    def test_returns_self(self):
        a = Agent("test")
        result = a.fallback("gpt-4o")
        assert result is a

    def test_multiple_fallbacks_accumulate(self):
        a = Agent("test").fallback("gpt-4o").fallback("claude-3-opus")
        assert a._config["_fallbacks"] == ["gpt-4o", "claude-3-opus"]


class TestRetryFallbackCombined:
    def test_retry_and_fallback_together(self):
        a = Agent("test").model("gemini-2.5-flash").retry(max_attempts=3).fallback("gpt-4o")
        assert a._config["_retry"]["max_attempts"] == 3
        assert a._config["_fallbacks"] == ["gpt-4o"]
        assert a._config["model"] == "gemini-2.5-flash"

    def test_internal_fields_excluded_from_repr(self):
        a = Agent("test").retry().fallback("gpt-4o")
        r = repr(a)
        assert "_retry" not in r
        assert "_fallbacks" not in r
