"""Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects."""

import pytest  # noqa: F401 (used inside test methods)

from adk_fluent.planner import BasePlanner, BuiltInPlanner, PlanReActPlanner


class TestBasePlannerBuilder:
    """Tests for BasePlanner builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BasePlanner("test_args", "test_kwargs")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BasePlanner("test_args", "test_kwargs")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestBuiltInPlannerBuilder:
    """Tests for BuiltInPlanner builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BuiltInPlanner("test_thinking_config")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BuiltInPlanner("test_thinking_config")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestPlanReActPlannerBuilder:
    """Tests for PlanReActPlanner builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = PlanReActPlanner("test_args", "test_kwargs")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = PlanReActPlanner("test_args", "test_kwargs")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")
