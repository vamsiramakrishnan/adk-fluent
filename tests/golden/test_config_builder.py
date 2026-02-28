"""Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects."""

import pytest  # noqa: F401 (used inside test methods)

from adk_fluent.config import RunConfig


class TestRunConfigBuilder:
    """Tests for RunConfig builder mechanics (no .build() calls)."""
    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = RunConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.max_llm_calls() returns the builder instance for chaining."""
        builder = RunConfig()
        result = builder.max_llm_calls(42)
        assert result is builder

    def test_config_accumulation(self):
        """Setting .max_llm_calls() stores the value in builder._config."""
        builder = RunConfig()
        builder.max_llm_calls(42)
        assert builder._config["max_llm_calls"] == 42

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = RunConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")
