# Module: `plugin`

# RecordingsPlugin

> Fluent builder for `google.adk.cli.plugins.recordings_plugin.RecordingsPlugin`

Plugin for recording ADK agent interactions.

## Terminal Methods

### `.build() -> RecordingsPlugin`

Resolve into a native ADK RecordingsPlugin.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | `str` |

---

# ReplayPlugin

> Fluent builder for `google.adk.cli.plugins.replay_plugin.ReplayPlugin`

Plugin for replaying ADK agent interactions from recordings.

## Terminal Methods

### `.build() -> ReplayPlugin`

Resolve into a native ADK ReplayPlugin.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | `str` |

---

# BasePlugin

> Fluent builder for `google.adk.plugins.base_plugin.BasePlugin`

Base class for creating plugins.

## Constructor

```python
BasePlugin(name)
```

| Argument | Type |
|----------|------|
| `name` | `str` |

## Terminal Methods

### `.build() -> BasePlugin`

Resolve into a native ADK BasePlugin.

---

# BigQueryAgentAnalyticsPlugin

> Fluent builder for `google.adk.plugins.bigquery_agent_analytics_plugin.BigQueryAgentAnalyticsPlugin`

BigQuery Agent Analytics Plugin (v2.0 using Write API).

## Constructor

```python
BigQueryAgentAnalyticsPlugin(project_id, dataset_id, kwargs)
```

| Argument | Type |
|----------|------|
| `project_id` | `str` |
| `dataset_id` | `str` |
| `kwargs` | `Any` |

## Terminal Methods

### `.build() -> BigQueryAgentAnalyticsPlugin`

Resolve into a native ADK BigQueryAgentAnalyticsPlugin.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.table_id(value)` | `Optional[str]` |
| `.config(value)` | `Optional[BigQueryLoggerConfig]` |
| `.location(value)` | `str` |

---

# ContextFilterPlugin

> Fluent builder for `google.adk.plugins.context_filter_plugin.ContextFilterPlugin`

A plugin that filters the LLM context to reduce its size.

## Terminal Methods

### `.build() -> ContextFilterPlugin`

Resolve into a native ADK ContextFilterPlugin.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.num_invocations_to_keep(value)` | `Optional[int]` |
| `.custom_filter(value)` | `Optional[Callable[[list[types.Content]], list[types.Content]]]` |
| `.name(value)` | `str` |

---

# DebugLoggingPlugin

> Fluent builder for `google.adk.plugins.debug_logging_plugin.DebugLoggingPlugin`

A plugin that captures complete debug information to a file.

## Terminal Methods

### `.build() -> DebugLoggingPlugin`

Resolve into a native ADK DebugLoggingPlugin.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | `str` |
| `.output_path(value)` | `str` |
| `.include_session_state(value)` | `bool` |
| `.include_system_instruction(value)` | `bool` |

---

# GlobalInstructionPlugin

> Fluent builder for `google.adk.plugins.global_instruction_plugin.GlobalInstructionPlugin`

Plugin that provides global instructions functionality at the App level.

## Terminal Methods

### `.build() -> GlobalInstructionPlugin`

Resolve into a native ADK GlobalInstructionPlugin.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.global_instruction(value)` | `Union[str, InstructionProvider]` |
| `.name(value)` | `str` |

---

# LoggingPlugin

> Fluent builder for `google.adk.plugins.logging_plugin.LoggingPlugin`

A plugin that logs important information at each callback point.

## Terminal Methods

### `.build() -> LoggingPlugin`

Resolve into a native ADK LoggingPlugin.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | `str` |

---

# MultimodalToolResultsPlugin

> Fluent builder for `google.adk.plugins.multimodal_tool_results_plugin.MultimodalToolResultsPlugin`

A plugin that modifies function tool responses to support returning list of parts directly.

## Terminal Methods

### `.build() -> MultimodalToolResultsPlugin`

Resolve into a native ADK MultimodalToolResultsPlugin.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | `str` |

---

# ReflectAndRetryToolPlugin

> Fluent builder for `google.adk.plugins.reflect_retry_tool_plugin.ReflectAndRetryToolPlugin`

Provides self-healing, concurrent-safe error recovery for tool failures.

## Terminal Methods

### `.build() -> ReflectAndRetryToolPlugin`

Resolve into a native ADK ReflectAndRetryToolPlugin.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | `str` |
| `.max_retries(value)` | `int` |
| `.throw_exception_if_retry_exceeded(value)` | `bool` |
| `.tracking_scope(value)` | `TrackingScope` |

---

# SaveFilesAsArtifactsPlugin

> Fluent builder for `google.adk.plugins.save_files_as_artifacts_plugin.SaveFilesAsArtifactsPlugin`

A plugin that saves files embedded in user messages as artifacts.

## Terminal Methods

### `.build() -> SaveFilesAsArtifactsPlugin`

Resolve into a native ADK SaveFilesAsArtifactsPlugin.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.name(value)` | `str` |

---

# AgentSimulatorPlugin

> Fluent builder for `google.adk.tools.agent_simulator.agent_simulator_plugin.AgentSimulatorPlugin`

ADK Plugin for AgentSimulator.

## Constructor

```python
AgentSimulatorPlugin(simulator_engine)
```

| Argument | Type |
|----------|------|
| `simulator_engine` | `AgentSimulatorEngine` |

## Terminal Methods

### `.build() -> AgentSimulatorPlugin`

Resolve into a native ADK AgentSimulatorPlugin.
