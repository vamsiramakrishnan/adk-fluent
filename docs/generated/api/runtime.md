# Module: `runtime`

## Builders in this module

| Builder | Description |
|---------|-------------|
| [App](builder-App) | Represents an LLM-backed agentic application. |
| [InMemoryRunner](builder-InMemoryRunner) | An in-memory Runner for testing and development. |
| [Runner](builder-Runner) | The Runner class is used to run agents. |

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

| Argument | Type |
|----------|------|
| `name` | `str` |
| `root_agent` | `BaseAgent` |

### Configuration

#### `.plugin(value: BasePlugin) -> Self`

Append to ``plugins`` (lazy — built at .build() time).

### Control Flow & Execution

#### `.build() -> App`

Resolve into a native ADK App.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.plugins(value)` | `list[BasePlugin]` |
| `.events_compaction_config(value)` | `Union[EventsCompactionConfig, NoneType]` |
| `.context_cache_config(value)` | `Union[ContextCacheConfig, NoneType]` |
| `.resumability_config(value)` | `Union[ResumabilityConfig, NoneType]` |

---

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

| Field | Type |
|-------|------|
| `.agent(value)` | `Optional[BaseAgent]` |
| `.app_name(value)` | `Optional[str]` |
| `.plugins(value)` | `Optional[list[BasePlugin]]` |
| `.app(value)` | `Optional[App]` |
| `.plugin_close_timeout(value)` | `float` |

---

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

| Argument | Type |
|----------|------|
| `session_service` | `BaseSessionService` |

### Control Flow & Execution

#### `.build() -> Runner`

Resolve into a native ADK Runner.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.app(value)` | `Optional[App]` |
| `.app_name(value)` | `Optional[str]` |
| `.agent(value)` | `Optional[BaseAgent]` |
| `.plugins(value)` | `Optional[List[BasePlugin]]` |
| `.artifact_service(value)` | `Optional[BaseArtifactService]` |
| `.memory_service(value)` | `Optional[BaseMemoryService]` |
| `.credential_service(value)` | `Optional[BaseCredentialService]` |
| `.plugin_close_timeout(value)` | `float` |
| `.auto_create_session(value)` | `bool` |
