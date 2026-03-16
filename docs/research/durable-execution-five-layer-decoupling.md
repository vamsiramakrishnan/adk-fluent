# Plan: Five-Layer Decoupling — Definition / Compile / Runtime / Execution Backend / Compute

## Context

adk-fluent has a clean builder→IR→backend pipeline, but all five concerns are currently collapsed into a single ADK-dependent execution path. The user wants each concern independently swappable:

1. **Definition** — declaring agent logic (builders, operators, namespaces)
2. **Compile Time** — validating, optimizing, and lowering definitions into a runnable plan
3. **Runtime** — orchestrating execution (session lifecycle, event streaming, middleware)
4. **Execution Backend** — the durability/scheduling engine (ADK, Temporal, DBOS, plain asyncio)
5. **Compute** — the infrastructure where work physically runs (model providers, state stores, tool runtimes, deployment targets)

```
┌──────────────────────────────────────────────────────────────────────┐
│  1. DEFINITION LAYER                                                │
│     "What does this agent do?"                                      │
│                                                                     │
│  Agent("writer", "gemini-2.5-flash")                               │
│    .instruct(P.role("expert") + P.task("write essays"))            │
│    .tool(search_fn)                                                 │
│    .writes("draft")                                                 │
│    .guard(G.length(max=2000))                                       │
│                                                                     │
│  Pipeline("flow")                                                   │
│    .step(researcher).step(writer).step(reviewer)                    │
│                                                                     │
│  Output: Builder objects (immutable, CoW)                           │
├──────────────────────────────────────────────────────────────────────┤
│  2. COMPILE LAYER                                                   │
│     "Is this valid? What's the optimized execution plan?"           │
│                                                                     │
│  builder.to_ir()          → IR tree (frozen dataclasses)            │
│  contract_check(ir)       → validate state flow, detect errors      │
│  optimize(ir)             → fuse transforms, prune dead branches    │
│  lower(ir, target)        → emit backend-specific execution plan    │
│                                                                     │
│  Output: Validated, optimized IR + CompilationArtifact              │
├──────────────────────────────────────────────────────────────────────┤
│  3. RUNTIME LAYER                                                   │
│     "How do I manage sessions, events, and middleware?"             │
│                                                                     │
│  SessionManager           → create / resume / persist sessions      │
│  EventBus                 → route events to subscribers             │
│  MiddlewareStack          → before/after hooks, tracing, cost       │
│  StreamCoordinator        → backpressure, concurrency control       │
│                                                                     │
│  Output: Managed execution context                                  │
├──────────────────────────────────────────────────────────────────────┤
│  4. EXECUTION BACKEND LAYER                                         │
│     "What scheduling/durability guarantees do I get?"               │
│                                                                     │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│  │   ADK   │ │ Temporal  │ │  DBOS  │ │Prefect │ │Asyncio │       │
│  │         │ │          │ │        │ │        │ │  (bare)│       │
│  │ Native  │ │ Workflows│ │ Durable│ │ Flows  │ │Corouti-│       │
│  │ Runner  │ │+Activities│ │ Funcs │ │+Tasks  │ │  nes   │       │
│  └─────────┘ └──────────┘ └────────┘ └────────┘ └────────┘       │
│                                                                     │
│  Each backend interprets the lowered IR differently.                │
│  Durability, replay, checkpointing are backend concerns.            │
├──────────────────────────────────────────────────────────────────────┤
│  5. COMPUTE LAYER                                                   │
│     "Where does work physically happen?"                            │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐      │
│  │ModelProvider  │  │ StateStore   │  │   ToolRuntime        │      │
│  │              │  │              │  │                      │      │
│  │ Gemini       │  │ InMemory     │  │ Local (subprocess)   │      │
│  │ OpenAI       │  │ SQLite       │  │ Sandboxed (gVisor)   │      │
│  │ Anthropic    │  │ PostgreSQL   │  │ Remote (Cloud Run)   │      │
│  │ Ollama       │  │ Redis        │  │ MCP Server           │      │
│  │ Bedrock      │  │ Firestore    │  │                      │      │
│  │ vLLM         │  │ DynamoDB     │  │                      │      │
│  └──────────────┘  └──────────────┘  └──────────────────────┘      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │ DeployTarget: local | Cloud Run | K8s | Lambda | Vertex  │      │
│  └──────────────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Current State: Where Each Layer Lives Today

| Layer | Current Location | Decoupled? |
|-------|-----------------|-----------|
| **Definition** | `_base.py`, `agent.py`, `workflow.py`, namespaces (S,C,P,A,M,T,E,G) | **Yes** — builders are ADK-agnostic |
| **Compile** | `_ir.py`, `_ir_generated.py`, `testing/contracts.py`, `backends/adk.py:compile()` | **Partially** — IR is clean, but compilation goes straight to ADK objects |
| **Runtime** | `_helpers.py` (hardcoded `InMemoryRunner`), `middleware.py` (`_MiddlewarePlugin(BasePlugin)`) | **No** — welded to ADK Runner and Plugin system |
| **Execution Backend** | `backends/adk.py` (only backend, `run()`/`stream()` not implemented) | **No** — ADK is the only option |
| **Compute** | ADK handles model calls internally; `service.py` wraps ADK session/artifact services | **No** — model provider = whatever ADK supports, state = ADK session services |

### Specific coupling points (from codebase exploration):

1. **`_primitives.py`** — 11 agents subclass `google.adk.agents.base_agent.BaseAgent`, yield `google.adk.events.event.Event`
2. **`_helpers.py:run_one_shot_async()`** — imports `InMemoryRunner` directly, creates sessions via ADK service
3. **`backends/adk.py`** — only backend; `run()` and `stream()` raise `NotImplementedError`
4. **`middleware.py`** — `_MiddlewarePlugin` extends ADK's `BasePlugin`
5. **`service.py`** — all 15 service builders wrap ADK classes directly
6. **`_visibility.py`** — extends ADK's `BasePlugin`
7. **200+ `google.adk.*` imports** across the codebase — but **localized to ~7 files**

### What's already clean:
- **IR nodes** (`_ir.py`, `_ir_generated.py`) — ZERO ADK imports, pure dataclasses
- **Backend protocol** (`backends/_protocol.py`) — exists, references only IR types
- **All namespace modules** (S, C, P, A, M, T, E, G) — mostly ADK-agnostic
- **Builder base** (`_base.py`) — no ADK imports, pure builder machinery

---

## Phase 1: Formalize the Compile Layer

**Goal**: Make compilation a distinct, pluggable step with clear input/output contracts.

### 1a. Introduce CompilationResult

Currently `Backend.compile()` returns `Any`. Formalize this:

```python
# src/adk_fluent/compile/__init__.py

