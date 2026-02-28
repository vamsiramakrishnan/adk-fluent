# Callback-Driven Dispatch & Continuous Stream Execution

## Philosophy: Leverage Python, Build Only the Novel

**Principle**: Use Python's stdlib async primitives everywhere. Only build what's genuinely novel — the ADK integration layer and fluent API.

### Audit: What Python already provides vs. what we must build

| Need                                | Python stdlib solution                                                      | Our role                                             |
| ----------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------- |
| Task tracking across pipeline steps | `contextvars.ContextVar` — per-execution scoping, no global state           | Use directly — replaces `_TASK_REGISTRY` module dict |
| Fire background tasks               | `asyncio.create_task()` — already used by `RaceAgent`                       | Use directly                                         |
| Wait for tasks with timeout         | `asyncio.wait(tasks, timeout=N)` — already used by `RaceAgent`              | Use directly                                         |
| Structured concurrency cleanup      | `asyncio.TaskGroup` (Python 3.11+, guaranteed by `requires-python >= 3.11`) | Use for JoinAgent's task group management            |
| Stream source protocol              | `typing.AsyncIterator[str]` — IS the protocol                               | Source = thin factory returning `AsyncIterator[str]` |
| Push-based ingestion                | `asyncio.Queue` — already used in `TimeoutAgent`                            | Thin wrapper, expose `.push()`                       |
| Concurrency control                 | `asyncio.Semaphore` — already used in `run_map_async`                       | Use directly                                         |
| Graceful shutdown                   | `signal` + `asyncio.Event`                                                  | Use directly                                         |
| Dead-letter queue                   | A callback `on_error(item, exc)`                                            | Not a class — just a param                           |
| Metrics                             | `dataclass` with counters                                                   | Not a framework — just counters                      |

**What's genuinely novel (no Python library does this):**

