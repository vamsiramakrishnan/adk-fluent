# Module: `runtime`

## Builders in this module

| Builder                                  | Description                                      |
| ---------------------------------------- | ------------------------------------------------ |
| [App](builder-App)                       | Represents an LLM-backed agentic application.    |
| [InMemoryRunner](builder-InMemoryRunner) | An in-memory Runner for testing and development. |
| [Runner](builder-Runner)                 | The Runner class is used to run agents.          |

(builder-App)=

## App

> Fluent builder for `google.adk.apps.app.App`

Represents an LLM-backed agentic application.

**Quick start:**

```python
from adk_fluent import App

result = (
    App("name_value", "root_agent_value")
    .plugin(...)
    .build()
)
```

### Constructor

```python
App(name: str, root_agent: BaseAgent)
```

| Argument     | Type        |
| ------------ | ----------- |
| `name`       | `str`       |
| `root_agent` | `BaseAgent` |

### Configuration

#### `.plugin(value: BasePlugin) -> Self`

Append to `plugins` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> App`

Resolve into a native ADK App.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                              | Type                     |
| ---------------------------------- | ------------------------ |
| `.plugins(value)`                  | `list[BasePlugin]`       |
| `.events_compaction_config(value)` | \`EventsCompactionConfig |
| `.context_cache_config(value)`     | \`ContextCacheConfig     |
| `.resumability_config(value)`      | \`ResumabilityConfig     |

______________________________________________________________________

(builder-InMemoryRunner)=

## InMemoryRunner

> Fluent builder for `google.adk.runners.InMemoryRunner`

An in-memory Runner for testing and development.

**Quick start:**

```python
from adk_fluent import InMemoryRunner

result = (
    InMemoryRunner()
    .build()
)
```

### Control Flow & Execution

#### `.build() -> InMemoryRunner`

Resolve into a native ADK InMemoryRunner.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type                 |
| ------------------------------ | -------------------- |
| `.agent(value)`                | \`BaseAgent          |
| `.app_name(value)`             | \`str                |
| `.plugins(value)`              | \`list\[BasePlugin\] |
| `.app(value)`                  | \`App                |
| `.plugin_close_timeout(value)` | `float`              |

______________________________________________________________________

(builder-Runner)=

## Runner

> Fluent builder for `google.adk.runners.Runner`

The Runner class is used to run agents.

**Quick start:**

```python
from adk_fluent import Runner

result = (
    Runner("session_service_value")
    .build()
)
```

### Constructor

```python
Runner(session_service: BaseSessionService)
```

| Argument          | Type                 |
| ----------------- | -------------------- |
| `session_service` | `BaseSessionService` |

### Control Flow & Execution

#### `.build() -> Runner`

Resolve into a native ADK Runner.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field                          | Type                    |
| ------------------------------ | ----------------------- |
| `.app(value)`                  | \`App                   |
| `.app_name(value)`             | \`str                   |
| `.agent(value)`                | \`BaseAgent             |
| `.plugins(value)`              | \`list\[BasePlugin\]    |
| `.artifact_service(value)`     | \`BaseArtifactService   |
| `.memory_service(value)`       | \`BaseMemoryService     |
| `.credential_service(value)`   | \`BaseCredentialService |
| `.plugin_close_timeout(value)` | `float`                 |
| `.auto_create_session(value)`  | `bool`                  |
