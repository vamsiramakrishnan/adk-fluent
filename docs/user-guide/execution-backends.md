# Execution Backends

:::{admonition} At a Glance
:class: tip

- Three backends: ADK (stable, production), Temporal (in dev, durable), asyncio (in dev, zero-dep)
- Same builder code works across all backends --- only `.engine()` call changes
- Default is ADK --- you don't need to choose a backend to get started
:::

adk-fluent decouples **what** your agent does (builders, operators, namespaces) from **how** it runs (the execution engine). The same builder definition can compile to different backends with different durability, scheduling, and deployment characteristics.

:::{admonition} Backend maturity
:class: important

| Backend | Status | Install |
|---------|--------|---------|
| **ADK** | **Stable** — production-ready, default backend | `pip install adk-fluent` |
| **Temporal** | **In Development** — API may change, core compile/run path works | `pip install adk-fluent[temporal]` |
| **asyncio** | **In Development** — reference implementation, no durability | `pip install adk-fluent` (included) |
| **Prefect** | **In Development** — compile + plan generation works | `pip install adk-fluent[prefect]` |
| **DBOS** | **In Development** — compile + plan generation works | `pip install adk-fluent[dbos]` |

Only the ADK backend is recommended for production use today. Temporal, Prefect, and DBOS support is actively being built and available for early experimentation.
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

`.engine()` accepts the backend name as the first argument and forwards keyword arguments to the backend constructor.

::::{tab-set}
:::{tab-item} ADK (default)
```python
from adk_fluent import Agent

# No .engine() needed — ADK is the default
agent = Agent("helper", "gemini-2.5-flash").instruct("Help.")
response = agent.ask("What is 2+2?")
```
:::
:::{tab-item} Temporal (in dev)
```python
from temporalio.client import Client
from adk_fluent import Agent

client = await Client.connect("localhost:7233")

agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("Help.")
    .engine("temporal", client=client, task_queue="agents")
)
response = await agent.ask_async("What is 2+2?")
```
:::
:::{tab-item} asyncio (in dev)
```python
from adk_fluent import Agent

agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("Help.")
    .engine("asyncio")
)
response = await agent.ask_async("What is 2+2?")
```
:::
::::

### Global default: `configure()`

```python
import adk_fluent

adk_fluent.configure(engine="temporal", engine_config={"client": temporal_client})

# All agents now use Temporal by default
response = await Agent("x").instruct("...").ask_async("hello")
```

### Direct backend instantiation

For full control, create a backend directly and use it with the compile layer:

::::{tab-set}
:::{tab-item} ADK
```python
from adk_fluent.backends.adk import ADKBackend
from adk_fluent.compile import compile

backend = ADKBackend()
ir = (Agent("a") >> Agent("b")).to_ir()
result = compile(ir, backend=backend)
```
:::
:::{tab-item} Temporal (in dev)
```python
from temporalio.client import Client
from adk_fluent.backends.temporal import TemporalBackend
from adk_fluent.compile import compile

client = await Client.connect("localhost:7233")
backend = TemporalBackend(client=client, task_queue="agents")
ir = (Agent("a") >> Agent("b")).to_ir()
result = compile(ir, backend=backend)
```
:::
:::{tab-item} asyncio (in dev)
```python
from adk_fluent.backends.asyncio_backend import AsyncioBackend
from adk_fluent.compile import compile

backend = AsyncioBackend()
ir = (Agent("a") >> Agent("b")).to_ir()
result = compile(ir, backend=backend)
```
:::
::::

## Backend Comparison

The same pipeline definition works across all backends — only the engine selection changes:

::::{tab-set}
:::{tab-item} ADK (default)
**Status: Stable** — production-ready

Compiles IR to native ADK objects (`LlmAgent`, `SequentialAgent`, etc.) and executes via ADK's `InMemoryRunner`.

```python
from adk_fluent import Agent

# Define a pipeline — identical across all backends
pipeline = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic.").writes("findings")
    >> Agent("writer", "gemini-2.5-flash")
    .instruct("Write a report about {findings}.")
)

# ADK: default, no .engine() needed
response = pipeline.ask("AI in healthcare")
```

**When to use:** Prototyping, development, production workloads that don't need crash recovery.
:::
:::{tab-item} Temporal (in dev)
**Status: In Development** — API may change

Compiles IR to Temporal workflows and activities. LLM calls become activities (cached on replay); deterministic nodes become workflow code.

```python
from temporalio.client import Client
from adk_fluent import Agent

client = await Client.connect("localhost:7233")

# Same pipeline definition — just add .engine()
pipeline = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic.").writes("findings")
    >> Agent("writer", "gemini-2.5-flash")
    .instruct("Write a report about {findings}.")
).engine("temporal", client=client, task_queue="research")

# Must use async — Temporal starts a workflow
response = await pipeline.ask_async("AI in healthcare")
```

