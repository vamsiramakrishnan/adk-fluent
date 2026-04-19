# Module: `executor`

## Builders in this module

| Builder | Description |
|---------|-------------|
| [A2aAgentExecutor](builder-A2aAgentExecutor) | An AgentExecutor that runs an ADK Agent against an A2A request and. |
| [AgentEngineSandboxCodeExecutor](builder-AgentEngineSandboxCodeExecutor) | A code executor that uses Agent Engine Code Execution Sandbox to execute code. |
| [BaseCodeExecutor](builder-BaseCodeExecutor) | Abstract base class for all code executors. |
| [BuiltInCodeExecutor](builder-BuiltInCodeExecutor) | A code executor that uses the Model's built-in code executor. |
| [UnsafeLocalCodeExecutor](builder-UnsafeLocalCodeExecutor) | A code executor that unsafely execute code in the current local context. |
| [VertexAiCodeExecutor](builder-VertexAiCodeExecutor) | A code executor that uses Vertex Code Interpreter Extension to execute code. |

(builder-A2aAgentExecutor)=
## A2aAgentExecutor

> Fluent builder for `google.adk.a2a.executor.a2a_agent_executor.A2aAgentExecutor`

An AgentExecutor that runs an ADK Agent against an A2A request and.

**Quick start:**

```python
from adk_fluent import A2aAgentExecutor

result = (
    A2aAgentExecutor("runner_value")
    .build()
)
```

### Constructor

```python
A2aAgentExecutor(runner: Runner | Callable[..., Runner | Awaitable[Runner]])
```

| Argument | Type |
|----------|------|
| `runner` | `Runner | Callable[..., Runner | Awaitable[Runner]]` |

### Control Flow & Execution

(method-A2aAgentExecutor-build)=
#### `.build() -> A2aAgentExecutor` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK A2aAgentExecutor.

**Example:**

```python
a2aagentexecutor = A2aAgentExecutor("a2aagentexecutor").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.config(value)` | `A2aAgentExecutorConfig | None` |

---

(builder-AgentEngineSandboxCodeExecutor)=
## AgentEngineSandboxCodeExecutor

> Fluent builder for `google.adk.code_executors.agent_engine_sandbox_code_executor.AgentEngineSandboxCodeExecutor`

A code executor that uses Agent Engine Code Execution Sandbox to execute code.

**Quick start:**

```python
from adk_fluent import AgentEngineSandboxCodeExecutor

result = (
    AgentEngineSandboxCodeExecutor()
    .code_block_delimiter(...)
    .build()
)
```

### Configuration

(method-AgentEngineSandboxCodeExecutor-code_block_delimiter)=
#### `.code_block_delimiter(value: tuple[str, str]) -> Self` {bdg-info}`Configuration`

Append to `code_block_delimiters` (lazy — built at .build() time).

**Example:**

```python
agentenginesandboxcodeexecutor = AgentEngineSandboxCodeExecutor("agentenginesandboxcodeexecutor").code_block_delimiter("...")
```

### Control Flow & Execution

(method-AgentEngineSandboxCodeExecutor-build)=
#### `.build() -> AgentEngineSandboxCodeExecutor` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK AgentEngineSandboxCodeExecutor.

**Example:**

```python
agentenginesandboxcodeexecutor = AgentEngineSandboxCodeExecutor("agentenginesandboxcodeexecutor").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.optimize_data_file(value)` | {py:class}`bool` |
| `.stateful(value)` | {py:class}`bool` |
| `.error_retry_attempts(value)` | {py:class}`int` |
| `.code_block_delimiters(value)` | `list[tuple[str, str]]` |
| `.execution_result_delimiters(value)` | `tuple[str, str]` |
| `.sandbox_resource_name(value)` | {py:class}`str` |

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
    .code_block_delimiter(...)
    .build()
)
```

### Configuration

(method-BaseCodeExecutor-code_block_delimiter)=
#### `.code_block_delimiter(value: tuple[str, str]) -> Self` {bdg-info}`Configuration`

Append to `code_block_delimiters` (lazy — built at .build() time).

**Example:**

```python
basecodeexecutor = BaseCodeExecutor("basecodeexecutor").code_block_delimiter("...")
```

### Control Flow & Execution

(method-BaseCodeExecutor-build)=
#### `.build() -> BaseCodeExecutor` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BaseCodeExecutor.

**Example:**

```python
basecodeexecutor = BaseCodeExecutor("basecodeexecutor").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.optimize_data_file(value)` | {py:class}`bool` |
| `.stateful(value)` | {py:class}`bool` |
| `.error_retry_attempts(value)` | {py:class}`int` |
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
    .code_block_delimiter(...)
    .build()
)
```

### Configuration

(method-BuiltInCodeExecutor-code_block_delimiter)=
#### `.code_block_delimiter(value: tuple[str, str]) -> Self` {bdg-info}`Configuration`

Append to `code_block_delimiters` (lazy — built at .build() time).

**Example:**

```python
builtincodeexecutor = BuiltInCodeExecutor("builtincodeexecutor").code_block_delimiter("...")
```

### Control Flow & Execution

(method-BuiltInCodeExecutor-build)=
#### `.build() -> BuiltInCodeExecutor` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK BuiltInCodeExecutor.

**Example:**

```python
builtincodeexecutor = BuiltInCodeExecutor("builtincodeexecutor").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.optimize_data_file(value)` | {py:class}`bool` |
| `.stateful(value)` | {py:class}`bool` |
| `.error_retry_attempts(value)` | {py:class}`int` |
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
    .code_block_delimiter(...)
    .build()
)
```

### Configuration

(method-UnsafeLocalCodeExecutor-code_block_delimiter)=
#### `.code_block_delimiter(value: tuple[str, str]) -> Self` {bdg-info}`Configuration`

Append to `code_block_delimiters` (lazy — built at .build() time).

**Example:**

```python
unsafelocalcodeexecutor = UnsafeLocalCodeExecutor("unsafelocalcodeexecutor").code_block_delimiter("...")
```

### Control Flow & Execution

(method-UnsafeLocalCodeExecutor-build)=
#### `.build() -> UnsafeLocalCodeExecutor` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK UnsafeLocalCodeExecutor.

**Example:**

```python
unsafelocalcodeexecutor = UnsafeLocalCodeExecutor("unsafelocalcodeexecutor").build("...")
```

### Forwarded Fields

These fields are available via `__getattr__` forwarding.

| Field | Type |
|-------|------|
| `.optimize_data_file(value)` | {py:class}`bool` |
| `.stateful(value)` | {py:class}`bool` |
| `.error_retry_attempts(value)` | {py:class}`int` |
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

### Control Flow & Execution

(method-VertexAiCodeExecutor-build)=
#### `.build() -> VertexAiCodeExecutor` {bdg-primary}`Control Flow & Execution`

Resolve into a native ADK VertexAiCodeExecutor.

**Example:**

```python
vertexaicodeexecutor = VertexAiCodeExecutor("vertexaicodeexecutor").build("...")
```

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
