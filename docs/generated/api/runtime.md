# Module: `runtime`

# App

> Fluent builder for `google.adk.apps.app.App`

Represents an LLM-backed agentic application.

## Constructor

```python
App(name, root_agent)
```

| Argument | Type |
|----------|------|
| `name` | `str` |
| `root_agent` | `BaseAgent` |

## Terminal Methods

### `.build() -> App`

Resolve into a native ADK App.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.plugins(value)` | `list[BasePlugin]` |
| `.events_compaction_config(value)` | `Union[EventsCompactionConfig, NoneType]` |
| `.context_cache_config(value)` | `Union[ContextCacheConfig, NoneType]` |
| `.resumability_config(value)` | `Union[ResumabilityConfig, NoneType]` |

---

# InMemoryRunner

> Fluent builder for `google.adk.runners.InMemoryRunner`

An in-memory Runner for testing and development.

## Terminal Methods

### `.build() -> InMemoryRunner`

Resolve into a native ADK InMemoryRunner.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.agent(value)` | `Optional[BaseAgent]` |
| `.app_name(value)` | `Optional[str]` |
| `.plugins(value)` | `Optional[list[BasePlugin]]` |
| `.app(value)` | `Optional[App]` |
| `.plugin_close_timeout(value)` | `float` |

---

# Runner

> Fluent builder for `google.adk.runners.Runner`

The Runner class is used to run agents.

## Constructor

```python
Runner(session_service)
```

| Argument | Type |
|----------|------|
| `session_service` | `BaseSessionService` |

## Terminal Methods

### `.build() -> Runner`

Resolve into a native ADK Runner.

## Forwarded Fields

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
