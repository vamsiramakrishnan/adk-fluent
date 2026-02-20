"""Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects."""

import pytest  # noqa: F401 (used inside test methods)

from adk_fluent.service import (
    BaseArtifactService,
    BaseMemoryService,
    BaseSessionService,
    DatabaseSessionService,
    FileArtifactService,
    ForwardingArtifactService,
    GcsArtifactService,
    InMemoryArtifactService,
    InMemoryMemoryService,
    InMemorySessionService,
    PerAgentDatabaseSessionService,
    SqliteSessionService,
    VertexAiMemoryBankService,
    VertexAiRagMemoryService,
    VertexAiSessionService,
)


class TestBaseArtifactServiceBuilder:
    """Tests for BaseArtifactService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BaseArtifactService("test_args", "test_kwargs")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BaseArtifactService("test_args", "test_kwargs")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestFileArtifactServiceBuilder:
    """Tests for FileArtifactService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = FileArtifactService("test_root_dir")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = FileArtifactService("test_root_dir")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestGcsArtifactServiceBuilder:
    """Tests for GcsArtifactService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = GcsArtifactService("test_bucket_name", "test_kwargs")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = GcsArtifactService("test_bucket_name", "test_kwargs")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestInMemoryArtifactServiceBuilder:
    """Tests for InMemoryArtifactService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = InMemoryArtifactService()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.artifacts() returns the builder instance for chaining."""
        builder = InMemoryArtifactService()
        result = builder.artifacts({})
        assert result is builder

    def test_config_accumulation(self):
        """Setting .artifacts() stores the value in builder._config."""
        builder = InMemoryArtifactService()
        builder.artifacts({})
        assert builder._config["artifacts"] == {}

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = InMemoryArtifactService()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestPerAgentDatabaseSessionServiceBuilder:
    """Tests for PerAgentDatabaseSessionService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = PerAgentDatabaseSessionService("test_agents_root")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = PerAgentDatabaseSessionService("test_agents_root")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestBaseMemoryServiceBuilder:
    """Tests for BaseMemoryService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BaseMemoryService("test_args", "test_kwargs")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BaseMemoryService("test_args", "test_kwargs")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestInMemoryMemoryServiceBuilder:
    """Tests for InMemoryMemoryService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = InMemoryMemoryService()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = InMemoryMemoryService()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestVertexAiMemoryBankServiceBuilder:
    """Tests for VertexAiMemoryBankService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = VertexAiMemoryBankService()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = VertexAiMemoryBankService()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestVertexAiRagMemoryServiceBuilder:
    """Tests for VertexAiRagMemoryService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = VertexAiRagMemoryService()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.vector_distance_threshold() returns the builder instance for chaining."""
        builder = VertexAiRagMemoryService()
        result = builder.vector_distance_threshold(0.5)
        assert result is builder

    def test_config_accumulation(self):
        """Setting .vector_distance_threshold() stores the value in builder._config."""
        builder = VertexAiRagMemoryService()
        builder.vector_distance_threshold(0.5)
        assert builder._config["vector_distance_threshold"] == 0.5

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = VertexAiRagMemoryService()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestBaseSessionServiceBuilder:
    """Tests for BaseSessionService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BaseSessionService("test_args", "test_kwargs")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BaseSessionService("test_args", "test_kwargs")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestDatabaseSessionServiceBuilder:
    """Tests for DatabaseSessionService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = DatabaseSessionService("test_db_url", "test_kwargs")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = DatabaseSessionService("test_db_url", "test_kwargs")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestInMemorySessionServiceBuilder:
    """Tests for InMemorySessionService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = InMemorySessionService()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = InMemorySessionService()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestSqliteSessionServiceBuilder:
    """Tests for SqliteSessionService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = SqliteSessionService("test_db_path")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = SqliteSessionService("test_db_path")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestVertexAiSessionServiceBuilder:
    """Tests for VertexAiSessionService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = VertexAiSessionService()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = VertexAiSessionService()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestForwardingArtifactServiceBuilder:
    """Tests for ForwardingArtifactService builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ForwardingArtifactService("test_tool_context")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ForwardingArtifactService("test_tool_context")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")
