"""Auto-generated builder-mechanics tests. Verify fluent API surface without constructing ADK objects."""

import pytest  # noqa: F401 (used inside test methods)

from adk_fluent.config import (
    AgentConfig,
    AgentRefConfig,
    AgentSimulatorConfig,
    AgentToolConfig,
    ArgumentConfig,
    AudioCacheConfig,
    BaseAgentConfig,
    BaseGoogleCredentialsConfig,
    BaseToolConfig,
    BigQueryCredentialsConfig,
    BigQueryLoggerConfig,
    BigQueryToolConfig,
    BigtableCredentialsConfig,
    CodeConfig,
    ContextCacheConfig,
    DataAgentCredentialsConfig,
    DataAgentToolConfig,
    EventsCompactionConfig,
    ExampleToolConfig,
    FeatureConfig,
    GetSessionConfig,
    InjectionConfig,
    LlmAgentConfig,
    LoopAgentConfig,
    McpToolsetConfig,
    ParallelAgentConfig,
    PubSubCredentialsConfig,
    PubSubToolConfig,
    ResumabilityConfig,
    RetryConfig,
    RunConfig,
    SequentialAgentConfig,
    SimplePromptOptimizerConfig,
    SpannerCredentialsConfig,
    ToolArgsConfig,
    ToolConfig,
    ToolSimulationConfig,
    ToolThreadPoolConfig,
)


