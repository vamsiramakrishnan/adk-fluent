"""Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects."""

import pytest  # noqa: F401 (used inside test methods)

from adk_fluent.plugin import (
    AgentSimulatorPlugin,
    BasePlugin,
    BigQueryAgentAnalyticsPlugin,
    ContextFilterPlugin,
    DebugLoggingPlugin,
    GlobalInstructionPlugin,
    LoggingPlugin,
    MultimodalToolResultsPlugin,
    RecordingsPlugin,
    ReflectAndRetryToolPlugin,
    ReplayPlugin,
    SaveFilesAsArtifactsPlugin,
)


class TestRecordingsPluginBuilder:
    """Tests for RecordingsPlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = RecordingsPlugin()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.name() returns the builder instance for chaining."""
        builder = RecordingsPlugin()
        result = builder.name("test_value")
        assert result is builder

    def test_config_accumulation(self):
        """Setting .name() stores the value in builder._config."""
        builder = RecordingsPlugin()
        builder.name("test_value")
        assert builder._config["name"] == "test_value"

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = RecordingsPlugin()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestReplayPluginBuilder:
    """Tests for ReplayPlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ReplayPlugin()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.name() returns the builder instance for chaining."""
        builder = ReplayPlugin()
        result = builder.name("test_value")
        assert result is builder

    def test_config_accumulation(self):
        """Setting .name() stores the value in builder._config."""
        builder = ReplayPlugin()
        builder.name("test_value")
        assert builder._config["name"] == "test_value"

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ReplayPlugin()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestBasePluginBuilder:
    """Tests for BasePlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BasePlugin("test_name")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BasePlugin("test_name")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestBigQueryAgentAnalyticsPluginBuilder:
    """Tests for BigQueryAgentAnalyticsPlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BigQueryAgentAnalyticsPlugin("test_project_id", "test_dataset_id", "test_kwargs")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.table_id() returns the builder instance for chaining."""
        builder = BigQueryAgentAnalyticsPlugin("test_project_id", "test_dataset_id", "test_kwargs")
        result = builder.table_id("test_value")
        assert result is builder

    def test_config_accumulation(self):
        """Setting .table_id() stores the value in builder._config."""
        builder = BigQueryAgentAnalyticsPlugin("test_project_id", "test_dataset_id", "test_kwargs")
        builder.table_id("test_value")
        assert builder._config["table_id"] == "test_value"

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BigQueryAgentAnalyticsPlugin("test_project_id", "test_dataset_id", "test_kwargs")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestContextFilterPluginBuilder:
    """Tests for ContextFilterPlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ContextFilterPlugin()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.num_invocations_to_keep() returns the builder instance for chaining."""
        builder = ContextFilterPlugin()
        result = builder.num_invocations_to_keep(None)
        assert result is builder

    def test_config_accumulation(self):
        """Setting .num_invocations_to_keep() stores the value in builder._config."""
        builder = ContextFilterPlugin()
        builder.num_invocations_to_keep(None)
        assert builder._config["num_invocations_to_keep"] == None

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ContextFilterPlugin()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestDebugLoggingPluginBuilder:
    """Tests for DebugLoggingPlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = DebugLoggingPlugin()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.name() returns the builder instance for chaining."""
        builder = DebugLoggingPlugin()
        result = builder.name("test_value")
        assert result is builder

    def test_config_accumulation(self):
        """Setting .name() stores the value in builder._config."""
        builder = DebugLoggingPlugin()
        builder.name("test_value")
        assert builder._config["name"] == "test_value"

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = DebugLoggingPlugin()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestGlobalInstructionPluginBuilder:
    """Tests for GlobalInstructionPlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = GlobalInstructionPlugin()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.global_instruction() returns the builder instance for chaining."""
        builder = GlobalInstructionPlugin()
        result = builder.global_instruction("test_value")
        assert result is builder

    def test_config_accumulation(self):
        """Setting .global_instruction() stores the value in builder._config."""
        builder = GlobalInstructionPlugin()
        builder.global_instruction("test_value")
        assert builder._config["global_instruction"] == "test_value"

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = GlobalInstructionPlugin()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestLoggingPluginBuilder:
    """Tests for LoggingPlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = LoggingPlugin()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.name() returns the builder instance for chaining."""
        builder = LoggingPlugin()
        result = builder.name("test_value")
        assert result is builder

    def test_config_accumulation(self):
        """Setting .name() stores the value in builder._config."""
        builder = LoggingPlugin()
        builder.name("test_value")
        assert builder._config["name"] == "test_value"

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = LoggingPlugin()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestMultimodalToolResultsPluginBuilder:
    """Tests for MultimodalToolResultsPlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = MultimodalToolResultsPlugin()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.name() returns the builder instance for chaining."""
        builder = MultimodalToolResultsPlugin()
        result = builder.name("test_value")
        assert result is builder

    def test_config_accumulation(self):
        """Setting .name() stores the value in builder._config."""
        builder = MultimodalToolResultsPlugin()
        builder.name("test_value")
        assert builder._config["name"] == "test_value"

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = MultimodalToolResultsPlugin()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestReflectAndRetryToolPluginBuilder:
    """Tests for ReflectAndRetryToolPlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ReflectAndRetryToolPlugin()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.name() returns the builder instance for chaining."""
        builder = ReflectAndRetryToolPlugin()
        result = builder.name("test_value")
        assert result is builder

    def test_config_accumulation(self):
        """Setting .name() stores the value in builder._config."""
        builder = ReflectAndRetryToolPlugin()
        builder.name("test_value")
        assert builder._config["name"] == "test_value"

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ReflectAndRetryToolPlugin()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestSaveFilesAsArtifactsPluginBuilder:
    """Tests for SaveFilesAsArtifactsPlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = SaveFilesAsArtifactsPlugin()
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_chaining_returns_self(self):
        """.name() returns the builder instance for chaining."""
        builder = SaveFilesAsArtifactsPlugin()
        result = builder.name("test_value")
        assert result is builder

    def test_config_accumulation(self):
        """Setting .name() stores the value in builder._config."""
        builder = SaveFilesAsArtifactsPlugin()
        builder.name("test_value")
        assert builder._config["name"] == "test_value"

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = SaveFilesAsArtifactsPlugin()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestAgentSimulatorPluginBuilder:
    """Tests for AgentSimulatorPlugin builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = AgentSimulatorPlugin("test_simulator_engine")
        assert builder is not None
        assert isinstance(builder._config, dict)

    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = AgentSimulatorPlugin("test_simulator_engine")
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")
