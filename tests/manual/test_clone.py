"""Tests for deep_clone_builder and .clone() functionality."""

from adk_fluent._helpers import deep_clone_builder
from adk_fluent.agent import Agent


class TestDeepCloneBuilder:
    """Tests for the deep_clone_builder helper function."""

    def test_clone_returns_new_instance(self):
        """clone returns a new builder instance, not the same object."""
        original = Agent("original")
        cloned = deep_clone_builder(original, "cloned")
        assert cloned is not original

    def test_clone_has_new_name(self):
        """clone sets the new name in _config."""
        original = Agent("original")
        cloned = deep_clone_builder(original, "cloned")
        assert cloned._config["name"] == "cloned"
        assert original._config["name"] == "original"

    def test_clone_preserves_config(self):
        """clone preserves existing config values from the original."""
        original = Agent("original")
        original._config["description"] = "test description"
        original._config["instruction"] = "do things"
        cloned = deep_clone_builder(original, "cloned")
        assert cloned._config["description"] == "test description"
        assert cloned._config["instruction"] == "do things"

    def test_clone_is_deep_copy(self):
        """Modifying clone config does not affect original."""
        original = Agent("original")
        original._config["description"] = "original desc"
        cloned = deep_clone_builder(original, "cloned")
        cloned._config["description"] = "cloned desc"
        assert original._config["description"] == "original desc"

    def test_clone_copies_callbacks(self):
        """Modifying clone callbacks does not affect original."""
        fn1 = lambda ctx: None
        original = Agent("original")
        original._callbacks["before_model_callback"].append(fn1)

        cloned = deep_clone_builder(original, "cloned")
        fn2 = lambda ctx: None
        cloned._callbacks["before_model_callback"].append(fn2)

        assert len(original._callbacks["before_model_callback"]) == 1
        assert len(cloned._callbacks["before_model_callback"]) == 2

    def test_clone_copies_lists(self):
        """Modifying clone lists does not affect original."""
        original = Agent("original")
        original._lists["tools"].append("tool_a")

        cloned = deep_clone_builder(original, "cloned")
        cloned._lists["tools"].append("tool_b")

        assert original._lists["tools"] == ["tool_a"]
        assert cloned._lists["tools"] == ["tool_a", "tool_b"]

    def test_clone_returns_same_builder_type(self):
        """clone returns an instance of the same builder class."""
        original = Agent("original")
        cloned = deep_clone_builder(original, "cloned")
        assert type(cloned) is Agent
