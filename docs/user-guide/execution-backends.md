# Execution Backends

adk-fluent decouples **what** your agent does (builders, operators, namespaces) from **how** it runs (the execution engine). The same builder definition can compile to different backends with different durability, scheduling, and deployment characteristics.

:::{admonition} Backend maturity
:class: important

| Backend | Status | Install |
|---------|--------|---------|
| **ADK** | **Stable** — production-ready, default backend | `pip install adk-fluent` |
| **Temporal** | **In Development** — API may change, core compile/run path works | `pip install adk-fluent[temporal]` |
| **asyncio** | **In Development** — reference implementation, no durability | `pip install adk-fluent` (included) |
| **DBOS** | **Conceptual** — under research, not yet implemented | — |
| **Prefect** | **Conceptual** — under research, not yet implemented | — |

Only the ADK backend is recommended for production use today. Temporal support is actively being built and is available for early experimentation. DBOS and Prefect are being evaluated as future backend candidates — no code exists yet.
:::

## How It Works

```
Builder → .to_ir() → IR Tree → Backend.compile() → Runnable → Backend.run()
                                    ↑
                              engine selection
```

1. Builders produce an **IR tree** (frozen dataclasses, zero ADK imports)
2. A **Backend** compiles the IR to engine-specific runnables
3. The backend **executes** the runnable with session and state management

The IR is the universal contract. Every backend must be implementable from IR alone.

## Selecting a Backend

### Per-agent: `.engine()`

```python
from adk_fluent import Agent

# Default — ADK backend (no .engine() needed)
agent = Agent("helper", "gemini-2.5-flash").instruct("Help.")

# Explicit ADK selection
agent = Agent("helper", "gemini-2.5-flash").instruct("Help.").engine("adk")

# Temporal backend (requires pip install adk-fluent[temporal])
agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("Help.")
    .engine("temporal", client=temporal_client, task_queue="agents")
)

# Asyncio backend (zero-dependency reference implementation)
agent = Agent("helper", "gemini-2.5-flash").instruct("Help.").engine("asyncio")
```

`.engine()` accepts the backend name as the first argument and forwards keyword arguments to the backend constructor.

### Global default: `configure()`

```python
import adk_fluent

adk_fluent.configure(engine="temporal", engine_config={"client": temporal_client})

# All agents now use Temporal by default
response = await Agent("x").instruct("...").ask_async("hello")
```

### Direct backend instantiation

For full control, create a backend directly and use it with the compile layer:

```python
from adk_fluent.backends.adk import ADKBackend
from adk_fluent.compile import compile

backend = ADKBackend()
ir = (Agent("a") >> Agent("b")).to_ir()
result = compile(ir, backend=backend)
```

## Backend Comparison

### ADK Backend (Stable)

The default backend. Compiles IR to native ADK objects (`LlmAgent`, `SequentialAgent`, etc.) and executes via ADK's `InMemoryRunner`.

```python
# This is the default — you don't need to specify it
agent = Agent("writer", "gemini-2.5-flash").instruct("Write a story.")
response = agent.ask("Tell me about space exploration.")
```

**Capabilities:**
- Streaming: Yes
- Parallel execution: Yes
- Durable execution: No
- Crash recovery: No
- Distributed: No
- Human-in-the-loop signals: No

**When to use:** Prototyping, development, production workloads that don't need crash recovery or durability.

### Temporal Backend (In Development)

:::{admonition} In Development
:class: warning

The Temporal backend is under active development. The compile path and basic run path work, but the API may change. Not recommended for production use yet. Contributions and feedback are welcome.
:::

Compiles IR to Temporal workflows and activities. LLM calls become activities (cached on replay); deterministic nodes become workflow code.

```python
from temporalio.client import Client
from adk_fluent import Agent

# Connect to Temporal
client = await Client.connect("localhost:7233")

# Select Temporal backend
agent = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic thoroughly.")
    .engine("temporal", client=client, task_queue="research")
)

response = await agent.ask_async("quantum computing advances")
```

**Capabilities:**
- Streaming: No (falls back to collecting all events)
- Parallel execution: Yes
- Durable execution: Yes — survives process crashes
- Crash recovery: Yes — replays from checkpoint, zero repeated LLM cost
- Distributed: Yes — runs across multiple workers
- Human-in-the-loop signals: Yes (via `GateNode`)

**IR → Temporal mapping:**

| IR Node | Temporal Concept | Deterministic? |
|---------|-----------------|---------------|
| `AgentNode` | Activity (LLM call = I/O) | No |
| `SequenceNode` | Workflow body (sequential awaits) | Yes |
| `ParallelNode` | Workflow with `asyncio.gather()` | Yes |
| `LoopNode` | Workflow `while` loop (checkpointed) | Yes |
| `TransformNode` | Inline workflow code (pure function) | Yes |
| `RouteNode` | Inline workflow code (switch) | Yes |
| `FallbackNode` | Workflow try/except chain | Yes |
| `GateNode` | `workflow.wait_condition()` + Signal | Yes |