@dataclass
class CompilationResult:
    """Output of the compile step — input to the runtime step."""
    ir: FullNode                          # Original IR (for introspection)
    runnable: Any                         # Backend-specific executable
    backend_name: str                     # Which backend compiled this
    capabilities: EngineCapabilities      # What this compilation supports
    metadata: dict[str, Any]              # Backend-specific metadata
    warnings: list[str]                   # Non-fatal compilation warnings
```

**File**: `src/adk_fluent/compile/__init__.py` (new package)

### 1b. Add IR optimization passes

Before lowering to a backend, run optimization passes on the IR:

```python
# src/adk_fluent/compile/passes.py

def fuse_transforms(ir: FullNode) -> FullNode:
    """Merge adjacent TransformNodes into a single transform."""

def eliminate_dead_branches(ir: FullNode) -> FullNode:
    """Remove unreachable branches in RouteNode."""

def validate_contracts(ir: FullNode) -> list[ContractViolation]:
    """Run static contract checks (already exists in testing/contracts.py)."""

def annotate_checkpoints(ir: FullNode) -> FullNode:
    """Mark nodes that need checkpointing for durable backends."""
```

This reuses existing logic from `testing/contracts.py` but makes it a formal compile pass.

**File**: `src/adk_fluent/compile/passes.py` (new)

### 1c. Compiler entry point

```python
# src/adk_fluent/compile/__init__.py

