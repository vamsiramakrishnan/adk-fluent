# IR and Backends

The Intermediate Representation (IR) decouples the fluent builder API from ADK. Builders compile to a tree of frozen dataclasses, which backends then compile to native objects.

## Why IR?

- **Inspection**: Walk and analyze the agent tree without building ADK objects
- **Testing**: Use mock backends for deterministic testing without LLM calls
- **Visualization**: Generate Mermaid diagrams from the IR tree
- **Portability**: Future backends could target different execution engines

## IR Nodes

Every builder maps to an IR node type:

| Builder           | IR Node         | ADK Type                 |
| ----------------- | --------------- | ------------------------ |
| `Agent`           | `AgentNode`     | `LlmAgent`               |
| `Pipeline` / `>>` | `SequenceNode`  | `SequentialAgent`        |
| `FanOut` / `\|`   | `ParallelNode`  | `ParallelAgent`          |
| `Loop` / `*`      | `LoopNode`      | `LoopAgent`              |
| `>> fn`           | `TransformNode` | `FnAgent` (custom)       |
| `tap(fn)`         | `TapNode`       | `TapAgent` (custom)      |
| `a // b`          | `FallbackNode`  | `FallbackAgent` (custom) |
| `race(a, b)`      | `RaceNode`      | `RaceAgent` (custom)     |
| `gate(pred)`      | `GateNode`      | `GateAgent` (custom)     |
| `Route(...)`      | `RouteNode`     | `_RouteAgent` (custom)   |

IR nodes are frozen dataclasses -- immutable and safe to inspect:

```python
from adk_fluent import Agent

pipeline = Agent("a").instruct("Step 1.") >> Agent("b").instruct("Step 2.")
ir = pipeline.to_ir()

# SequenceNode with two AgentNode children
print(type(ir).__name__)  # SequenceNode
print(len(ir.children))   # 2
print(ir.children[0].name)  # a
print(ir.children[1].name)  # b
```

## Backend Protocol

A backend compiles IR nodes into runnable objects:

```python
from adk_fluent.backends import Backend

class Backend(Protocol):
    def compile(self, node, config=None) -> Any: ...
    async def run(self, compiled, prompt, **kwargs) -> list[AgentEvent]: ...
    async def stream(self, compiled, prompt, **kwargs) -> AsyncIterator[AgentEvent]: ...
```

### ADKBackend

The built-in `ADKBackend` compiles IR to native ADK objects:

```python
from adk_fluent.backends.adk import ADKBackend
from adk_fluent import Agent, ExecutionConfig

backend = ADKBackend()
ir = (Agent("a") >> Agent("b")).to_ir()
app = backend.compile(ir, config=ExecutionConfig(app_name="demo"))
```

`.to_app()` is shorthand for this -- it creates an ADKBackend internally.

## ExecutionConfig

Configuration for the compiled App:

```python
from adk_fluent import ExecutionConfig, CompactionConfig

config = ExecutionConfig(
    app_name="my_app",               # App name (default: "adk_fluent_app")
    resumable=True,                   # Enable session resumability
    compaction=CompactionConfig(      # Event compaction settings
        interval=10,                  # Compact every N events
        overlap=2,                    # Keep N events of overlap
    ),
    middlewares=(retry_mw, log_mw),   # Middleware stack
)
```

| Field         | Type                       | Default            | Description                 |
| ------------- | -------------------------- | ------------------ | --------------------------- |
| `app_name`    | `str`                      | `"adk_fluent_app"` | Application name            |
| `resumable`   | `bool`                     | `False`            | Enable session resumability |
| `compaction`  | `CompactionConfig \| None` | `None`             | Event compaction settings   |
| `middlewares` | `tuple`                    | `()`               | Middleware stack            |

## Visualization

`.to_mermaid()` generates a Mermaid graph from the IR:

```python
from adk_fluent import Agent

pipeline = Agent("classifier") >> Agent("resolver") >> Agent("responder")
print(pipeline.to_mermaid())
```

Output:

```
graph TD
    n1[["classifier_then_resolver_then_responder (sequence)"]]
    n2["classifier"]
    n3["resolver"]
    n4["responder"]
    n2 --> n3
    n3 --> n4
```

When agents have `.produces()` or `.consumes()` annotations, the diagram includes data-flow edges.
