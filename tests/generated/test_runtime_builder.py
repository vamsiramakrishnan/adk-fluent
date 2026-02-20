"""Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects."""

import pytest  # noqa: F401 (used inside test methods)

from adk_fluent.runtime import App, InMemoryRunner, Runner


class TestAppBuilder:
    """Tests for App builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = App("test_name", "test_root_agent")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.plugins() returns the builder instance for chaining."""
        builder = App("test_name", "test_root_agent")
        result = builder.plugins([])
        assert result is builder

    def test_config_accumulation(self):
        """Setting .plugins() stores the value in builder._config."""
        builder = App("test_name", "test_root_agent")
        builder.plugins([])
        assert builder._config["plugins"] == []

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = App("test_name", "test_root_agent")
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestInMemoryRunnerBuilder:
    """Tests for InMemoryRunner builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = InMemoryRunner()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.agent() returns the builder instance for chaining."""
        builder = InMemoryRunner()
        result = builder.agent(None)
        assert result is builder

    def test_config_accumulation(self):
        """Setting .agent() stores the value in builder._config."""
        builder = InMemoryRunner()
        builder.agent(None)
        assert builder._config["agent"] == None

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = InMemoryRunner()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestRunnerBuilder:
    """Tests for Runner builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = Runner("test_session_service")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.app() returns the builder instance for chaining."""
        builder = Runner("test_session_service")
        result = builder.app(None)
        assert result is builder

    def test_config_accumulation(self):
        """Setting .app() stores the value in builder._config."""
        builder = Runner("test_session_service")
        builder.app(None)
        assert builder._config["app"] == None

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = Runner("test_session_service")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")
