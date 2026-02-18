"""Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects."""

import pytest  # noqa: F401 (used inside test methods)

from adk_fluent.executor import (
    AgentEngineSandboxCodeExecutor,
    BaseCodeExecutor,
    BuiltInCodeExecutor,
    UnsafeLocalCodeExecutor,
    VertexAiCodeExecutor,
)


class TestAgentEngineSandboxCodeExecutorBuilder:
    """Tests for AgentEngineSandboxCodeExecutor builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = AgentEngineSandboxCodeExecutor()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.optimize_data_file() returns the builder instance for chaining."""
        builder = AgentEngineSandboxCodeExecutor()
        result = builder.optimize_data_file(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .optimize_data_file() stores the value in builder._config."""
        builder = AgentEngineSandboxCodeExecutor()
        builder.optimize_data_file(True)
        assert builder._config["optimize_data_file"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = AgentEngineSandboxCodeExecutor()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestBaseCodeExecutorBuilder:
    """Tests for BaseCodeExecutor builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BaseCodeExecutor()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.optimize_data_file() returns the builder instance for chaining."""
        builder = BaseCodeExecutor()
        result = builder.optimize_data_file(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .optimize_data_file() stores the value in builder._config."""
        builder = BaseCodeExecutor()
        builder.optimize_data_file(True)
        assert builder._config["optimize_data_file"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BaseCodeExecutor()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestBuiltInCodeExecutorBuilder:
    """Tests for BuiltInCodeExecutor builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BuiltInCodeExecutor()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.optimize_data_file() returns the builder instance for chaining."""
        builder = BuiltInCodeExecutor()
        result = builder.optimize_data_file(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .optimize_data_file() stores the value in builder._config."""
        builder = BuiltInCodeExecutor()
        builder.optimize_data_file(True)
        assert builder._config["optimize_data_file"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BuiltInCodeExecutor()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestUnsafeLocalCodeExecutorBuilder:
    """Tests for UnsafeLocalCodeExecutor builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = UnsafeLocalCodeExecutor()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.optimize_data_file() returns the builder instance for chaining."""
        builder = UnsafeLocalCodeExecutor()
        result = builder.optimize_data_file(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .optimize_data_file() stores the value in builder._config."""
        builder = UnsafeLocalCodeExecutor()
        builder.optimize_data_file(True)
        assert builder._config["optimize_data_file"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = UnsafeLocalCodeExecutor()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestVertexAiCodeExecutorBuilder:
    """Tests for VertexAiCodeExecutor builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = VertexAiCodeExecutor()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = VertexAiCodeExecutor()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")