**When to use:** Long-running pipelines, crash recovery, distributed execution.
:::
:::{tab-item} asyncio (in dev)
**Status: In Development** — reference implementation

Direct IR interpreter using plain `asyncio`. No durability, no external dependencies.

```python
from adk_fluent import Agent

# Same pipeline definition — just add .engine()
pipeline = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic.").writes("findings")
    >> Agent("writer", "gemini-2.5-flash")
    .instruct("Write a report about {findings}.")
).engine("asyncio")

response = await pipeline.ask_async("AI in healthcare")
```

**When to use:** Testing the backend abstraction, environments where ADK is not available.
:::
::::

### Capability Details

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

### Prefect (in dev)
**Status: In Development** — API may change

Compiles IR to Prefect flows and tasks. LLM calls become tasks with result caching; deterministic nodes become inline flow code. Supports HITL via `pause_flow_run()`.

```python
from adk_fluent import Agent

# Same pipeline definition — just add .engine()
pipeline = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic.").writes("findings")
    >> Agent("writer", "gemini-2.5-flash")
    .instruct("Write a report about {findings}.")
).engine("prefect", work_pool="gpu-pool")

response = await pipeline.ask_async("AI in healthcare")
```

**When to use:** Teams already using Prefect, need durability with familiar UI.

### DBOS (in dev)
**Status: In Development** — API may change

Compiles IR to DBOS durable workflows and steps backed by PostgreSQL. LLM calls become `@DBOS.step()` functions (durably recorded); deterministic nodes become inline workflow code. Supports HITL via `DBOS.recv()`.

```python
from adk_fluent import Agent

# Same pipeline definition — just add .engine()
pipeline = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic.").writes("findings")
    >> Agent("writer", "gemini-2.5-flash")
    .instruct("Write a report about {findings}.")
).engine("dbos", database_url="postgresql://localhost/agents")

response = await pipeline.ask_async("AI in healthcare")
```

**When to use:** Lightweight durability without heavy infrastructure (only PostgreSQL needed).

### SDK vs. Orchestrator

:::{important}
**ADK is a full SDK** — it owns model calls, tool execution, state management, and deployment. When you use the ADK backend, adk-fluent compiles IR to native ADK objects and ADK handles everything.

**Temporal, Prefect, and DBOS are orchestrators** — they own scheduling, durability, and crash recovery, but delegate LLM calls to a `ModelProvider` from the compute layer. This is why they need additional configuration (model_provider, database_url) that ADK doesn't.

The key benefit of orchestrators: if a 10-step pipeline crashes at step 7, the orchestrator replays steps 1-6 from cache (zero LLM cost) and re-executes only step 7+.
:::

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

| Capability | ADK | Temporal | asyncio | Prefect | DBOS |
|------------|-----|----------|---------|---------|------|
| `streaming` | Yes | No | Yes | No | No |
| `parallel` | Yes | Yes | Yes | Yes | Yes |
| `durable` | No | Yes | No | Yes* | Yes |
| `replay` | No | Yes | No | No | Yes |
| `checkpointing` | No | Yes | No | Yes* | Yes |
| `signals` | No | Yes | No | Yes | Yes |
| `dispatch_join` | Yes | Yes | Yes | Yes | Yes |
| `distributed` | No | Yes | No | Yes* | No |

\*Requires Prefect Server or Prefect Cloud.

## Backend Registry

Backends self-register. You can query the registry:

```python
from adk_fluent.backends import available_backends, get_backend

print(available_backends())  # ['adk', 'asyncio', 'dbos', 'prefect', 'temporal']

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
| Long-running pipelines that must survive crashes | **Temporal** |
| Distributed multi-worker execution | **Temporal** or **Prefect** |
| Human-in-the-loop approval workflows | **Temporal**, **Prefect**, or **DBOS** |
| Testing backend abstraction | **asyncio** |
| Team already uses Prefect | **Prefect** |
| Lightweight durability, minimal infrastructure | **DBOS** |
| Cost-sensitive crash recovery | **Temporal** or **DBOS** (replay = zero LLM cost) |

:::{tip}
Start with the ADK backend. If you later need durability or distribution, switch by adding `.engine("temporal", ...)` — your builder definitions don't change.
:::

:::{seealso}
- [IR & Backends](ir-and-backends.md) — IR node types and the compilation pipeline
- [Temporal Guide](temporal-guide.md) — Temporal-specific patterns, constraints, and examples
- [Execution](execution.md) — `.ask()`, `.stream()`, `.session()` and how they interact with backends
- [Middleware](middleware.md) — pipeline-wide middleware works across all backends
:::