def compile(
    ir: FullNode,
    *,
    backend: str | Backend = "adk",
    config: ExecutionConfig | None = None,
    optimize: bool = True,
) -> CompilationResult:
    """Compile IR to a runnable artifact for the specified backend."""
    if optimize:
        ir = run_passes(ir)
    backend_impl = resolve_backend(backend)
    runnable = backend_impl.compile(ir, config)
    return CompilationResult(
        ir=ir,
        runnable=runnable,
        backend_name=backend_impl.name,
        capabilities=backend_impl.capabilities,
    )
```

**File**: `src/adk_fluent/compile/__init__.py`

---

## Phase 2: Formalize the Runtime Layer

**Goal**: Extract session management, event routing, and middleware execution from the ADK-specific code into a backend-agnostic runtime.

### 2a. Runtime protocol

```python
# src/adk_fluent/runtime_protocol.py

class Runtime(Protocol):
    """Manages the execution lifecycle independent of backend."""

    async def execute(
        self,
        compiled: CompilationResult,
        prompt: str,
        *,
        session_id: str | None = None,
        user_id: str = "default",
    ) -> ExecutionResult: ...

    async def execute_stream(
        self,
        compiled: CompilationResult,
        prompt: str,
        **kwargs,
    ) -> AsyncIterator[AgentEvent]: ...

    async def create_session(self, **kwargs) -> str: ...
    async def resume(self, session_id: str) -> ExecutionResult: ...


@dataclass
class ExecutionResult:
    text: str
    events: list[AgentEvent]
    state: dict[str, Any]
    session_id: str
    metadata: ExecutionMetadata
```

### 2b. Default runtime implementation

```python
# src/adk_fluent/runtime_default.py

class DefaultRuntime:
    """Backend-agnostic runtime that delegates to the compiled backend."""

    def __init__(
        self,
        *,
        state_store: StateStore | None = None,
        middleware: list[Middleware] | None = None,
        event_handlers: list[EventHandler] | None = None,
    ): ...

    async def execute(self, compiled, prompt, **kwargs):
        # 1. Create or resume session via StateStore
        session = await self._state_store.create(...)

        # 2. Run middleware stack (before)
        await self._middleware.before_run(context)

        # 3. Delegate to backend
        events = await compiled.backend.run(compiled.runnable, prompt, session=session)

        # 4. Run middleware stack (after)
        await self._middleware.after_run(context, events)

        # 5. Persist state
        await self._state_store.save(session.id, context.state)

        return ExecutionResult(...)
```

This means middleware is NO LONGER an ADK plugin. It's a runtime concern that works identically across all backends.

**Files**:
- `src/adk_fluent/runtime_protocol.py` (new)
- `src/adk_fluent/runtime_default.py` (new)

### 2c. Decouple middleware from ADK BasePlugin

Currently `_MiddlewarePlugin(BasePlugin)` is the only way middleware runs. Split:

1. **Middleware protocol** (already engine-agnostic in `middleware.py`) — keep as-is
2. **ADK adapter** (`_MiddlewarePlugin`) — moves into `backends/adk/`
3. **Runtime adapter** — `DefaultRuntime` calls middleware directly, no plugin needed

**File**: `src/adk_fluent/middleware.py` — split, keep protocol at top level

---

## Phase 3: Formalize the Execution Backend Layer

**Goal**: Extend the Backend protocol to fully cover what each engine provides.

### 3a. Extended Backend protocol

```python
# src/adk_fluent/backends/_protocol.py

@runtime_checkable
class Backend(Protocol):
    """An execution engine that runs compiled IR."""

    name: str

    # --- Compilation ---
    def compile(self, node: FullNode, config: ExecutionConfig | None = None) -> Any:
        """IR → engine-specific runnable."""

    # --- Execution ---
    async def run(self, runnable: Any, prompt: str, *, session: SessionState) -> list[AgentEvent]:
        """Execute and collect all events."""

    async def stream(self, runnable: Any, prompt: str, *, session: SessionState) -> AsyncIterator[AgentEvent]:
        """Stream events as they occur."""

    # --- Capabilities ---
    @property
    def capabilities(self) -> EngineCapabilities:
        """Declare what this engine supports."""


