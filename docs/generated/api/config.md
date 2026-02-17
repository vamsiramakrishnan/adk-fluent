# Module: `config`

# AgentConfig

> Fluent builder for `google.adk.agents.agent_config.AgentConfig`

The config for the YAML schema to create an agent.

## Constructor

```python
AgentConfig(root)
```

| Argument | Type |
|----------|------|
| `root` | `RootModelRootType` |

## Terminal Methods

### `.build() -> AgentConfig`

Resolve into a native ADK AgentConfig.

---

# BaseAgentConfig

> Fluent builder for `google.adk.agents.base_agent_config.BaseAgentConfig`

The config for the YAML schema of a BaseAgent.

## Constructor

```python
BaseAgentConfig(name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

## Methods

### `.describe(value)`

- **Type:** `str`
- **Maps to:** `description`
- Optional. The description of the agent.

## Terminal Methods

### `.build() -> BaseAgentConfig`

Resolve into a native ADK BaseAgentConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent_class(value)` | `Union[Literal[BaseAgent], str]` |
| `.sub_agents(value)` | `Union[list[AgentRefConfig], NoneType]` |
| `.before_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |
| `.after_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |

---

# AgentRefConfig

> Fluent builder for `google.adk.agents.common_configs.AgentRefConfig`

The config for the reference to another agent.

## Terminal Methods

### `.build() -> AgentRefConfig`

