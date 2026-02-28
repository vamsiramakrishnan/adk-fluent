"""Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects."""

import pytest  # noqa: F401 (used inside test methods)

from adk_fluent.workflow import Pipeline


class TestPipelineBuilder:
    """Tests for Pipeline builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = Pipeline("test_name")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.sub_agents() returns the builder instance for chaining."""
        builder = Pipeline("test_name")
        result = builder.sub_agents([])
        assert result is builder

    def test_config_accumulation(self):
        """Setting .sub_agents() stores the value in builder._config."""
        builder = Pipeline("test_name")
        builder.sub_agents([])
        assert builder._config["sub_agents"] == []

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = Pipeline("test_name")
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")