@dataclass(frozen=True)
class EngineCapabilities:
    streaming: bool = True
    parallel: bool = True
    durable: bool = False           # survives process crash
    replay: bool = False            # can replay from checkpoint
    checkpointing: bool = False     # saves progress at each step
    signals: bool = False           # external input during execution (HITL)
    dispatch_join: bool = True      # fire-and-forget + sync
    distributed: bool = False       # runs across multiple processes/machines
```

### 3b. Backend registry with auto-discovery

```python
# src/adk_fluent/backends/__init__.py

_REGISTRY: dict[str, Callable[..., Backend]] = {}

def register(name: str, factory: Callable[..., Backend]) -> None: ...
def get(name: str, **kwargs) -> Backend: ...
def available() -> list[str]: ...

# Auto-register ADK
register("adk", lambda **kw: ADKBackend(**kw))

# Temporal registers on import of extras
# register("temporal", lambda **kw: TemporalBackend(**kw))
```

### 3c. Implement ADK backend's run()/stream()

Move logic from `_helpers.py:run_one_shot_async()` into `ADKBackend`:

```python
# src/adk_fluent/backends/adk.py

class ADKBackend:
    async def run(self, runnable, prompt, *, session):
        from google.adk.runners import InMemoryRunner
        runner = InMemoryRunner(agent=runnable, app_name=self._app_name)
        adk_session = await runner.session_service.create_session(...)
        # Copy state from our SessionState into ADK session
        events = []
        async for event in runner.run_async(...):
            events.append(self._to_agent_event(event))
        return events
```

**Files**:
- `src/adk_fluent/backends/_protocol.py` — extend protocol
- `src/adk_fluent/backends/__init__.py` — add registry
- `src/adk_fluent/backends/adk.py` — implement run()/stream()

---

## Phase 4: Formalize the Compute Layer

**Goal**: Make model providers, state stores, and tool runtimes independently pluggable.

### 4a. Compute protocols

```python
# src/adk_fluent/compute/_protocol.py

class ModelProvider(Protocol):
    """Abstraction over LLM providers."""
    model_id: str
    async def generate(self, messages: list[Message], tools: list[ToolDef], config: GenerateConfig) -> GenerateResult: ...
    async def generate_stream(self, messages, tools, config) -> AsyncIterator[Chunk]: ...


class StateStore(Protocol):
    """Abstraction over session/state persistence."""
    async def create(self, namespace: str, **initial_state) -> str: ...   # returns session_id
    async def load(self, session_id: str) -> dict[str, Any]: ...
    async def save(self, session_id: str, state: dict[str, Any]) -> None: ...
    async def list_sessions(self, namespace: str) -> list[str]: ...


class ToolRuntime(Protocol):
    """Abstraction over tool execution environments."""
    async def execute(self, tool_name: str, fn: Callable, args: dict[str, Any]) -> Any: ...


class ArtifactStore(Protocol):
    """Abstraction over artifact persistence."""
    async def save(self, key: str, data: bytes, metadata: dict) -> int: ...   # returns version
    async def load(self, key: str, version: int | None = None) -> bytes: ...
```

### 4b. Default implementations

```python
# src/adk_fluent/compute/memory.py
class InMemoryStateStore:
    """Dict-based state store for testing."""

# src/adk_fluent/compute/sqlite.py
class SqliteStateStore:
    """SQLite-backed state store."""

# src/adk_fluent/compute/local.py
class LocalToolRuntime:
    """Execute tools in the current process."""
```

### 4c. Compute configuration

```python
# src/adk_fluent/compute/__init__.py

@dataclass
class ComputeConfig:
    """Binds compute resources to an execution."""
    model_provider: ModelProvider | str | None = None   # str = model name, resolved by backend
    state_store: StateStore | None = None
    tool_runtime: ToolRuntime | None = None
    artifact_store: ArtifactStore | None = None