class TestAgentConfigBuilder:
    """Tests for AgentConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = AgentConfig('test_root')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = AgentConfig('test_root')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestBaseAgentConfigBuilder:
    """Tests for BaseAgentConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BaseAgentConfig('test_name')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.describe() returns the builder instance for chaining."""
        builder = BaseAgentConfig('test_name')
        result = builder.describe("test_value")
        assert result is builder


    def test_config_accumulation(self):
        """Setting .sub_agents() stores the value in builder._config."""
        builder = BaseAgentConfig('test_name')
        builder.sub_agents(None)
        assert builder._config["sub_agents"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BaseAgentConfig('test_name')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestAgentRefConfigBuilder:
    """Tests for AgentRefConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = AgentRefConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.config_path() returns the builder instance for chaining."""
        builder = AgentRefConfig()
        result = builder.config_path(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .config_path() stores the value in builder._config."""
        builder = AgentRefConfig()
        builder.config_path(None)
        assert builder._config["config_path"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = AgentRefConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestArgumentConfigBuilder:
    """Tests for ArgumentConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ArgumentConfig('test_value')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.name() returns the builder instance for chaining."""
        builder = ArgumentConfig('test_value')
        result = builder.name(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .name() stores the value in builder._config."""
        builder = ArgumentConfig('test_value')
        builder.name(None)
        assert builder._config["name"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ArgumentConfig('test_value')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestCodeConfigBuilder:
    """Tests for CodeConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = CodeConfig('test_name')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.args() returns the builder instance for chaining."""
        builder = CodeConfig('test_name')
        result = builder.args(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .args() stores the value in builder._config."""
        builder = CodeConfig('test_name')
        builder.args(None)
        assert builder._config["args"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = CodeConfig('test_name')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestContextCacheConfigBuilder:
    """Tests for ContextCacheConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ContextCacheConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.cache_intervals() returns the builder instance for chaining."""
        builder = ContextCacheConfig()
        result = builder.cache_intervals(42)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .cache_intervals() stores the value in builder._config."""
        builder = ContextCacheConfig()
        builder.cache_intervals(42)
        assert builder._config["cache_intervals"] == 42


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ContextCacheConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestLlmAgentConfigBuilder:
    """Tests for LlmAgentConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = LlmAgentConfig('test_name', 'test_instruction')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.describe() returns the builder instance for chaining."""
        builder = LlmAgentConfig('test_name', 'test_instruction')
        result = builder.describe("test_value")
        assert result is builder


    def test_config_accumulation(self):
        """Setting .agent_class() stores the value in builder._config."""
        builder = LlmAgentConfig('test_name', 'test_instruction')
        builder.agent_class("test_value")
        assert builder._config["agent_class"] == "test_value"


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = LlmAgentConfig('test_name', 'test_instruction')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestLoopAgentConfigBuilder:
    """Tests for LoopAgentConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = LoopAgentConfig('test_name')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.describe() returns the builder instance for chaining."""
        builder = LoopAgentConfig('test_name')
        result = builder.describe("test_value")
        assert result is builder


    def test_config_accumulation(self):
        """Setting .agent_class() stores the value in builder._config."""
        builder = LoopAgentConfig('test_name')
        builder.agent_class("test_value")
        assert builder._config["agent_class"] == "test_value"


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = LoopAgentConfig('test_name')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestParallelAgentConfigBuilder:
    """Tests for ParallelAgentConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ParallelAgentConfig('test_name')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.describe() returns the builder instance for chaining."""
        builder = ParallelAgentConfig('test_name')
        result = builder.describe("test_value")
        assert result is builder


    def test_config_accumulation(self):
        """Setting .agent_class() stores the value in builder._config."""
        builder = ParallelAgentConfig('test_name')
        builder.agent_class("test_value")
        assert builder._config["agent_class"] == "test_value"


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ParallelAgentConfig('test_name')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestRunConfigBuilder:
    """Tests for RunConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = RunConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.speech_config() returns the builder instance for chaining."""
        builder = RunConfig()
        result = builder.speech_config(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .speech_config() stores the value in builder._config."""
        builder = RunConfig()
        builder.speech_config(None)
        assert builder._config["speech_config"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = RunConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestToolThreadPoolConfigBuilder:
    """Tests for ToolThreadPoolConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ToolThreadPoolConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.max_workers() returns the builder instance for chaining."""
        builder = ToolThreadPoolConfig()
        result = builder.max_workers(42)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .max_workers() stores the value in builder._config."""
        builder = ToolThreadPoolConfig()
        builder.max_workers(42)
        assert builder._config["max_workers"] == 42


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ToolThreadPoolConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestSequentialAgentConfigBuilder:
    """Tests for SequentialAgentConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = SequentialAgentConfig('test_name')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.describe() returns the builder instance for chaining."""
        builder = SequentialAgentConfig('test_name')
        result = builder.describe("test_value")
        assert result is builder


    def test_config_accumulation(self):
        """Setting .agent_class() stores the value in builder._config."""
        builder = SequentialAgentConfig('test_name')
        builder.agent_class("test_value")
        assert builder._config["agent_class"] == "test_value"


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = SequentialAgentConfig('test_name')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestEventsCompactionConfigBuilder:
    """Tests for EventsCompactionConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = EventsCompactionConfig('test_compaction_interval', 'test_overlap_size')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.summarizer() returns the builder instance for chaining."""
        builder = EventsCompactionConfig('test_compaction_interval', 'test_overlap_size')
        result = builder.summarizer(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .summarizer() stores the value in builder._config."""
        builder = EventsCompactionConfig('test_compaction_interval', 'test_overlap_size')
        builder.summarizer(None)
        assert builder._config["summarizer"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = EventsCompactionConfig('test_compaction_interval', 'test_overlap_size')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestResumabilityConfigBuilder:
    """Tests for ResumabilityConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ResumabilityConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.is_resumable() returns the builder instance for chaining."""
        builder = ResumabilityConfig()
        result = builder.is_resumable(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .is_resumable() stores the value in builder._config."""
        builder = ResumabilityConfig()
        builder.is_resumable(True)
        assert builder._config["is_resumable"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ResumabilityConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestFeatureConfigBuilder:
    """Tests for FeatureConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = FeatureConfig('test_stage')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.default_on() returns the builder instance for chaining."""
        builder = FeatureConfig('test_stage')
        result = builder.default_on(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .default_on() stores the value in builder._config."""
        builder = FeatureConfig('test_stage')
        builder.default_on(True)
        assert builder._config["default_on"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = FeatureConfig('test_stage')
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestAudioCacheConfigBuilder:
    """Tests for AudioCacheConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = AudioCacheConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.max_cache_size_bytes() returns the builder instance for chaining."""
        builder = AudioCacheConfig()
        result = builder.max_cache_size_bytes(42)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .max_cache_size_bytes() stores the value in builder._config."""
        builder = AudioCacheConfig()
        builder.max_cache_size_bytes(42)
        assert builder._config["max_cache_size_bytes"] == 42


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = AudioCacheConfig()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestSimplePromptOptimizerConfigBuilder:
    """Tests for SimplePromptOptimizerConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = SimplePromptOptimizerConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.optimizer_model() returns the builder instance for chaining."""
        builder = SimplePromptOptimizerConfig()
        result = builder.optimizer_model("test_value")
        assert result is builder


    def test_config_accumulation(self):
        """Setting .optimizer_model() stores the value in builder._config."""
        builder = SimplePromptOptimizerConfig()
        builder.optimizer_model("test_value")
        assert builder._config["optimizer_model"] == "test_value"


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = SimplePromptOptimizerConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestBigQueryLoggerConfigBuilder:
    """Tests for BigQueryLoggerConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BigQueryLoggerConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.enabled() returns the builder instance for chaining."""
        builder = BigQueryLoggerConfig()
        result = builder.enabled(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .enabled() stores the value in builder._config."""
        builder = BigQueryLoggerConfig()
        builder.enabled(True)
        assert builder._config["enabled"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BigQueryLoggerConfig()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestRetryConfigBuilder:
    """Tests for RetryConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = RetryConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.max_retries() returns the builder instance for chaining."""
        builder = RetryConfig()
        result = builder.max_retries(42)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .max_retries() stores the value in builder._config."""
        builder = RetryConfig()
        builder.max_retries(42)
        assert builder._config["max_retries"] == 42


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = RetryConfig()
        with pytest.raises(AttributeError, match="not a recognized parameter"):
            builder.zzz_not_a_real_field("oops")


class TestGetSessionConfigBuilder:
    """Tests for GetSessionConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = GetSessionConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.num_recent_events() returns the builder instance for chaining."""
        builder = GetSessionConfig()
        result = builder.num_recent_events(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .num_recent_events() stores the value in builder._config."""
        builder = GetSessionConfig()
        builder.num_recent_events(None)
        assert builder._config["num_recent_events"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = GetSessionConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestBaseGoogleCredentialsConfigBuilder:
    """Tests for BaseGoogleCredentialsConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BaseGoogleCredentialsConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.credentials() returns the builder instance for chaining."""
        builder = BaseGoogleCredentialsConfig()
        result = builder.credentials(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .credentials() stores the value in builder._config."""
        builder = BaseGoogleCredentialsConfig()
        builder.credentials(None)
        assert builder._config["credentials"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BaseGoogleCredentialsConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestAgentSimulatorConfigBuilder:
    """Tests for AgentSimulatorConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = AgentSimulatorConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.tool_simulation_configs() returns the builder instance for chaining."""
        builder = AgentSimulatorConfig()
        result = builder.tool_simulation_configs([])
        assert result is builder


    def test_config_accumulation(self):
        """Setting .tool_simulation_configs() stores the value in builder._config."""
        builder = AgentSimulatorConfig()
        builder.tool_simulation_configs([])
        assert builder._config["tool_simulation_configs"] == []


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = AgentSimulatorConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestInjectionConfigBuilder:
    """Tests for InjectionConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = InjectionConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.injection_probability() returns the builder instance for chaining."""
        builder = InjectionConfig()
        result = builder.injection_probability(0.5)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .injection_probability() stores the value in builder._config."""
        builder = InjectionConfig()
        builder.injection_probability(0.5)
        assert builder._config["injection_probability"] == 0.5


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = InjectionConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestToolSimulationConfigBuilder:
    """Tests for ToolSimulationConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ToolSimulationConfig('test_tool_name')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.injection_configs() returns the builder instance for chaining."""
        builder = ToolSimulationConfig('test_tool_name')
        result = builder.injection_configs([])
        assert result is builder


    def test_config_accumulation(self):
        """Setting .injection_configs() stores the value in builder._config."""
        builder = ToolSimulationConfig('test_tool_name')
        builder.injection_configs([])
        assert builder._config["injection_configs"] == []


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ToolSimulationConfig('test_tool_name')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestAgentToolConfigBuilder:
    """Tests for AgentToolConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = AgentToolConfig('test_agent')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.skip_summarization() returns the builder instance for chaining."""
        builder = AgentToolConfig('test_agent')
        result = builder.skip_summarization(True)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .skip_summarization() stores the value in builder._config."""
        builder = AgentToolConfig('test_agent')
        builder.skip_summarization(True)
        assert builder._config["skip_summarization"] == True


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = AgentToolConfig('test_agent')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestBigQueryCredentialsConfigBuilder:
    """Tests for BigQueryCredentialsConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BigQueryCredentialsConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.credentials() returns the builder instance for chaining."""
        builder = BigQueryCredentialsConfig()
        result = builder.credentials(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .credentials() stores the value in builder._config."""
        builder = BigQueryCredentialsConfig()
        builder.credentials(None)
        assert builder._config["credentials"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BigQueryCredentialsConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestBigQueryToolConfigBuilder:
    """Tests for BigQueryToolConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BigQueryToolConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.maximum_bytes_billed() returns the builder instance for chaining."""
        builder = BigQueryToolConfig()
        result = builder.maximum_bytes_billed(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .maximum_bytes_billed() stores the value in builder._config."""
        builder = BigQueryToolConfig()
        builder.maximum_bytes_billed(None)
        assert builder._config["maximum_bytes_billed"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BigQueryToolConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestBigtableCredentialsConfigBuilder:
    """Tests for BigtableCredentialsConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BigtableCredentialsConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.credentials() returns the builder instance for chaining."""
        builder = BigtableCredentialsConfig()
        result = builder.credentials(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .credentials() stores the value in builder._config."""
        builder = BigtableCredentialsConfig()
        builder.credentials(None)
        assert builder._config["credentials"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BigtableCredentialsConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestDataAgentToolConfigBuilder:
    """Tests for DataAgentToolConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = DataAgentToolConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.max_query_result_rows() returns the builder instance for chaining."""
        builder = DataAgentToolConfig()
        result = builder.max_query_result_rows(42)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .max_query_result_rows() stores the value in builder._config."""
        builder = DataAgentToolConfig()
        builder.max_query_result_rows(42)
        assert builder._config["max_query_result_rows"] == 42


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = DataAgentToolConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestDataAgentCredentialsConfigBuilder:
    """Tests for DataAgentCredentialsConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = DataAgentCredentialsConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.credentials() returns the builder instance for chaining."""
        builder = DataAgentCredentialsConfig()
        result = builder.credentials(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .credentials() stores the value in builder._config."""
        builder = DataAgentCredentialsConfig()
        builder.credentials(None)
        assert builder._config["credentials"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = DataAgentCredentialsConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestExampleToolConfigBuilder:
    """Tests for ExampleToolConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ExampleToolConfig('test_examples')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ExampleToolConfig('test_examples')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestMcpToolsetConfigBuilder:
    """Tests for McpToolsetConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = McpToolsetConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.stdio_server_params() returns the builder instance for chaining."""
        builder = McpToolsetConfig()
        result = builder.stdio_server_params(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .stdio_server_params() stores the value in builder._config."""
        builder = McpToolsetConfig()
        builder.stdio_server_params(None)
        assert builder._config["stdio_server_params"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = McpToolsetConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestPubSubToolConfigBuilder:
    """Tests for PubSubToolConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = PubSubToolConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.project_id() returns the builder instance for chaining."""
        builder = PubSubToolConfig()
        result = builder.project_id("test_value")
        assert result is builder


    def test_config_accumulation(self):
        """Setting .project_id() stores the value in builder._config."""
        builder = PubSubToolConfig()
        builder.project_id("test_value")
        assert builder._config["project_id"] == "test_value"


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = PubSubToolConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestPubSubCredentialsConfigBuilder:
    """Tests for PubSubCredentialsConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = PubSubCredentialsConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.credentials() returns the builder instance for chaining."""
        builder = PubSubCredentialsConfig()
        result = builder.credentials(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .credentials() stores the value in builder._config."""
        builder = PubSubCredentialsConfig()
        builder.credentials(None)
        assert builder._config["credentials"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = PubSubCredentialsConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestSpannerCredentialsConfigBuilder:
    """Tests for SpannerCredentialsConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = SpannerCredentialsConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.credentials() returns the builder instance for chaining."""
        builder = SpannerCredentialsConfig()
        result = builder.credentials(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .credentials() stores the value in builder._config."""
        builder = SpannerCredentialsConfig()
        builder.credentials(None)
        assert builder._config["credentials"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = SpannerCredentialsConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestBaseToolConfigBuilder:
    """Tests for BaseToolConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = BaseToolConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = BaseToolConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestToolArgsConfigBuilder:
    """Tests for ToolArgsConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ToolArgsConfig()
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ToolArgsConfig()
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")


class TestToolConfigBuilder:
    """Tests for ToolConfig builder mechanics (no .build() calls)."""

    def test_builder_creation(self):
        """Builder constructor stores args in _config."""
        builder = ToolConfig('test_name')
        assert builder is not None
        assert isinstance(builder._config, dict)


    def test_chaining_returns_self(self):
        """.args() returns the builder instance for chaining."""
        builder = ToolConfig('test_name')
        result = builder.args(None)
        assert result is builder


    def test_config_accumulation(self):
        """Setting .args() stores the value in builder._config."""
        builder = ToolConfig('test_name')
        builder.args(None)
        assert builder._config["args"] == None


    def test_typo_detection(self):
        """Typos in method names raise clear AttributeError."""
        builder = ToolConfig('test_name')
        with pytest.raises(AttributeError, match="not a recognized field"):
            builder.zzz_not_a_real_field("oops")
