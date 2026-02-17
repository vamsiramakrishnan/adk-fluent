# Module: `executor`

## Builders in this module

| Builder | Description |
|---------|-------------|
| [AgentEngineSandboxCodeExecutor](builder-AgentEngineSandboxCodeExecutor) | A code executor that uses Agent Engine Code Execution Sandbox to execute code. |
| [BaseCodeExecutor](builder-BaseCodeExecutor) | Abstract base class for all code executors. |
| [BuiltInCodeExecutor](builder-BuiltInCodeExecutor) | A code executor that uses the Model's built-in code executor. |
| [UnsafeLocalCodeExecutor](builder-UnsafeLocalCodeExecutor) | A code executor that unsafely execute code in the current local context. |
| [VertexAiCodeExecutor](builder-VertexAiCodeExecutor) | A code executor that uses Vertex Code Interpreter Extension to execute code. |

(builder-AgentEngineSandboxCodeExecutor)=
## AgentEngineSandboxCodeExecutor

> Fluent builder for `google.adk.code_executors.agent_engine_sandbox_code_executor.AgentEngineSandboxCodeExecutor`

A code executor that uses Agent Engine Code Execution Sandbox to execute code.

**Quick start:**

```python
from adk_fluent import AgentEngineSandboxCodeExecutor

result = (
    AgentEngineSandboxCodeExecutor()
    .build()
)
```

### Terminal Methods

#### `.build() -> AgentEngineSandboxCodeExecutor`

Resolve into a native ADK AgentEngineSandboxCodeExecutor.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.optimize_data_file(value)` | `bool` |
| `.stateful(value)` | `bool` |
| `.error_retry_attempts(value)` | `int` |
| `.code_block_delimiters(value)` | `list[tuple[str, str]]` |
| `.execution_result_delimiters(value)` | `tuple[str, str]` |
| `.sandbox_resource_name(value)` | `str` |

---

(builder-BaseCodeExecutor)=
## BaseCodeExecutor

> Fluent builder for `google.adk.code_executors.base_code_executor.BaseCodeExecutor`

Abstract base class for all code executors.

**Quick start:**

```python
from adk_fluent import BaseCodeExecutor

result = (
    BaseCodeExecutor()
    .build()
)
```

### Terminal Methods

#### `.build() -> BaseCodeExecutor`

Resolve into a native ADK BaseCodeExecutor.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.optimize_data_file(value)` | `bool` |
| `.stateful(value)` | `bool` |
| `.error_retry_attempts(value)` | `int` |
| `.code_block_delimiters(value)` | `list[tuple[str, str]]` |
| `.execution_result_delimiters(value)` | `tuple[str, str]` |

---

(builder-BuiltInCodeExecutor)=
## BuiltInCodeExecutor

> Fluent builder for `google.adk.code_executors.built_in_code_executor.BuiltInCodeExecutor`

A code executor that uses the Model's built-in code executor.

**Quick start:**

```python
from adk_fluent import BuiltInCodeExecutor

result = (
    BuiltInCodeExecutor()
    .build()
)
```

### Terminal Methods

#### `.build() -> BuiltInCodeExecutor`

Resolve into a native ADK BuiltInCodeExecutor.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.optimize_data_file(value)` | `bool` |
| `.stateful(value)` | `bool` |
| `.error_retry_attempts(value)` | `int` |
| `.code_block_delimiters(value)` | `list[tuple[str, str]]` |
| `.execution_result_delimiters(value)` | `tuple[str, str]` |

---

(builder-UnsafeLocalCodeExecutor)=
## UnsafeLocalCodeExecutor

> Fluent builder for `google.adk.code_executors.unsafe_local_code_executor.UnsafeLocalCodeExecutor`

A code executor that unsafely execute code in the current local context.

**Quick start:**

```python
from adk_fluent import UnsafeLocalCodeExecutor

result = (
    UnsafeLocalCodeExecutor()
    .build()
)
```

### Terminal Methods

#### `.build() -> UnsafeLocalCodeExecutor`

Resolve into a native ADK UnsafeLocalCodeExecutor.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.optimize_data_file(value)` | `bool` |
| `.stateful(value)` | `bool` |
| `.error_retry_attempts(value)` | `int` |
| `.code_block_delimiters(value)` | `list[tuple[str, str]]` |
| `.execution_result_delimiters(value)` | `tuple[str, str]` |

---

(builder-VertexAiCodeExecutor)=
## VertexAiCodeExecutor

> Fluent builder for `google.adk.code_executors.vertex_ai_code_executor.VertexAiCodeExecutor`

A code executor that uses Vertex Code Interpreter Extension to execute code.

**Quick start:**

```python
from adk_fluent import VertexAiCodeExecutor

result = (
    VertexAiCodeExecutor()
    .build()
)
```

### Terminal Methods

#### `.build() -> VertexAiCodeExecutor`

Resolve into a native ADK VertexAiCodeExecutor.

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.optimize_data_file(value)` | `Any` |
| `.stateful(value)` | `Any` |
| `.error_retry_attempts(value)` | `Any` |
| `.code_block_delimiters(value)` | `Any` |
| `.execution_result_delimiters(value)` | `Any` |
| `.resource_name(value)` | `Any` |