```

When `model_provider` is a string (e.g., `"gemini-2.5-flash"`), the backend resolves it using its native model handling. When it's a `ModelProvider` instance, the backend uses it directly. This lets the ADK backend keep using ADK's model handling by default, while other backends can use any provider.

**New directory**: `src/adk_fluent/compute/`

---

## Phase 5: Temporal Backend (First Alternative Engine)

**Goal**: Prove the architecture works by implementing a non-ADK backend.

### 5a. IR → Temporal mapping

| IR Node | Temporal Concept | Deterministic? |
|---------|-----------------|---------------|
| `AgentNode` | **Activity** (LLM call = I/O) | No |
| `SequenceNode` | **Workflow** body (sequential awaits) | Yes |
| `ParallelNode` | **Workflow** with `asyncio.gather()` over activities | Yes |
| `LoopNode` | **Workflow** `while` loop (each iteration checkpointed) | Yes |
| `TransformNode` | Inline workflow code (pure function) | Yes |
| `TapNode` | Inline workflow code (observation, no I/O) | Yes |
| `RouteNode` | Inline workflow code (deterministic switch) | Yes |
| `FallbackNode` | Workflow with try/except chain over activities | Yes |
| `DispatchNode` | `workflow.start_child_workflow()` | Yes |
| `JoinNode` | `await child_handle.result()` | Yes |
| `GateNode` | `workflow.wait_condition()` + **Signal** | Yes |
| `TimeoutNode` | `asyncio.wait_for(activity, timeout=)` | Yes |
| `RaceNode` | First-completed over parallel activities | Yes |
| `MapOverNode` | Workflow loop, each item = activity | Yes |

**Key principle**: Deterministic nodes become workflow code (replayed from history). Non-deterministic nodes (LLM calls, tool calls) become activities (cached on replay).

### 5b. TemporalBackend structure

```python
# src/adk_fluent/backends/temporal.py

class TemporalBackend:
    def __init__(self, client: Client, task_queue: str = "adk-fluent"):
        self._client = client
        self._task_queue = task_queue

    def compile(self, node: FullNode, config=None) -> TemporalRunnable:
        """Walk IR tree, generate workflow + activity definitions."""
        # Each AgentNode → @activity.defn
        # Top-level structure → @workflow.defn
        return TemporalRunnable(workflow_cls=..., activities=..., worker_config=...)

    async def run(self, runnable, prompt, *, session):
        handle = await self._client.start_workflow(...)
        return await handle.result()

    @property
    def capabilities(self):
        return EngineCapabilities(
            durable=True, replay=True, checkpointing=True,
            signals=True, distributed=True, streaming=False,
        )
```

### 5c. Activity wrapping for LLM calls

```python
@activity.defn
async def llm_activity(input: LLMActivityInput) -> LLMActivityOutput:
    """Non-deterministic: calls LLM via ModelProvider."""
    provider = resolve_provider(input.model)
    messages = build_messages(input.instruction, input.context, input.history)
    result = await provider.generate(messages, input.tools, input.config)

    # Tool execution loop (each tool call is also an activity)
    while result.tool_calls:
        tool_results = []
        for tc in result.tool_calls:
            tr = await workflow.execute_activity(
                tool_activity, ToolActivityInput(name=tc.name, args=tc.args),
                start_to_close_timeout=timedelta(seconds=60),
            )
            tool_results.append(tr)
        result = await provider.generate(messages + tool_results, input.tools, input.config)

    return LLMActivityOutput(text=result.text, state_delta=result.state)
```

### 5d. Crash recovery example

```
Pipeline: researcher → writer → reviewer

Step 1: researcher runs (Activity) → checkpoint saved
Step 2: writer runs (Activity) → checkpoint saved
Step 3: CRASH during reviewer

On restart:
- Temporal replays workflow
- researcher activity: returns cached result (zero LLM cost)
- writer activity: returns cached result (zero LLM cost)
- reviewer activity: re-executes (only this LLM call is made)
```

**New file**: `src/adk_fluent/backends/temporal.py`
**New extras**: `pip install adk-fluent[temporal]` → adds `temporalio` dependency

---

## Phase 6: Asyncio Backend (Zero-Dependency Reference)

**Goal**: Pure Python backend with no framework. Proves the abstraction works without any external engine.

```python
# src/adk_fluent/backends/asyncio_backend.py

