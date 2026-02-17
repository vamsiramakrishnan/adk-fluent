# Module: `service`

# BaseArtifactService

> Fluent builder for `google.adk.artifacts.base_artifact_service.BaseArtifactService`

Abstract base class for artifact services.

## Constructor

```python
BaseArtifactService(args, kwargs)
```

| Argument | Type |
|----------|------|
| `args` | `Any` |
| `kwargs` | `Any` |

## Terminal Methods

### `.build() -> BaseArtifactService`

Resolve into a native ADK BaseArtifactService.

---

# FileArtifactService

> Fluent builder for `google.adk.artifacts.file_artifact_service.FileArtifactService`

Stores filesystem-backed artifacts beneath a configurable root directory.

## Constructor

```python
FileArtifactService(root_dir)
```

| Argument | Type |
|----------|------|
| `root_dir` | `Path | str` |

## Terminal Methods

### `.build() -> FileArtifactService`

Resolve into a native ADK FileArtifactService.

---

# GcsArtifactService

> Fluent builder for `google.adk.artifacts.gcs_artifact_service.GcsArtifactService`

An artifact service implementation using Google Cloud Storage (GCS).

## Constructor

```python
GcsArtifactService(bucket_name, kwargs)
```

| Argument | Type |
|----------|------|
| `bucket_name` | `str` |
| `kwargs` | `Any` |

## Terminal Methods

### `.build() -> GcsArtifactService`

Resolve into a native ADK GcsArtifactService.

---

# InMemoryArtifactService

> Fluent builder for `google.adk.artifacts.in_memory_artifact_service.InMemoryArtifactService`

An in-memory implementation of the artifact service.

## Terminal Methods

### `.build() -> InMemoryArtifactService`

Resolve into a native ADK InMemoryArtifactService.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.artifacts(value)` | `dict[str, list[_ArtifactEntry]]` |

---

# PerAgentDatabaseSessionService

> Fluent builder for `google.adk.cli.utils.local_storage.PerAgentDatabaseSessionService`

Routes session storage to per-agent `.adk/session.db` files.

## Constructor

```python
PerAgentDatabaseSessionService(agents_root)
```

| Argument | Type |
|----------|------|
| `agents_root` | `Path | str` |

## Terminal Methods

### `.build() -> PerAgentDatabaseSessionService`

Resolve into a native ADK PerAgentDatabaseSessionService.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.app_name_to_dir(value)` | `Optional[Mapping[str, str]]` |

---

# BaseMemoryService

> Fluent builder for `google.adk.memory.base_memory_service.BaseMemoryService`

Base class for memory services.

## Constructor

```python
BaseMemoryService(args, kwargs)
```

| Argument | Type |
|----------|------|
| `args` | `Any` |
| `kwargs` | `Any` |

## Terminal Methods

### `.build() -> BaseMemoryService`

Resolve into a native ADK BaseMemoryService.

---

# InMemoryMemoryService

> Fluent builder for `google.adk.memory.in_memory_memory_service.InMemoryMemoryService`

An in-memory memory service for prototyping purpose only.

## Terminal Methods

### `.build() -> InMemoryMemoryService`

Resolve into a native ADK InMemoryMemoryService.

---

# VertexAiMemoryBankService

> Fluent builder for `google.adk.memory.vertex_ai_memory_bank_service.VertexAiMemoryBankService`

Implementation of the BaseMemoryService using Vertex AI Memory Bank.

## Terminal Methods

### `.build() -> VertexAiMemoryBankService`

Resolve into a native ADK VertexAiMemoryBankService.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.project(value)` | `Optional[str]` |
| `.location(value)` | `Optional[str]` |
| `.agent_engine_id(value)` | `Optional[str]` |
| `.express_mode_api_key(value)` | `Optional[str]` |

---

# VertexAiRagMemoryService

> Fluent builder for `google.adk.memory.vertex_ai_rag_memory_service.VertexAiRagMemoryService`

A memory service that uses Vertex AI RAG for storage and retrieval.

## Terminal Methods

### `.build() -> VertexAiRagMemoryService`

Resolve into a native ADK VertexAiRagMemoryService.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.rag_corpus(value)` | `Optional[str]` |
| `.similarity_top_k(value)` | `Optional[int]` |
| `.vector_distance_threshold(value)` | `float` |

---

# BaseSessionService

> Fluent builder for `google.adk.sessions.base_session_service.BaseSessionService`

Base class for session services.

## Constructor

```python
BaseSessionService(args, kwargs)
```

| Argument | Type |
|----------|------|
| `args` | `Any` |
| `kwargs` | `Any` |

## Terminal Methods

### `.build() -> BaseSessionService`

Resolve into a native ADK BaseSessionService.

---

# DatabaseSessionService

> Fluent builder for `google.adk.sessions.database_session_service.DatabaseSessionService`

A session service that uses a database for storage.

## Constructor

```python
DatabaseSessionService(db_url, kwargs)
```

| Argument | Type |
|----------|------|
| `db_url` | `str` |
| `kwargs` | `Any` |

## Terminal Methods

### `.build() -> DatabaseSessionService`

Resolve into a native ADK DatabaseSessionService.

---

# InMemorySessionService

> Fluent builder for `google.adk.sessions.in_memory_session_service.InMemorySessionService`

An in-memory implementation of the session service.

## Terminal Methods

### `.build() -> InMemorySessionService`

Resolve into a native ADK InMemorySessionService.

---

# SqliteSessionService

> Fluent builder for `google.adk.sessions.sqlite_session_service.SqliteSessionService`

A session service that uses an SQLite database for storage via aiosqlite.

## Constructor

```python
SqliteSessionService(db_path)
```

| Argument | Type |
|----------|------|
| `db_path` | `str` |

## Terminal Methods

### `.build() -> SqliteSessionService`

Resolve into a native ADK SqliteSessionService.

---

# VertexAiSessionService

> Fluent builder for `google.adk.sessions.vertex_ai_session_service.VertexAiSessionService`

Connects to the Vertex AI Agent Engine Session Service using Agent Engine SDK.

## Terminal Methods

### `.build() -> VertexAiSessionService`

Resolve into a native ADK VertexAiSessionService.

## Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.project(value)` | `Optional[str]` |
| `.location(value)` | `Optional[str]` |
| `.agent_engine_id(value)` | `Optional[str]` |
| `.express_mode_api_key(value)` | `Optional[str]` |

---

# ForwardingArtifactService

> Fluent builder for `google.adk.tools._forwarding_artifact_service.ForwardingArtifactService`

Artifact service that forwards to the parent tool context.

## Constructor

```python
ForwardingArtifactService(tool_context)
```

| Argument | Type |
|----------|------|
| `tool_context` | `ToolContext` |

## Terminal Methods

### `.build() -> ForwardingArtifactService`

Resolve into a native ADK ForwardingArtifactService.