**Crash recovery example:**

```
Pipeline: researcher → writer → reviewer

Step 1: researcher runs (Activity) → checkpoint saved
Step 2: writer runs (Activity) → checkpoint saved
Step 3: CRASH during reviewer

On restart:
- Temporal replays workflow from history
- researcher: returns cached result (zero LLM cost)
- writer: returns cached result (zero LLM cost)
- reviewer: re-executes (only this LLM call is made)
```

**Constraints:**
- All workflow code must be deterministic — no `random()`, `datetime.now()`, or I/O in workflow code
- `.stream()` is not natively supported — falls back to run-then-yield
- Requires a running Temporal server (`temporal server start-dev` for local development)

See [Temporal Guide](temporal-guide.md) for detailed patterns and constraints.

### Asyncio Backend (In Development)

:::{admonition} In Development
:class: warning

The asyncio backend is a reference implementation that proves the backend abstraction works without any external engine. It is under development and not recommended for production use.
:::

Direct IR interpreter using plain `asyncio`. No durability, no external dependencies.

```python
agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("Help the user.")
    .engine("asyncio")
)

response = await agent.ask_async("What is the capital of France?")
```

**Capabilities:**
- Streaming: Yes
- Parallel execution: Yes
- Durable execution: No
- Crash recovery: No
- Distributed: No
- Human-in-the-loop signals: No

**When to use:** Testing the backend abstraction, environments where ADK is not available, educational purposes.

### Future Backends (Conceptual)

:::{admonition} Under Research
:class: note

The following backends are being **evaluated as concepts only**. No implementation exists. They are listed here to show the architecture's extensibility, not as commitments.
:::

| Backend | Concept | Potential Fit |
|---------|---------|--------------|
| **DBOS** | Durable functions with PostgreSQL | Lightweight durability without Temporal infrastructure |
| **Prefect** | Flow orchestration with observability | Teams already using Prefect for data pipelines |

## Engine Capabilities

Every backend declares its capabilities via `EngineCapabilities`:

```python
from adk_fluent.compile import EngineCapabilities
from adk_fluent.backends import get_backend

backend = get_backend("adk")
caps = backend.capabilities

print(caps.streaming)      # True
print(caps.durable)        # False
print(caps.checkpointing)  # False
```

| Capability | ADK | Temporal | asyncio |
|------------|-----|----------|---------|
| `streaming` | Yes | No | Yes |
| `parallel` | Yes | Yes | Yes |
| `durable` | No | Yes | No |
| `replay` | No | Yes | No |
| `checkpointing` | No | Yes | No |
| `signals` | No | Yes | No |
| `dispatch_join` | Yes | Yes | Yes |
| `distributed` | No | Yes | No |

## Backend Registry

Backends self-register. You can query the registry:

```python
from adk_fluent.backends import available_backends, get_backend

print(available_backends())  # ['adk', 'asyncio', 'temporal']

backend = get_backend("temporal", client=client, task_queue="my-queue")
```

### Custom backends

Implement the `Backend` protocol to create your own:

```python
from adk_fluent.backends._protocol import Backend

class MyBackend:
    name = "custom"

    def compile(self, node, config=None):
        # IR → your engine's runnable
        ...

    async def run(self, compiled, prompt, **kwargs):
        # Execute and return events
        ...

    async def stream(self, compiled, prompt, **kwargs):
        # Stream events (or fall back to run)
        events = await self.run(compiled, prompt, **kwargs)
        for e in events:
            yield e

    @property
    def capabilities(self):
        from adk_fluent.compile import EngineCapabilities
        return EngineCapabilities(streaming=True, parallel=True)
```

Register it:

```python
from adk_fluent.backends import register_backend
register_backend("custom", lambda **kw: MyBackend(**kw))
```

## Choosing a Backend

| Situation | Recommended Backend |
|-----------|-------------------|
| Prototyping / development | **ADK** (default) |
| Production without durability needs | **ADK** |
| Long-running pipelines that must survive crashes | **Temporal** (when stable) |
| Distributed multi-worker execution | **Temporal** (when stable) |
| Human-in-the-loop approval workflows | **Temporal** (when stable) |
| Testing backend abstraction | **asyncio** |
| Existing Prefect/DBOS infrastructure | Watch for future backends |

:::{tip}
Start with the ADK backend. If you later need durability or distribution, switch to Temporal by adding `.engine("temporal", ...)` — your builder definitions don't change.
:::

:::{seealso}
- [IR & Backends](ir-and-backends.md) — IR node types and the compilation pipeline
- [Temporal Guide](temporal-guide.md) — Temporal-specific patterns, constraints, and examples
- [Execution](execution.md) — `.ask()`, `.stream()`, `.session()` and how they interact with backends
- [Middleware](middleware.md) — pipeline-wide middleware works across all backends
:::