class AsyncioBackend:
    """Direct IR interpreter using asyncio. No durability, no framework."""

    def __init__(self, *, model_provider: ModelProvider | None = None):
        self._provider = model_provider

    def compile(self, node, config=None):
        return AsyncioRunnable(node, config, self._provider)

    async def run(self, runnable, prompt, *, session):
        return await self._interpret(runnable.root, prompt, session.state)

    async def _interpret(self, node, prompt, state):
        match node:
            case AgentNode():     return await self._run_agent(node, prompt, state)
            case SequenceNode():  return await self._run_sequence(node, prompt, state)
            case ParallelNode():  return await self._run_parallel(node, prompt, state)
            case LoopNode():      return await self._run_loop(node, prompt, state)
            case TransformNode(): return self._run_transform(node, state)
            case FallbackNode():  return await self._run_fallback(node, prompt, state)
            # ... etc

    @property
    def capabilities(self):
        return EngineCapabilities(streaming=True, parallel=True)  # no durability
```

**New file**: `src/adk_fluent/backends/asyncio_backend.py`

---

## Phase 7: Wire it Together — User-Facing API

**Goal**: Users select engine and compute with minimal ceremony.

### 7a. Builder method: `.engine()`

```python
agent = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic.")
    .engine("temporal", client=temporal_client, task_queue="research")
)
result = await agent.ask_async("quantum computing")
```

### 7b. Global default

```python
import adk_fluent
adk_fluent.configure(
    engine="temporal",
    engine_config={"client": temporal_client},
    compute=ComputeConfig(
        state_store=SqliteStateStore("sessions.db"),
    ),
)

# All agents now use Temporal by default
result = await Agent("x").instruct("...").ask_async("hello")
```

### 7c. Execution helper refactor

```python
# src/adk_fluent/_helpers.py

async def run_one_shot_async(builder, prompt, *, engine=None, compute=None, **kwargs):
    ir = builder.to_ir()
    config = builder._execution_config()

    # Resolve backend
    backend = resolve_backend(engine or config.engine or get_default_engine())

    # Compile
    compiled = compile(ir, backend=backend, config=config)

    # Create runtime
    runtime = DefaultRuntime(
        state_store=compute.state_store if compute else InMemoryStateStore(),
        middleware=config.middlewares,
    )

    # Execute
    return await runtime.execute(compiled, prompt, **kwargs)
```

**Files**:
- `src/adk_fluent/agent.py` — add `.engine()`, `.compute()` builder methods
- `src/adk_fluent/_helpers.py` — refactor to use runtime + backend
- `src/adk_fluent/__init__.py` — add `configure()` function

---

## Phase 8: Move ADK Primitives into Backend Scope

**Goal**: `_primitives.py` agents are ADK implementation details, not universal abstractions.

### 8a. Restructure backends/adk/

```
src/adk_fluent/backends/
  __init__.py              # Registry, Backend protocol re-export
  _protocol.py             # Backend protocol, EngineCapabilities
  adk/
    __init__.py            # ADKBackend class
    _compiler.py           # IR → ADK object compilation (current adk.py)
    _primitives.py         # FnAgent, TapAgent, DispatchAgent, etc. (moved)
    _middleware_plugin.py   # _MiddlewarePlugin(BasePlugin) (moved from middleware.py)
    _visibility_plugin.py   # VisibilityPlugin (moved from _visibility.py)
  temporal.py              # TemporalBackend
  asyncio_backend.py       # AsyncioBackend