1. `DispatchAgent._run_async_impl` — fire-and-continue inside ADK's BaseAgent async generator model
1. `JoinAgent._run_async_impl` — barrier that collects dispatched events back into ADK's event stream
1. Fluent builders + IR nodes (that's what adk-fluent IS)
1. `AsyncIterator[str]` → ADK `runner.run_async()` bridge (nobody feeds streams into ADK)
1. Session strategy routing (per_item / shared / keyed)

## Part 0: GIL, Deep Dispatch Chains, and High-Performance Execution

### Why the GIL doesn't matter here

LLM agent execution is **99%+ I/O-bound**: prepare prompt → call LLM API (network wait) → parse response → maybe call tools (network wait). Python's GIL is released during every `await`, which means:

- 100 concurrent `asyncio.create_task()` agents all waiting on Gemini API calls → 100 truly concurrent I/O operations
- The GIL only serializes the tiny Python code between awaits (prompt formatting, response parsing)
- This is exactly what `asyncio` was designed for — cooperative multitasking on I/O-bound work

**`asyncio` is the correct high-performance model for LLM agents.** Using threads or processes would add overhead (context switching, IPC serialization) with zero benefit since the bottleneck is network I/O, not CPU.

### Deep dispatch chains: dispatch → dispatch → dispatch → dispatch

The risk: agent A dispatches agents B and C, agent B dispatches D and E, agent D dispatches F and G — exponential task explosion.

**Solution: Global task budget via `asyncio.Semaphore`**

```python
# Single semaphore shared across ALL dispatch levels
_global_task_budget: ContextVar[asyncio.Semaphore] = ContextVar("_global_task_budget")

# Set at the top level (StreamRunner or initial dispatch)
_global_task_budget.set(asyncio.Semaphore(50))  # max 50 concurrent agent tasks

# Every DispatchAgent acquires from the same semaphore before creating a task
# If budget exhausted → dispatch blocks (backpressure propagates up the tree)
```

This means:

- A 4-level deep dispatch chain shares the same 50-task budget
- When the budget is full, deeper dispatches naturally block until shallower ones complete
- No explosion — backpressure propagates through the entire tree
- The budget is per-`ContextVar` scope (per runner invocation), not global

### `ContextVar` propagation through dispatch chains

`contextvars` propagate automatically through `asyncio.create_task()`:

```python
# Parent sets ContextVar
_dispatch_tasks.set({"email": task_e})

# Child task created with create_task() — INHERITS parent context
task = asyncio.create_task(child_agent.run_async(ctx))
# Inside child: _dispatch_tasks.get() sees parent's dict
# But child can set its own (copy-on-write semantics)
```

This means nested dispatch/join naturally works:

- Level 0: `dispatch(A, B)` → sets `_dispatch_tasks` with A, B
- Level 1 (inside A): `dispatch(C, D)` → A's child context gets its own copy with C, D
- Level 1 (inside A): `join()` → waits for C, D (A's local dispatches)
- Level 0: `join()` → waits for A, B (top-level dispatches)

Each dispatch level has its own `ContextVar` scope. No interference between levels.

### Performance characteristics

| Metric                                    | Value                                                       | Why                                                |
| ----------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------- |
| Max concurrent LLM calls                  | Limited only by API quota + `_global_task_budget` semaphore | All I/O, no GIL contention                         |
| Dispatch overhead                         | ~1μs per `create_task()`                                    | stdlib, zero allocation beyond the coroutine frame |
| Join overhead                             | ~1μs per `asyncio.wait()` call                              | stdlib, epoll-based                                |
| Memory per task                           | ~2KB (coroutine frame + task object)                        | 50 tasks ≈ 100KB                                   |
| Deep dispatch (4 levels, 3 children each) | 81 leaf tasks, bounded by semaphore                         | Backpressure prevents explosion                    |
| ContextVar lookup                         | O(1) per access                                             | dict lookup on the execution context               |

### What about CPU-bound agents?

If an agent does heavy computation (data processing, embedding generation), the GIL does block other tasks during that computation. For this case, `asyncio.to_thread()` (stdlib) offloads to a thread pool where the GIL is released during C extensions:

```python
# For CPU-bound tools, users can wrap with to_thread
async def heavy_tool(data: str) -> str:
    return await asyncio.to_thread(cpu_bound_function, data)
```

This is a user-level pattern, not something we need to build into the framework.

## Part 1: `dispatch()` / `join()` — Background Agent Dispatch

### Design: stdlib-first

The entire dispatch/join mechanism is built from **three stdlib primitives**:

```python
import asyncio
from contextvars import ContextVar

# 1. ContextVar replaces module-level _TASK_REGISTRY
#    Automatically scoped per-execution, no cleanup needed, no global state
_dispatch_tasks: ContextVar[dict[str, asyncio.Task]] = ContextVar("_dispatch_tasks", default=None)

# 2. asyncio.create_task() — same as RaceAgent already uses
# 3. asyncio.wait() — same as RaceAgent already uses
```

**Why `ContextVar` instead of module-level dict:**

- No manual cleanup — garbage collected when execution context ends
- No global state pollution — concurrent executions don't interfere
- Thread-safe by design
- Pythonic — this is exactly what `contextvars` was designed for

### Proposed API

```python
from adk_fluent import Agent, dispatch, join

# 1. Basic: fire-and-continue
workflow = (
    writer
    >> dispatch(email_sender, audit_logger)   # non-blocking
    >> formatter                               # runs immediately
    >> join()                                  # barrier
    >> publisher
)

# 2. Named tasks with selective join
workflow = (
    writer
    >> dispatch(
        research_agent, email_sender,
        names=["research", "email"],
        on_complete=lambda name, result: print(f"{name} done"),
    )
    >> quick_formatter                      # runs while dispatch tasks work
    >> join("research", timeout=30)         # wait only for research
    >> publisher
    >> join("email")                        # collect email later
)

# 3. Method form — works on ANY builder (Agent, Pipeline, FanOut, Loop)
bg_pipeline = (researcher >> analyzer).dispatch(name="analysis")
workflow = writer >> bg_pipeline >> formatter >> join("analysis") >> publisher

# 4. Progress streaming (partial results while running)
workflow = (
    writer
    >> dispatch(
        long_agent,
        progress_key="live_progress",       # partial text streams here
    )
    >> monitor                              # reads state["live_progress"]
    >> join()
)
```

### Implementation

#### `DispatchAgent(BaseAgent)` — the fire-and-continue primitive

```python
class DispatchAgent(BaseAgent):
    """Launches sub-agents as background tasks, returns immediately."""

    _task_names: tuple[str, ...]
    _on_complete: Callable | None
    _on_error: Callable | None
    _progress_key: str | None

    async def _run_async_impl(self, ctx):
        # Get or create the per-invocation task dict via ContextVar
        tasks = _dispatch_tasks.get()
        if tasks is None:
            tasks = {}
            _dispatch_tasks.set(tasks)

        for i, child in enumerate(self.sub_agents):
            name = self._task_names[i] if self._task_names else child.name

            async def _run_child(agent, task_name):
                events = []
                last_text = ""
                try:
                    async for event in agent.run_async(ctx):
                        events.append(event)
                        # Stream partial results if progress_key set
                        if self._progress_key and event.content:
                            for part in (event.content.parts or []):
                                if part.text:
                                    last_text = part.text
                                    ctx.session.state[self._progress_key] = last_text

                    # Update state metadata
                    ctx.session.state.setdefault("_dispatch_results", {})[task_name] = last_text
                    if self._on_complete:
                        self._on_complete(task_name, last_text)
                    return events

                except Exception as exc:
                    if self._on_error:
                        self._on_error(task_name, exc)
                    raise

            task = asyncio.create_task(_run_child(child, name))
            tasks[name] = task

            # Serializable metadata in state (for downstream agents to check)
            ctx.session.state.setdefault("_dispatch_handles", {})[name] = {
                "status": "running", "agent": child.name,
            }

        # Return immediately — pipeline continues
        return
        yield  # async generator protocol
```

#### `JoinAgent(BaseAgent)` — the barrier

```python
class JoinAgent(BaseAgent):
    """Blocks until dispatched tasks complete, yields their events."""

    _target_names: tuple[str, ...] | None
    _timeout: float | None

    async def _run_async_impl(self, ctx):
        tasks = _dispatch_tasks.get() or {}
        if not tasks:
            return; yield

        # Select which tasks to wait for
        if self._target_names:
            to_wait = {k: v for k, v in tasks.items() if k in self._target_names}
        else:
            to_wait = dict(tasks)

        # stdlib: asyncio.wait with timeout
        done, pending = await asyncio.wait(
            to_wait.values(),
            timeout=self._timeout,
        )

        # Cancel timed-out tasks
        for task in pending:
            task.cancel()

        # Yield events from completed tasks into main stream
        for task in done:
            if not task.cancelled() and not task.exception():
                for event in task.result():
                    yield event

        # Update state metadata
        for name, task in to_wait.items():
            if task in done and not task.exception():
                ctx.session.state.get("_dispatch_handles", {})[name] = {"status": "completed"}
            elif task in done and task.exception():
                ctx.session.state.get("_dispatch_handles", {})[name] = {"status": "error"}
            else:
                ctx.session.state.get("_dispatch_handles", {})[name] = {"status": "timed_out"}

        # Remove joined tasks from registry
        for name in to_wait:
            tasks.pop(name, None)
```

#### Builders follow existing pattern

`_DispatchBuilder` and `_JoinBuilder` follow `_RaceBuilder` / `_GateBuilder` exactly. ~50 lines each.

#### IR nodes

```python
@dataclass(frozen=True)
class DispatchNode:
    name: str
    children: tuple = ()
    task_names: tuple[str, ...] = ()
    progress_key: str | None = None

@dataclass(frozen=True)
class JoinNode:
    name: str
    target_names: tuple[str, ...] | None = None
    timeout: float | None = None
```

## Part 2: `StreamRunner` — stdlib-powered continuous execution

### Design: Source = `AsyncIterator[str]` (the protocol IS the abstraction)

Python already has the perfect protocol for streams: `AsyncIterator`. We don't need a class hierarchy.

```python
# Source is a namespace of factory functions that return AsyncIterator[str]
# The "framework" is just: async for item in source: process(item)
```

### `Source` — thin factory namespace (`src/adk_fluent/source.py`)

```python
"""Stream source factories. Each returns an AsyncIterator[str]."""

import asyncio
from collections.abc import AsyncIterator, Callable, Iterable
from typing import Any

_SENTINEL = object()


class Source:
    """Factory namespace for stream sources. All return AsyncIterator[str]."""

    @staticmethod
    async def from_async(agen: AsyncIterator[str]) -> AsyncIterator[str]:
        """Pass through an existing async iterator."""
        async for item in agen:
            yield item

    @staticmethod
    async def from_iter(iterable: Iterable[str]) -> AsyncIterator[str]:
        """Wrap a sync iterable (file, list) as async."""
        for item in iterable:
            yield item

    @staticmethod
    async def poll(fn: Callable[[], Any], interval: float = 1.0) -> AsyncIterator[str]:
        """Call fn() every interval seconds. Yield non-None results."""
        while True:
            result = fn()
            if asyncio.iscoroutine(result):
                result = await result
            if result is not None:
                yield str(result)
            await asyncio.sleep(interval)

    @staticmethod
    def callback() -> "Inbox":
        """Push-based source. Returns an Inbox with .push() and async iteration."""
        return Inbox()


class Inbox:
    """Push-based async source. Wraps asyncio.Queue."""

    def __init__(self, maxsize: int = 0):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)

    def push(self, item: str) -> None:
        """Push an item (non-blocking). Called from webhooks, etc."""
        self._queue.put_nowait(item)

    async def push_async(self, item: str) -> None:
        """Push an item (async, respects maxsize backpressure)."""
        await self._queue.put(item)

    def close(self) -> None:
        """Signal no more items."""
        self._queue.put_nowait(_SENTINEL)

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        item = await self._queue.get()
        if item is _SENTINEL:
            raise StopAsyncIteration
        return item
```

**Total code: ~50 lines.** No base class, no inheritance, no framework. Just factories returning `AsyncIterator[str]` and one thin wrapper around `asyncio.Queue`.

### `StreamRunner` — the ADK bridge (`src/adk_fluent/stream.py`)

The **only novel part**: bridging `AsyncIterator[str]` → ADK's `runner.run_async()`.

```python
"""Continuous stream execution engine. Bridges AsyncIterator → ADK Runner."""

import asyncio
import signal
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types


@dataclass
class StreamStats:
    """Live counters. Just a dataclass, not a framework."""
    processed: int = 0
    errors: int = 0
    in_flight: int = 0
    start_time: float = field(default_factory=time.monotonic)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.start_time

    @property
    def throughput(self) -> float:
        return self.processed / max(self.elapsed, 0.001)


class StreamRunner:
    """Production continuous execution. Stdlib-powered."""

    def __init__(self, builder):
        self._builder = builder
        self._source: AsyncIterator[str] | None = None
        self._concurrency: int = 1
        self._session_strategy: str = "per_item"
        self._session_key_fn: Callable | None = None
        self._on_result: Callable | None = None
        self._on_error: Callable | None = None
        self._shutdown_timeout: float = 30.0
        self._stop_event = asyncio.Event()
        self.stats = StreamStats()
        # Session caches
        self._shared_session = None
        self._keyed_sessions: dict[str, Any] = {}

    # --- Fluent config (returns self) ---
    def source(self, src) -> "StreamRunner":
        self._source = src; return self

    def concurrency(self, n: int) -> "StreamRunner":
        self._concurrency = n; return self

    def session_strategy(self, strategy: str) -> "StreamRunner":
        self._session_strategy = strategy; return self

    def session_key(self, fn: Callable) -> "StreamRunner":
        self._session_key_fn = fn; self._session_strategy = "keyed"; return self

    def on_result(self, fn: Callable) -> "StreamRunner":
        self._on_result = fn; return self

    def on_error(self, fn: Callable) -> "StreamRunner":
        self._on_error = fn; return self

    def graceful_shutdown(self, timeout: float = 30) -> "StreamRunner":
        self._shutdown_timeout = timeout; return self

    # --- Lifecycle ---
    async def start(self) -> None:
        """Main loop. Reads source, processes with bounded concurrency."""
        agent = self._builder.build()
        app_name = f"_stream_{agent.name}"
        runner = InMemoryRunner(agent=agent, app_name=app_name)

        # stdlib: Semaphore for concurrency, Event for shutdown
        sem = asyncio.Semaphore(self._concurrency)
        tasks: set[asyncio.Task] = set()

        # stdlib: signal handling for graceful shutdown
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(sig, self._stop_event.set)

        async def _process(item: str):
            async with sem:
                self.stats.in_flight += 1
                try:
                    session = await self._resolve_session(runner, app_name, item)
                    content = types.Content(role="user", parts=[types.Part(text=item)])
                    last_text = ""
                    async for event in runner.run_async(
                        user_id="_stream", session_id=session.id, new_message=content,
                    ):
                        if event.content and event.content.parts:
                            for part in event.content.parts:
                                if part.text:
                                    last_text = part.text
                    self.stats.processed += 1
                    if self._on_result:
                        self._on_result(item, last_text)
                except Exception as exc:
                    self.stats.errors += 1
                    if self._on_error:
                        self._on_error(item, exc)
                finally:
                    self.stats.in_flight -= 1

        # Main loop: stdlib async for + create_task
        async for item in self._source:
            if self._stop_event.is_set():
                break
            task = asyncio.create_task(_process(item))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

        # Drain in-flight
        if tasks:
            await asyncio.wait(tasks, timeout=self._shutdown_timeout)

    async def stop(self) -> None:
        self._stop_event.set()

    async def _resolve_session(self, runner, app_name, item):
        if self._session_strategy == "per_item":
            return await runner.session_service.create_session(
                app_name=app_name, user_id="_stream"
            )
        elif self._session_strategy == "shared":
            if self._shared_session is None:
                self._shared_session = await runner.session_service.create_session(
                    app_name=app_name, user_id="_stream"
                )
            return self._shared_session
        elif self._session_strategy == "keyed" and self._session_key_fn:
            key = self._session_key_fn(item)
            if key not in self._keyed_sessions:
                self._keyed_sessions[key] = await runner.session_service.create_session(
                    app_name=app_name, user_id=f"_stream_{key}"
                )
            return self._keyed_sessions[key]
```

**Stdlib usage count**: `asyncio.Semaphore`, `asyncio.Event`, `asyncio.create_task`, `asyncio.wait`, `signal`, `time.monotonic`, `dataclass`. Zero third-party dependencies.

## Files to modify/create

| File                                    | Changes                                                                                                                                              | Lines (est.) |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| `src/adk_fluent/_base.py`               | `DispatchAgent`, `JoinAgent`, `_DispatchBuilder`, `_JoinBuilder`, `dispatch()`, `join()`, `.dispatch()` on BuilderBase, `_dispatch_tasks` ContextVar | ~200         |
| `src/adk_fluent/_ir.py`                 | `DispatchNode`, `JoinNode`, update `Node` union                                                                                                      | ~20          |
| `src/adk_fluent/backends/adk.py`        | `_compile_dispatch`, `_compile_join`                                                                                                                 | ~30          |
| `src/adk_fluent/source.py`              | **NEW** — `Source` factory, `Inbox`                                                                                                                  | ~55          |
| `src/adk_fluent/stream.py`              | **NEW** — `StreamRunner`, `StreamStats`                                                                                                              | ~120         |
| `src/adk_fluent/agent.py`               | `.run_on()` shortcut method                                                                                                                          | ~10          |
| `src/adk_fluent/__init__.py`            | Export `dispatch`, `join`, `Source`, `Inbox`, `StreamRunner`                                                                                         | ~5           |
| `examples/cookbook/59_dispatch_join.py` | **NEW**                                                                                                                                              | ~60          |
| `examples/cookbook/60_stream_runner.py` | **NEW**                                                                                                                                              | ~60          |

**Total new code: ~560 lines** (down from ~900+ in the previous plan).

## What we eliminated by leveraging stdlib

| Eliminated                                         | Replaced by                                          |
| -------------------------------------------------- | ---------------------------------------------------- |
| `_TASK_REGISTRY` module-level dict + cleanup logic | `contextvars.ContextVar` (auto-scoped, auto-cleaned) |
| `Source` base class with inheritance hierarchy     | `AsyncIterator[str]` protocol + factory functions    |
| `CallbackSource` custom class                      | `Inbox` — thin wrapper around `asyncio.Queue`        |
| Custom structured concurrency                      | `asyncio.Semaphore` + `asyncio.create_task`          |
| Shutdown framework                                 | `signal` + `asyncio.Event`                           |
| Metrics framework                                  | `StreamStats` dataclass with 4 fields                |
| DLQ infrastructure                                 | `on_error` callback parameter                        |

## Verification

1. `pytest tests/ -x --ignore=tests/golden` — regression
1. `python examples/cookbook/59_dispatch_join.py` — dispatch/join assertions
1. `python examples/cookbook/60_stream_runner.py` — stream assertions
1. `ruff check src/adk_fluent/`
1. `pyright src/adk_fluent/_base.py src/adk_fluent/source.py src/adk_fluent/stream.py`

## Context

Parts 1-2 (dispatch/join + StreamRunner) are **implemented and passing all tests**. The user now asks deeper architectural questions:

1. How do ADK sessions interplay with dispatch/join and StreamRunner?
1. What does the execution architecture look like?
1. Is it a separate process? How does the event loop work?
1. What happens with 100 concurrent users × 100 dispatches each?
1. What's missing in Middleware for dispatch/join observability?
1. Design proper ground-up mechanisms, not patch fixes.

This plan covers **Part 3: Session-Aware Execution Architecture** — the hardening layer that makes dispatch/join and StreamRunner production-grade.

______________________________________________________________________

## Architecture: How It All Fits Together

### Execution Model (NOT a Separate Process)

```
┌─────────────── Single Python Process ───────────────┐
│                                                       │
│  asyncio Event Loop (one per process)                 │
│  ┌─────────────────────────────────────────────────┐  │
│  │                                                 │  │
│  │  Web Server (FastAPI/Starlette/etc.)            │  │
│  │  ├── Request 1 → runner.run_async(session_A)    │  │
│  │  ├── Request 2 → runner.run_async(session_B)    │  │
│  │  └── Request N → runner.run_async(session_N)    │  │
│  │                                                 │  │
│  │  StreamRunner (continuous, no HTTP)              │  │
│  │  └── source → runner.run_async(per_item_session)│  │
│  │                                                 │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  All I/O (LLM API calls, tool calls) releases GIL     │
│  via await → true concurrent I/O, no thread needed    │
└───────────────────────────────────────────────────────┘
```

**Key insight**: There is no separate process. ADK's `Runner` and `InMemoryRunner` are plain Python classes. `runner.run_async()` is an async generator. The caller's event loop drives everything. For web apps, the web framework's event loop (uvicorn/gunicorn with uvloop) IS the event loop.

### Session Lifecycle: Who Creates What

```
                     ADK Runner
                         │
              runner.run_async(user_id, session_id, message)
                         │
                ┌────────▼────────┐
                │ _get_or_create_ │    ← Fetches Session from SessionService
                │    session()    │       (InMemory, SQLite, VertexAI, etc.)
                └────────┬────────┘
                         │
                ┌────────▼────────┐
                │ InvocationCtx   │    ← Created once per run_async() call
                │ .session = ←────│──── Same Session object shared by ALL
                │ .agent          │     agents in this invocation tree
                │ .services       │
                └────────┬────────┘
                         │
              agent.run_async(parent_ctx)
                         │
                ┌────────▼────────┐
                │ _create_inv_ctx │    ← parent_ctx.model_copy(update={agent})
                │ (BaseAgent)     │       SHALLOW COPY: same .session ref!
                └────────┬────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
        SequenceAgent          DispatchAgent
        (runs kids              (creates asyncio.Tasks)
         sequentially)               │
                              ┌──────┴──────┐
                              │             │
                          Task A         Task B
                          agent.run_async(ctx)  ← SAME ctx.session!
                          writes to state       writes to state
```

### Session-State Sharing: Why It's Safe (and Where It Could Break)

**Why concurrent session.state writes are safe in asyncio:**

1. asyncio is **single-threaded** — only one coroutine runs Python code at a time
1. `dict.__setitem__` is **atomic at bytecode level** in CPython
1. Between any two `await` points, code runs to completion without interruption

**The one pattern that can race (compound get-then-set):**

```python
# Safe: single atomic write
ctx.session.state["key"] = value

# UNSAFE across awaits:
results = ctx.session.state.get("_dispatch_results")  # read
if results is None:
    results = {}                                        # ← another task could have set it between these lines IF there's an await in between
    ctx.session.state["_dispatch_results"] = results    # write
```

**Current mitigation**: In DispatchAgent, the init-if-None pattern runs synchronously without awaits between get and set, so it IS safe within asyncio. The dict mutations themselves are atomic.

**Where it WOULD break**: With distributed session services (VertexAI, Database) that have eventual consistency. Two tasks writing to the same session could see stale reads. This is an **ADK-level concern**, not ours — ADK's Session model has no locking either.

### 100 Users × 100 Dispatches = 10,000 Tasks

```
Event Loop
├── User 1: runner.run_async(session_1)
│   └── Pipeline: writer >> dispatch(A,B,...×100) >> join()
│       ├── ContextVar scope 1: {task_A: Task, task_B: Task, ...}
│       └── Global budget: Semaphore(configurable)
│
├── User 2: runner.run_async(session_2)  ← DIFFERENT session
│   └── Pipeline: writer >> dispatch(A,B,...×100) >> join()
│       ├── ContextVar scope 2: {task_A: Task, ...}  ← ISOLATED
│       └── Global budget: SAME semaphore (shared)
│
└── User 100: runner.run_async(session_100)
    └── ...
```

**Isolation guarantees:**

- Each user has their own Session (different session_id) → state fully isolated
- Each user's dispatch tasks are tracked in their own ContextVar scope → task registries isolated
- The global task budget semaphore IS shared → prevents 100×100 = 10,000 concurrent LLM calls
- LLM API calls are I/O-bound → asyncio handles 10,000 concurrent awaits efficiently

**Resource analysis for 10,000 concurrent dispatch tasks:**

- Memory: ~2KB per task × 10,000 = ~20MB (negligible)
- File descriptors: limited by LLM API connection pooling (httpx defaults to 100 connections)
- LLM API quota: the REAL bottleneck — Gemini rate limits will throttle before Python does
- Task budget semaphore: bounds to N (default 50) concurrent agent executions across all users

______________________________________________________________________

## Part 3A: Configurable Task Budget

**Problem**: `_DEFAULT_TASK_BUDGET = 50` is hardcoded. Users need to configure it.

### Changes to `src/adk_fluent/_base.py`

**1. Make DispatchAgent accept a configurable budget:**

```python
# At module level, keep _DEFAULT_TASK_BUDGET = 50

class DispatchAgent(BaseAgent):
    _task_budget: int | None  # NEW: per-dispatch budget override

    def __init__(self, *, task_budget: int | None = None, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, "_task_budget", task_budget)

    async def _run_async_impl(self, ctx):
        budget = _global_task_budget.get()
        if budget is None:
            limit = self._task_budget or _DEFAULT_TASK_BUDGET
            budget = asyncio.Semaphore(limit)
            _global_task_budget.set(budget)
        # ... rest unchanged
```

**2. Add `.task_budget(n)` to the `dispatch()` factory and `_DispatchBuilder`:**

```python
def dispatch(*agents, names=None, on_complete=None, on_error=None,
             progress_key=None, task_budget: int | None = None):
    # ... pass task_budget through to builder

class _DispatchBuilder(BuilderBase):
    def __init__(self, ..., task_budget):
        self._task_budget = task_budget

    def task_budget(self, n: int) -> Self:
        self._task_budget = n
        return self
```

### Changes to `src/adk_fluent/stream.py`

**3. StreamRunner sets the global budget before processing:**

```python
class StreamRunner:
    def __init__(self, builder):
        # ... existing init
        self._task_budget: int = 50  # NEW

    def task_budget(self, n: int) -> StreamRunner:
        self._task_budget = n
        return self

    async def start(self):
        # Set global task budget for all dispatch agents within this stream
        _global_task_budget.set(asyncio.Semaphore(self._task_budget))
        # ... rest unchanged
```

______________________________________________________________________

## Part 3B: Dispatch-Aware Middleware Lifecycle

**Problem**: Middleware has no hooks for dispatch/join/stream lifecycle. When an agent is dispatched, `before_agent`/`after_agent` fire but middleware can't tell if it's a background dispatch or main pipeline agent.

### Design: Add optional dispatch/stream hooks to Middleware protocol

Add 5 new optional methods to the `Middleware` protocol in `src/adk_fluent/middleware.py`:

```python
@runtime_checkable
class Middleware(Protocol):
    # ... existing hooks unchanged ...

    # --- Dispatch lifecycle (NEW) ---

    async def on_dispatch(self, ctx: Any, task_name: str, agent_name: str) -> None:
        """Called when a task is dispatched as background. Non-blocking."""
        return None

    async def on_task_complete(self, ctx: Any, task_name: str, result: str) -> None:
        """Called when a dispatched task completes successfully."""
        return None

    async def on_task_error(self, ctx: Any, task_name: str, error: Exception) -> None:
        """Called when a dispatched task fails."""
        return None

    async def on_join(self, ctx: Any, joined_names: list[str],
                      timed_out_names: list[str]) -> None:
        """Called after a join completes, reporting which tasks completed vs timed out."""
        return None

    # --- Stream lifecycle (NEW) ---

    async def on_stream_item(self, ctx: Any, item: str, result: str | None,
                             error: Exception | None) -> None:
        """Called after each stream item is processed (success or failure)."""
        return None
```

### Wire hooks into DispatchAgent and JoinAgent

**In `src/adk_fluent/_base.py`, DispatchAgent.\_run_async_impl:**

```python
# After creating each task, fire on_dispatch
middleware_hooks = ctx.session.state.get("_middleware_hooks")
if middleware_hooks:
    await middleware_hooks.on_dispatch(ctx, task_name, child.name)

# In _run_child, after completion:
if middleware_hooks:
    await middleware_hooks.on_task_complete(ctx, tname, last_text)

# In _run_child, on error:
if middleware_hooks:
    await middleware_hooks.on_task_error(ctx, tname, exc)
```

**In JoinAgent.\_run_async_impl:**

```python
# After asyncio.wait completes:
joined = [task_to_name[t] for t in done if not t.exception()]
timed_out = [task_to_name[t] for t in pending]
if middleware_hooks:
    await middleware_hooks.on_join(ctx, joined, timed_out)
```

### Better approach: Use ContextVar for middleware hooks

Rather than storing middleware hooks in session state (non-serializable), use a ContextVar:

```python
# In _base.py, at module level:
_middleware_dispatch_hooks: ContextVar[Any] = ContextVar(
    "_middleware_dispatch_hooks", default=None
)
```

The `_MiddlewarePlugin` adapter in `middleware.py` sets this ContextVar in `before_run_callback`:

```python
class _MiddlewarePlugin(BasePlugin):
    async def before_run_callback(self, *, invocation_context):
        # Make middleware stack accessible to DispatchAgent/JoinAgent
        _middleware_dispatch_hooks.set(self)
        return await self._run_stack("before_run", invocation_context)
```

Then DispatchAgent/JoinAgent read from this ContextVar (which propagates through create_task).

### Wire stream hooks into StreamRunner

**In `src/adk_fluent/stream.py`, StreamRunner.start():**

```python
async def _process(item: str):
    async with sem:
        self.stats.in_flight += 1
        result_text = None
        error = None
        try:
            # ... existing processing ...
            result_text = last_text
        except Exception as exc:
            error = exc
            # ... existing error handling ...
        finally:
            self.stats.in_flight -= 1
            # Fire stream middleware hook
            if self._middlewares:
                for mw in self._middlewares:
                    hook = getattr(mw, "on_stream_item", None)
                    if hook:
                        await hook(None, item, result_text, error)
```

### Update \_MiddlewarePlugin adapter

Add dispatch-specific callback methods to `_MiddlewarePlugin` in `middleware.py`:

```python
class _MiddlewarePlugin(BasePlugin):
    # ... existing methods ...

    async def on_dispatch(self, ctx, task_name, agent_name):
        await self._run_stack_void("on_dispatch", ctx, task_name, agent_name)

    async def on_task_complete(self, ctx, task_name, result):
        await self._run_stack_void("on_task_complete", ctx, task_name, result)

    async def on_task_error(self, ctx, task_name, error):
        await self._run_stack_void("on_task_error", ctx, task_name, error)

    async def on_join(self, ctx, joined_names, timed_out_names):
        await self._run_stack_void("on_join", ctx, joined_names, timed_out_names)

    async def on_stream_item(self, ctx, item, result, error):
        await self._run_stack_void("on_stream_item", ctx, item, result, error)
```

______________________________________________________________________

## Part 3C: Execution Context Enrichment

**Problem**: `before_agent`/`after_agent` callbacks fire for dispatched agents but don't know the execution mode.

### Add dispatch metadata to ContextVar

```python
# In _base.py, module level:
_execution_mode: ContextVar[str] = ContextVar("_execution_mode", default="pipeline")
```

**In DispatchAgent.\_run_async_impl, inside \_run_child:**

```python
async def _run_child(agent=_child, tname=_name, ...):
    # Set execution mode for this task's context
    _execution_mode.set("dispatched")
    # ... run agent ...
```

**Expose to middleware via callback context enrichment:**

The `before_agent`/`after_agent` hooks receive a `callback_context`. We can make execution mode queryable:

```python
# In middleware.py, update before_agent_callback:
async def before_agent_callback(self, *, agent, callback_context):
    mode = _execution_mode.get("pipeline")
    return await self._run_stack(
        "before_agent",
        callback_context,
        getattr(agent, "name", str(agent)),
        # Pass mode as keyword arg if the middleware accepts it
    )
```

**Simpler alternative**: Middleware authors can import `_execution_mode` directly:

```python
from adk_fluent._base import _execution_mode

class MyMiddleware:
    async def before_agent(self, ctx, agent_name):
        mode = _execution_mode.get("pipeline")
        if mode == "dispatched":
            print(f"[BACKGROUND] {agent_name} starting")
        else:
            print(f"[MAIN] {agent_name} starting")
```

We'll expose this as a public helper:

```python
# In _base.py or a new _dispatch_context.py:
def get_execution_mode() -> str:
    """Returns 'pipeline', 'dispatched', or 'stream'."""
    return _execution_mode.get("pipeline")
```

______________________________________________________________________

## Part 3D: StreamRunner Middleware Integration

**Problem**: StreamRunner creates InMemoryRunner directly, bypassing middleware.

### Design: StreamRunner accepts middleware list

```python
class StreamRunner:
    def __init__(self, builder):
        # ... existing
        self._middlewares: list = []  # NEW

    def middleware(self, mw) -> StreamRunner:
        """Add middleware for stream execution observability."""
        self._middlewares.append(mw)
        return self

    async def start(self):
        agent = self._builder.build()
        app_name = f"_stream_{agent.name}"

        # If middleware configured, compile into plugin
        plugins = None
        if self._middlewares:
            from adk_fluent.middleware import _MiddlewarePlugin
            plugins = [_MiddlewarePlugin(
                name=f"{app_name}_middleware",
                stack=list(self._middlewares),
            )]

        # Also inherit middleware from the builder if it has any
        builder_mw = getattr(self._builder, "_middlewares", [])
        if builder_mw:
            if plugins is None:
                plugins = []
            plugins.append(_MiddlewarePlugin(
                name=f"{app_name}_builder_mw",
                stack=list(builder_mw),
            ))

        runner = InMemoryRunner(agent=agent, app_name=app_name, plugins=plugins)
        # ... rest unchanged, but also set _execution_mode to "stream"
```

This means middleware attached to the builder flows into StreamRunner execution, and the standard ADK plugin lifecycle (before_run, after_run, before_agent, etc.) fires for each stream item.

______________________________________________________________________

## Part 3E: DispatchLogMiddleware — Built-in Observability

Add a ready-to-use middleware for dispatch/join observability:

```python
# In middleware.py:

class DispatchLogMiddleware:
    """Observability for dispatch/join lifecycle.

    Usage:
        pipeline = (
            writer
            >> dispatch(emailer, optimizer)
            >> formatter
            >> join()
        )
        pipeline.middleware(DispatchLogMiddleware())
    """

    def __init__(self):
        self.dispatch_log: list[dict] = []

    async def on_dispatch(self, ctx, task_name, agent_name):
        self.dispatch_log.append({
            "event": "dispatch", "task": task_name,
            "agent": agent_name, "time": _time.time(),
        })

    async def on_task_complete(self, ctx, task_name, result):
        self.dispatch_log.append({
            "event": "task_complete", "task": task_name,
            "result_len": len(result) if result else 0,
            "time": _time.time(),
        })

    async def on_task_error(self, ctx, task_name, error):
        self.dispatch_log.append({
            "event": "task_error", "task": task_name,
            "error": str(error), "time": _time.time(),
        })

    async def on_join(self, ctx, joined, timed_out):
        self.dispatch_log.append({
            "event": "join", "joined": joined,
            "timed_out": timed_out, "time": _time.time(),
        })
```

______________________________________________________________________

## Files to Modify

| File                                          | Changes                                                                                                                                                                                                         | Est. Lines |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| `src/adk_fluent/_base.py`                     | Configurable `task_budget` on DispatchAgent + builder; `_execution_mode` ContextVar; `_middleware_dispatch_hooks` ContextVar; fire middleware hooks from DispatchAgent/JoinAgent; export `get_execution_mode()` | ~60        |
| `src/adk_fluent/middleware.py`                | 5 new optional hooks on Middleware protocol; 5 new methods on `_MiddlewarePlugin`; `DispatchLogMiddleware` built-in                                                                                             | ~80        |
| `src/adk_fluent/stream.py`                    | `.middleware()` fluent method; `.task_budget()` fluent method; plugin compilation; `_execution_mode.set("stream")`; fire `on_stream_item` hooks                                                                 | ~40        |
| `src/adk_fluent/__init__.py`                  | Export `DispatchLogMiddleware`, `get_execution_mode`                                                                                                                                                            | ~3         |
| `src/adk_fluent/prelude.py`                   | Export `DispatchLogMiddleware`                                                                                                                                                                                  | ~2         |
| `examples/cookbook/61_dispatch_middleware.py` | **NEW** — cookbook demonstrating dispatch-aware middleware                                                                                                                                                      | ~60        |
| `tests/manual/test_api_surface_v2.py`         | Update expected exports count                                                                                                                                                                                   | ~2         |

**Total new/modified code: ~250 lines**

______________________________________________________________________

## Verification

1. `pytest tests/ -x --ignore=tests/golden --ignore=tests/test_property_based.py` — regression
1. `python examples/cookbook/59_dispatch_join.py` — existing dispatch/join assertions still pass
1. `python examples/cookbook/60_stream_runner.py` — existing stream assertions still pass
1. `python examples/cookbook/61_dispatch_middleware.py` — NEW middleware assertions pass
1. `ruff check src/adk_fluent/`
1. `pyright src/adk_fluent/_base.py src/adk_fluent/middleware.py src/adk_fluent/stream.py`
