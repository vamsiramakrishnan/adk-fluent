"""Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects."""

import pytest  # noqa: F401 (used inside test methods)

from adk_fluent.agent import Agent


class TestAgentBuilder:
    """Tests for Agent builder mechanics (no .build() calls)."""
    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = Agent('test_name')
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.describe() returns the builder instance for chaining."""
        builder = Agent('test_name')
        result = builder.describe("test_value")
        assert result is builder

    def test_config_accumulation(self):
        """Setting .model() stores the value in builder._config."""
        builder = Agent('test_name')
        builder.model("test_value")
        assert builder._config["model"] == "test_value"

    def test_callback_accumulation(self):
        """Multiple .before_model() calls accumulate in builder._callbacks."""
        fn1 = lambda ctx: None
        fn2 = lambda ctx: None
        builder = (
            Agent('test_name')
            .before_model(fn1)
            .before_model(fn2)
        )
        assert builder._callbacks["before_model_callback"] == [fn1, fn2]

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = Agent('test_name')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")