Resolve into a native ADK AgentRefConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.config_path(value)` | `Union[str, NoneType]` |
| `.code(value)` | `Union[str, NoneType]` |

---

# ArgumentConfig

> Fluent builder for `google.adk.agents.common_configs.ArgumentConfig`

An argument passed to a function or a class's constructor.

## Constructor

```python
ArgumentConfig(value)
```

| Argument | Type |
|----------|------|
| `value` | `Any` |

## Terminal Methods

### `.build() -> ArgumentConfig`

Resolve into a native ADK ArgumentConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | `Union[str, NoneType]` |

---

# CodeConfig

> Fluent builder for `google.adk.agents.common_configs.CodeConfig`

Code reference config for a variable, a function, or a class.

## Constructor

```python
CodeConfig(name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

## Terminal Methods

### `.build() -> CodeConfig`

Resolve into a native ADK CodeConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.args(value)` | `Union[list[ArgumentConfig], NoneType]` |

---

# ContextCacheConfig

> Fluent builder for `google.adk.agents.context_cache_config.ContextCacheConfig`

Configuration for context caching across all agents in an app.

## Terminal Methods

### `.build() -> ContextCacheConfig`

Resolve into a native ADK ContextCacheConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.cache_intervals(value)` | `int` |
| `.ttl_seconds(value)` | `int` |
| `.min_tokens(value)` | `int` |

---

# LlmAgentConfig

> Fluent builder for `google.adk.agents.llm_agent_config.LlmAgentConfig`

The config for the YAML schema of a LlmAgent.

## Constructor

```python
LlmAgentConfig(name, instruction)
```

| Argument | Type |
|----------|------|
| `name` | `str` |
| `instruction` | `str` |

## Methods

### `.describe(value)`

- **Type:** `str`
- **Maps to:** `description`
- Optional. The description of the agent.

### `.history(value)`

- **Type:** `Literal[default, none]`
- **Maps to:** `include_contents`
- Optional. LlmAgent.include_contents.

### `.instruct(value)`

- **Type:** `str`
- **Maps to:** `instruction`
- Required. LlmAgent.instruction. Dynamic instructions with placeholder support. Behavior: if static_instruction is None, goes to system_instruction; if static_instruction is set, goes to user content after static content.

### `.outputs(value)`

- **Type:** `Union[str, NoneType]`
- **Maps to:** `output_key`
- Optional. LlmAgent.output_key.

## Terminal Methods

### `.build() -> LlmAgentConfig`

Resolve into a native ADK LlmAgentConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent_class(value)` | `str` |
| `.sub_agents(value)` | `Union[list[AgentRefConfig], NoneType]` |
| `.before_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |
| `.after_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |
| `.model(value)` | `Union[str, NoneType]` |
| `.model_code(value)` | `Union[CodeConfig, NoneType]` |
| `.static_instruction(value)` | `Union[Content, str, File, Part, list[Union[str, File, Part]], NoneType]` |
| `.disallow_transfer_to_parent(value)` | `Union[bool, NoneType]` |
| `.disallow_transfer_to_peers(value)` | `Union[bool, NoneType]` |
| `.input_schema(value)` | `Union[CodeConfig, NoneType]` |
| `.output_schema(value)` | `Union[CodeConfig, NoneType]` |
| `.tools(value)` | `Union[list[ToolConfig], NoneType]` |
| `.before_model_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |
| `.after_model_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |
| `.before_tool_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |
| `.after_tool_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |
| `.generate_content_config(value)` | `Union[GenerateContentConfig, NoneType]` |

---

# LoopAgentConfig

> Fluent builder for `google.adk.agents.loop_agent_config.LoopAgentConfig`

The config for the YAML schema of a LoopAgent.

## Constructor

```python
LoopAgentConfig(name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

## Methods

### `.describe(value)`

- **Type:** `str`
- **Maps to:** `description`
- Optional. The description of the agent.

## Terminal Methods

### `.build() -> LoopAgentConfig`

Resolve into a native ADK LoopAgentConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent_class(value)` | `str` |
| `.sub_agents(value)` | `Union[list[AgentRefConfig], NoneType]` |
| `.before_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |
| `.after_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |
| `.max_iterations(value)` | `Union[int, NoneType]` |

---

# ParallelAgentConfig

> Fluent builder for `google.adk.agents.parallel_agent_config.ParallelAgentConfig`

The config for the YAML schema of a ParallelAgent.

## Constructor

```python
ParallelAgentConfig(name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

## Methods

### `.describe(value)`

- **Type:** `str`
- **Maps to:** `description`
- Optional. The description of the agent.

## Terminal Methods

### `.build() -> ParallelAgentConfig`

Resolve into a native ADK ParallelAgentConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent_class(value)` | `str` |
| `.sub_agents(value)` | `Union[list[AgentRefConfig], NoneType]` |
| `.before_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |
| `.after_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |

---

# RunConfig

> Fluent builder for `google.adk.agents.run_config.RunConfig`

Configs for runtime behavior of agents.

## Terminal Methods

### `.build() -> RunConfig`

Resolve into a native ADK RunConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.speech_config(value)` | `Union[SpeechConfig, NoneType]` |
| `.response_modalities(value)` | `Union[list[str], NoneType]` |
| `.save_input_blobs_as_artifacts(value)` | `bool` |
| `.support_cfc(value)` | `bool` |
| `.streaming_mode(value)` | `StreamingMode` |
| `.output_audio_transcription(value)` | `Union[AudioTranscriptionConfig, NoneType]` |
| `.input_audio_transcription(value)` | `Union[AudioTranscriptionConfig, NoneType]` |
| `.realtime_input_config(value)` | `Union[RealtimeInputConfig, NoneType]` |
| `.enable_affective_dialog(value)` | `Union[bool, NoneType]` |
| `.proactivity(value)` | `Union[ProactivityConfig, NoneType]` |
| `.session_resumption(value)` | `Union[SessionResumptionConfig, NoneType]` |
| `.context_window_compression(value)` | `Union[ContextWindowCompressionConfig, NoneType]` |
| `.save_live_blob(value)` | `bool` |
| `.tool_thread_pool_config(value)` | `Union[ToolThreadPoolConfig, NoneType]` |
| `.save_live_audio(value)` | `bool` |
| `.max_llm_calls(value)` | `int` |
| `.custom_metadata(value)` | `Union[dict[str, Any], NoneType]` |

---

# ToolThreadPoolConfig

> Fluent builder for `google.adk.agents.run_config.ToolThreadPoolConfig`

Configuration for the tool thread pool executor.

## Terminal Methods

### `.build() -> ToolThreadPoolConfig`

Resolve into a native ADK ToolThreadPoolConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.max_workers(value)` | `int` |

---

# SequentialAgentConfig

> Fluent builder for `google.adk.agents.sequential_agent_config.SequentialAgentConfig`

The config for the YAML schema of a SequentialAgent.

## Constructor

```python
SequentialAgentConfig(name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

## Methods

### `.describe(value)`

- **Type:** `str`
- **Maps to:** `description`
- Optional. The description of the agent.

## Terminal Methods

### `.build() -> SequentialAgentConfig`

Resolve into a native ADK SequentialAgentConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent_class(value)` | `str` |
| `.sub_agents(value)` | `Union[list[AgentRefConfig], NoneType]` |
| `.before_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |
| `.after_agent_callbacks(value)` | `Union[list[CodeConfig], NoneType]` |

---

# EventsCompactionConfig

> Fluent builder for `google.adk.apps.app.EventsCompactionConfig`

The config of event compaction for an application.

## Constructor

```python
EventsCompactionConfig(compaction_interval, overlap_size)
```

| Argument | Type |
|----------|------|
| `compaction_interval` | `int` |
| `overlap_size` | `int` |

## Terminal Methods

### `.build() -> EventsCompactionConfig`

Resolve into a native ADK EventsCompactionConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.summarizer(value)` | `Union[BaseEventsSummarizer, NoneType]` |
| `.token_threshold(value)` | `Union[int, NoneType]` |
| `.event_retention_size(value)` | `Union[int, NoneType]` |

---

# ResumabilityConfig

> Fluent builder for `google.adk.apps.app.ResumabilityConfig`

The config of the resumability for an application.

## Terminal Methods

### `.build() -> ResumabilityConfig`

Resolve into a native ADK ResumabilityConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.is_resumable(value)` | `bool` |

---

# FeatureConfig

> Fluent builder for `google.adk.features._feature_registry.FeatureConfig`

Feature configuration.

## Constructor

```python
FeatureConfig(stage)
```

| Argument | Type |
|----------|------|
| `stage` | `FeatureStage` |

## Terminal Methods

### `.build() -> FeatureConfig`

Resolve into a native ADK FeatureConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.default_on(value)` | `bool` |

---

# AudioCacheConfig

> Fluent builder for `google.adk.flows.llm_flows.audio_cache_manager.AudioCacheConfig`

Configuration for audio caching behavior.

## Terminal Methods

### `.build() -> AudioCacheConfig`

Resolve into a native ADK AudioCacheConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.max_cache_size_bytes(value)` | `int` |
| `.max_cache_duration_seconds(value)` | `float` |
| `.auto_flush_threshold(value)` | `int` |

---

# SimplePromptOptimizerConfig

> Fluent builder for `google.adk.optimization.simple_prompt_optimizer.SimplePromptOptimizerConfig`

Configuration for the IterativePromptOptimizer.

## Terminal Methods

### `.build() -> SimplePromptOptimizerConfig`

Resolve into a native ADK SimplePromptOptimizerConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.optimizer_model(value)` | `str` |
| `.model_configuration(value)` | `GenerateContentConfig` |
| `.num_iterations(value)` | `int` |
| `.batch_size(value)` | `int` |

---

# BigQueryLoggerConfig

> Fluent builder for `google.adk.plugins.bigquery_agent_analytics_plugin.BigQueryLoggerConfig`

Configuration for the BigQueryAgentAnalyticsPlugin.

## Terminal Methods

### `.build() -> BigQueryLoggerConfig`

Resolve into a native ADK BigQueryLoggerConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.enabled(value)` | `bool` |
| `.event_allowlist(value)` | `list[str] | None` |
| `.event_denylist(value)` | `list[str] | None` |
| `.max_content_length(value)` | `int` |
| `.table_id(value)` | `str` |
| `.clustering_fields(value)` | `list[str]` |
| `.log_multi_modal_content(value)` | `bool` |
| `.retry_config(value)` | `RetryConfig` |
| `.batch_size(value)` | `int` |
| `.batch_flush_interval(value)` | `float` |
| `.shutdown_timeout(value)` | `float` |
| `.queue_max_size(value)` | `int` |
| `.content_formatter(value)` | `Optional[Callable[[Any, str], Any]]` |
| `.gcs_bucket_name(value)` | `Optional[str]` |
| `.connection_id(value)` | `Optional[str]` |
| `.log_session_metadata(value)` | `bool` |
| `.custom_tags(value)` | `dict[str, Any]` |

---

# RetryConfig

> Fluent builder for `google.adk.plugins.bigquery_agent_analytics_plugin.RetryConfig`

Configuration for retrying failed BigQuery write operations.

## Terminal Methods

### `.build() -> RetryConfig`

Resolve into a native ADK RetryConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.max_retries(value)` | `int` |
| `.initial_delay(value)` | `float` |
| `.multiplier(value)` | `float` |
| `.max_delay(value)` | `float` |

---

# GetSessionConfig

> Fluent builder for `google.adk.sessions.base_session_service.GetSessionConfig`

The configuration of getting a session.

## Terminal Methods

### `.build() -> GetSessionConfig`

Resolve into a native ADK GetSessionConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.num_recent_events(value)` | `Union[int, NoneType]` |
| `.after_timestamp(value)` | `Union[float, NoneType]` |

---

# BaseGoogleCredentialsConfig

> Fluent builder for `google.adk.tools._google_credentials.BaseGoogleCredentialsConfig`

Base Google Credentials Configuration for Google API tools (Experimental).

## Terminal Methods

### `.build() -> BaseGoogleCredentialsConfig`

Resolve into a native ADK BaseGoogleCredentialsConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]` |
| `.client_id(value)` | `Union[str, NoneType]` |
| `.client_secret(value)` | `Union[str, NoneType]` |
| `.scopes(value)` | `Union[list[str], NoneType]` |

---

# AgentSimulatorConfig

> Fluent builder for `google.adk.tools.agent_simulator.agent_simulator_config.AgentSimulatorConfig`

Configuration for AgentSimulator.

## Terminal Methods

### `.build() -> AgentSimulatorConfig`

Resolve into a native ADK AgentSimulatorConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.tool_simulation_configs(value)` | `list[ToolSimulationConfig]` |
| `.simulation_model(value)` | `str` |
| `.simulation_model_configuration(value)` | `GenerateContentConfig` |
| `.tracing_path(value)` | `Union[str, NoneType]` |
| `.environment_data(value)` | `Union[str, NoneType]` |

---

# InjectionConfig

> Fluent builder for `google.adk.tools.agent_simulator.agent_simulator_config.InjectionConfig`

Injection configuration for a tool.

## Terminal Methods

### `.build() -> InjectionConfig`

Resolve into a native ADK InjectionConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.injection_probability(value)` | `float` |
| `.match_args(value)` | `Union[dict[str, Any], NoneType]` |
| `.injected_latency_seconds(value)` | `float` |
| `.random_seed(value)` | `Union[int, NoneType]` |
| `.injected_error(value)` | `Union[InjectedError, NoneType]` |
| `.injected_response(value)` | `Union[dict[str, Any], NoneType]` |

---

# ToolSimulationConfig

> Fluent builder for `google.adk.tools.agent_simulator.agent_simulator_config.ToolSimulationConfig`

Simulation configuration for a single tool.

## Constructor

```python
ToolSimulationConfig(tool_name)
```

| Argument | Type |
|----------|------|
| `tool_name` | `str` |

## Terminal Methods

### `.build() -> ToolSimulationConfig`

Resolve into a native ADK ToolSimulationConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.injection_configs(value)` | `list[InjectionConfig]` |
| `.mock_strategy_type(value)` | `MockStrategy` |

---

# AgentToolConfig

> Fluent builder for `google.adk.tools.agent_tool.AgentToolConfig`

The config for the AgentTool.

## Constructor

```python
AgentToolConfig(agent)
```

| Argument | Type |
|----------|------|
| `agent` | `AgentRefConfig` |

## Terminal Methods

### `.build() -> AgentToolConfig`

Resolve into a native ADK AgentToolConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.skip_summarization(value)` | `bool` |
| `.include_plugins(value)` | `bool` |

---

# BigQueryCredentialsConfig

> Fluent builder for `google.adk.tools.bigquery.bigquery_credentials.BigQueryCredentialsConfig`

BigQuery Credentials Configuration for Google API tools (Experimental).

## Terminal Methods

### `.build() -> BigQueryCredentialsConfig`

Resolve into a native ADK BigQueryCredentialsConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]` |
| `.client_id(value)` | `Union[str, NoneType]` |
| `.client_secret(value)` | `Union[str, NoneType]` |
| `.scopes(value)` | `Union[list[str], NoneType]` |

---

# BigQueryToolConfig

> Fluent builder for `google.adk.tools.bigquery.config.BigQueryToolConfig`

Configuration for BigQuery tools.

## Terminal Methods

### `.build() -> BigQueryToolConfig`

Resolve into a native ADK BigQueryToolConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.write_mode(value)` | `WriteMode` |
| `.maximum_bytes_billed(value)` | `Union[int, NoneType]` |
| `.max_query_result_rows(value)` | `int` |
| `.application_name(value)` | `Union[str, NoneType]` |
| `.compute_project_id(value)` | `Union[str, NoneType]` |
| `.location(value)` | `Union[str, NoneType]` |
| `.job_labels(value)` | `Union[dict[str, str], NoneType]` |

---

# BigtableCredentialsConfig

> Fluent builder for `google.adk.tools.bigtable.bigtable_credentials.BigtableCredentialsConfig`

Bigtable Credentials Configuration for Google API tools (Experimental).

## Terminal Methods

### `.build() -> BigtableCredentialsConfig`

Resolve into a native ADK BigtableCredentialsConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]` |
| `.client_id(value)` | `Union[str, NoneType]` |
| `.client_secret(value)` | `Union[str, NoneType]` |
| `.scopes(value)` | `Union[list[str], NoneType]` |

---

# DataAgentToolConfig

> Fluent builder for `google.adk.tools.data_agent.config.DataAgentToolConfig`

Configuration for Data Agent tools.

## Terminal Methods

### `.build() -> DataAgentToolConfig`

Resolve into a native ADK DataAgentToolConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.max_query_result_rows(value)` | `int` |

---

# DataAgentCredentialsConfig

> Fluent builder for `google.adk.tools.data_agent.credentials.DataAgentCredentialsConfig`

Data Agent Credentials Configuration for Google API tools.

## Terminal Methods

### `.build() -> DataAgentCredentialsConfig`

Resolve into a native ADK DataAgentCredentialsConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]` |
| `.client_id(value)` | `Union[str, NoneType]` |
| `.client_secret(value)` | `Union[str, NoneType]` |
| `.scopes(value)` | `Union[list[str], NoneType]` |

---

# ExampleToolConfig

> Fluent builder for `google.adk.tools.example_tool.ExampleToolConfig`

Fluent builder for ExampleToolConfig.

## Constructor

```python
ExampleToolConfig(examples)
```

| Argument | Type |
|----------|------|
| `examples` | `Union[list[Example], str]` |

## Terminal Methods

### `.build() -> ExampleToolConfig`

Resolve into a native ADK ExampleToolConfig.

---

# McpToolsetConfig

> Fluent builder for `google.adk.tools.mcp_tool.mcp_toolset.McpToolsetConfig`

The config for McpToolset.

## Terminal Methods

### `.build() -> McpToolsetConfig`

Resolve into a native ADK McpToolsetConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.stdio_server_params(value)` | `Union[StdioServerParameters, NoneType]` |
| `.stdio_connection_params(value)` | `Union[StdioConnectionParams, NoneType]` |
| `.sse_connection_params(value)` | `Union[SseConnectionParams, NoneType]` |
| `.streamable_http_connection_params(value)` | `Union[StreamableHTTPConnectionParams, NoneType]` |
| `.tool_filter(value)` | `Union[list[str], NoneType]` |
| `.tool_name_prefix(value)` | `Union[str, NoneType]` |
| `.auth_scheme(value)` | `Union[APIKey, HTTPBase, OAuth2, OpenIdConnect, HTTPBearer, OpenIdConnectWithConfig, NoneType]` |
| `.auth_credential(value)` | `Union[AuthCredential, NoneType]` |
| `.use_mcp_resources(value)` | `bool` |

---

# PubSubToolConfig

> Fluent builder for `google.adk.tools.pubsub.config.PubSubToolConfig`

Configuration for Pub/Sub tools.

## Terminal Methods

### `.build() -> PubSubToolConfig`

Resolve into a native ADK PubSubToolConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.project_id(value)` | `str | None` |

---

# PubSubCredentialsConfig

> Fluent builder for `google.adk.tools.pubsub.pubsub_credentials.PubSubCredentialsConfig`

Pub/Sub Credentials Configuration for Google API tools (Experimental).

## Terminal Methods

### `.build() -> PubSubCredentialsConfig`

Resolve into a native ADK PubSubCredentialsConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]` |
| `.client_id(value)` | `Union[str, NoneType]` |
| `.client_secret(value)` | `Union[str, NoneType]` |
| `.scopes(value)` | `Union[list[str], NoneType]` |

---

# SpannerCredentialsConfig

> Fluent builder for `google.adk.tools.spanner.spanner_credentials.SpannerCredentialsConfig`

Spanner Credentials Configuration for Google API tools (Experimental).

## Terminal Methods

### `.build() -> SpannerCredentialsConfig`

Resolve into a native ADK SpannerCredentialsConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.credentials(value)` | `Union[Credentials, NoneType]` |
| `.external_access_token_key(value)` | `Union[str, NoneType]` |
| `.client_id(value)` | `Union[str, NoneType]` |
| `.client_secret(value)` | `Union[str, NoneType]` |
| `.scopes(value)` | `Union[list[str], NoneType]` |

---

# BaseToolConfig

> Fluent builder for `google.adk.tools.tool_configs.BaseToolConfig`

The base class for all tool configs.

## Terminal Methods

### `.build() -> BaseToolConfig`

Resolve into a native ADK BaseToolConfig.

---

# ToolArgsConfig

> Fluent builder for `google.adk.tools.tool_configs.ToolArgsConfig`

Config to host free key-value pairs for the args in ToolConfig.

## Terminal Methods

### `.build() -> ToolArgsConfig`

Resolve into a native ADK ToolArgsConfig.

---

# ToolConfig

> Fluent builder for `google.adk.tools.tool_configs.ToolConfig`

The configuration for a tool.

## Constructor

```python
ToolConfig(name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

## Terminal Methods

### `.build() -> ToolConfig`

Resolve into a native ADK ToolConfig.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.args(value)` | `Union[ToolArgsConfig, NoneType]` |