```

### 8b. Backward compatibility shims

```python
# src/adk_fluent/_primitives.py (kept, imports from new location)
from adk_fluent.backends.adk._primitives import *  # noqa: F401,F403
```

---

## Implementation Order

| Step | What | Risk | Breaking? |
|------|------|------|----------|
| **1** | Create `src/adk_fluent/compile/` package, CompilationResult, compile passes | Low | No |
| **2** | Extend Backend protocol with capabilities, session support | Low | No (additive) |
| **3** | Implement `ADKBackend.run()` and `ADKBackend.stream()` | Medium | No (new code paths) |
| **4** | Create `src/adk_fluent/compute/` package, StateStore/ModelProvider/ToolRuntime protocols | Low | No (additive) |
| **5** | Create `DefaultRuntime`, decouple middleware from `BasePlugin` | Medium | No (new paths, old paths preserved) |
| **6** | Refactor `_helpers.py` to use Runtime + Backend (default = ADK) | Medium | No (same default behavior) |
| **7** | Implement `AsyncioBackend` (reference implementation, proves abstraction) | Low | No (opt-in) |
| **8** | Implement `TemporalBackend` | Medium | No (opt-in extra) |
| **9** | Add `.engine()`, `.compute()` builder methods, `configure()` global | Low | No (additive) |
| **10** | Move primitives into `backends/adk/` with compat shims | High | No (re-exports) |

---

## Critical Files

### New files:
- `src/adk_fluent/compile/__init__.py` — CompilationResult, compile()
- `src/adk_fluent/compile/passes.py` — IR optimization passes
- `src/adk_fluent/compute/__init__.py` — ComputeConfig
- `src/adk_fluent/compute/_protocol.py` — ModelProvider, StateStore, ToolRuntime, ArtifactStore
- `src/adk_fluent/compute/memory.py` — InMemoryStateStore
- `src/adk_fluent/runtime_protocol.py` — Runtime protocol
- `src/adk_fluent/runtime_default.py` — DefaultRuntime
- `src/adk_fluent/backends/temporal.py` — TemporalBackend
- `src/adk_fluent/backends/asyncio_backend.py` — AsyncioBackend

### Files to modify:
- `src/adk_fluent/backends/_protocol.py` — extend Backend, add EngineCapabilities
- `src/adk_fluent/backends/__init__.py` — add registry
- `src/adk_fluent/backends/adk.py` — implement run()/stream(), restructure
- `src/adk_fluent/_helpers.py` — delegate to Runtime + Backend
- `src/adk_fluent/_ir.py` — extend ExecutionConfig with engine/compute fields
- `src/adk_fluent/agent.py` — add .engine(), .compute() methods
- `src/adk_fluent/middleware.py` — split protocol from ADK adapter

### Files to restructure (Phase 8):
- `src/adk_fluent/_primitives.py` → `src/adk_fluent/backends/adk/_primitives.py`
- `src/adk_fluent/_visibility.py` → `src/adk_fluent/backends/adk/_visibility_plugin.py`

---

## Verification Plan

1. **Zero regressions**: `uv run pytest tests/ -v --tb=short` passes at every phase
2. **ADK backend parity**: Existing `.ask()`, `.build()`, operator tests produce identical results
3. **Protocol compliance**: `isinstance(ADKBackend(), Backend)` and `isinstance(TemporalBackend(...), Backend)` both true
4. **Asyncio backend smoke test**: Simple agent pipeline runs without ADK installed
5. **Temporal integration test**: 3-step pipeline survives simulated crash, replays steps 1-2 from cache
6. **Compute swap test**: Same pipeline runs with InMemoryStateStore and SqliteStateStore
7. **Engine swap test**: Same IR compiles successfully to ADK, asyncio, and Temporal backends

---

## Design Principles

1. **IR is the universal contract** — every backend must be implementable from IR alone
2. **ADK is the default, not a dependency** — existing code works unchanged
3. **Each layer is independently swappable** — change engine without changing compute, or vice versa
4. **No magic registration** — engine selection is always explicit (builder method or global config)
5. **Extras for heavy deps** — `pip install adk-fluent[temporal]`, `pip install adk-fluent[asyncio-only]`
6. **Backward compatible always** — every phase ships without breaking existing users
7. **Primitives are engine internals** — `FnAgent`, `DispatchAgent` are how ADK implements the IR, not user-facing contracts
