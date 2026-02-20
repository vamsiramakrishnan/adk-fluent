# ADK-FLUENT: Specification v4 — Comprehensive

**Status:** Supersedes SPEC_v3.md\
**Philosophy:** Rise with the tide of ADK, never get bolted to the ground by it\
**Architecture:** Expression IR → Backend Protocol → ADK (or anything else)\
**New in v4:** Seed-based IR generation, ADK construct alignment, middleware-as-plugin compilation, scope-aware state, event-stream protocol

______________________________________________________________________

## 0. The Meta-Pattern, Evolved

v3 established the IR as the architectural keystone. v4 makes the IR itself **self-seeding** — generated from ADK's own type system rather than hand-coded to match it.

### 0.1 The Seed-Based IR Generation Pipeline

The v3 spec defined IR node types by hand: `AgentNode`, `SequenceNode`, `LoopNode`, etc. This creates a second maintenance burden — now instead of just keeping wrappers in sync with ADK, we also keep IR nodes in sync with ADK. The meta-pattern demands we solve this structurally.

**The insight:** ADK's agent types are Pydantic `BaseModel` subclasses with fully introspectable `model_fields`. The IR node types should be *derived* from ADK's own type definitions, not written by hand to mirror them.

```
┌──────────────────────────────────────────────────┐
│  ADK Source (Pydantic BaseModels)                │
│  BaseAgent, LlmAgent, LoopAgent, ParallelAgent,  │
│  SequentialAgent, EventActions, State, App...     │
└──────────────────┬───────────────────────────────┘
                   │ introspect via model_fields,
                   │ __mro__, @final, field_validator
                   ▼
┌──────────────────────────────────────────────────┐
│  IR Seed Generator (codegen/ir_seed.py)          │
│  - Scans ADK agent hierarchy                     │
│  - Extracts field names, types, defaults         │
│  - Classifies: structural vs behavioral vs config│
│  - Emits frozen dataclass IR nodes               │
│  - Emits Backend.compile() dispatch stubs        │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│  Generated IR (_ir_generated.py)                 │
│  AgentNode, SequenceNode, LoopNode, etc.         │
│  + field mapping metadata for backend compilation│
└──────────────────┬───────────────────────────────┘
                   │  hand-written enrichments
                   ▼
┌──────────────────────────────────────────────────┐
│  IR Extensions (_ir_extensions.py)               │
│  writes_keys, reads_keys, produces/consumes,     │
│  transfer_targets, execution_config              │
│  (These are adk-fluent concepts, not ADK's)      │
└──────────────────────────────────────────────────┘
```

**How the seed generator works:**

```python
# codegen/ir_seed.py (sketch)
import inspect
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.parallel_agent import ParallelAgent

ADK_AGENT_CLASSES = [
    LlmAgent, LoopAgent, SequentialAgent, ParallelAgent,
]

def extract_ir_fields(adk_class: type) -> dict:
    """Extract fields from a Pydantic model, classifying them."""
    structural = {}   # sub_agents, max_iterations — shape the IR graph
    behavioral = {}   # before_agent_callback, tools — compiled by backend
    config = {}       # model, instruction, description — carried as data

    for name, field_info in adk_class.model_fields.items():
        if name in ('parent_agent',):
            continue  # Skip internal framework fields
        annotation = field_info.annotation

        if name == 'sub_agents':
            structural[name] = annotation
        elif 'callback' in name.lower() or name == 'tools':
            behavioral[name] = annotation
        else:
            config[name] = annotation

    return {'structural': structural, 'behavioral': behavioral, 'config': config}

def generate_ir_node(adk_class: type) -> str:
    """Generate a frozen dataclass IR node from an ADK class."""
    fields = extract_ir_fields(adk_class)
    # ... emit @dataclass(frozen=True) with config fields as data,
    #     structural fields as tuple[Node, ...], behavioral as dict
```

**What this means:** When ADK v2.0 adds a `ConditionalAgent` with new fields, we re-run the seed generator. It discovers the new class, extracts its fields, and generates an IR node. The hand-written `_ir_extensions.py` adds adk-fluent-specific enrichments (like `writes_keys`, `reads_keys`). The backend adapter gets a new `case ConditionalNode():` branch. **No user-facing API changes.**

### 0.2 The Three Layers of Hand-Written Code

v4 minimizes hand-coding to three categories:

| Layer                       | What                                                               | Why hand-written                                                      |
| --------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------- |
| **Expression algebra**      | `>>`, `\|`, `*`, `//`, `@` operators                               | Semantic meaning; operators define user intent                        |
| **IR extensions**           | `writes_keys`, `reads_keys`, `produces`/`consumes`, transfer edges | adk-fluent concepts that don't exist in ADK                           |
| **Backend behavioral code** | `_FnAgent._run_async_impl`, `_TapAgent._run_async_impl`            | Custom agent types that bridge fluent transforms to ADK's event model |

Everything else — builder classes, IR node types, backend dispatch, tool wrappers, config stubs — is generated.

______________________________________________________________________

## 1. ADK Construct Mapping for DevEx Alignment

Existing ADK developers think in specific constructs: `App`, `Session`, `Agent`, `Tool`, `Context`, `State`, `Artifact`, `Plugin`. adk-fluent must map cleanly onto these mental models rather than replacing them with unfamiliar abstractions.

### 1.1 The ADK Developer's Mental Model

From reading the ADK source (`base_agent.py:85-163`, `app.py:102-155`, `state.py:20-82`, `callback_context.py`, `tool_context.py`, `base_plugin.py`, `plugin_manager.py`), the construct hierarchy is:

```
App (name, root_agent, plugins[], context_cache_config)
 └─ Runner (app_name, agent, session_service, artifact_service, memory_service, plugins→PluginManager)
     └─ InvocationContext (session, agent, invocation_id, branch, services, run_config)
         └─ BaseAgent.run_async(ctx) → AsyncGenerator[Event, None]  [@final]
             ├─ _handle_before_agent_callback(ctx) → Event | None
             ├─ _run_async_impl(ctx) → AsyncGenerator[Event, None]  [subclass impl]
             │   ├─ LlmAgent: SingleFlow → LLM call loop
             │   │   ├─ before_model_callback(CallbackContext, LlmRequest) → LlmResponse?
             │   │   ├─ LLM.generate_content_async(request)
             │   │   ├─ after_model_callback(CallbackContext, LlmResponse) → LlmResponse?
             │   │   └─ if function_calls:
             │   │       ├─ before_tool_callback(tool, args, ToolContext) → dict?
             │   │       ├─ tool.run_async(args, tool_context)
             │   │       └─ after_tool_callback(tool, args, ToolContext, result) → dict?
             │   ├─ SequentialAgent: for sub in sub_agents: yield from sub.run_async(ctx)
             │   ├─ ParallelAgent: concurrent tasks, isolated branches
             │   └─ LoopAgent: repeat until escalate or max_iterations
             └─ _handle_after_agent_callback(ctx) → Event | None
```

**Plugin execution order** (from `plugin_manager.py:166-200`): Plugins run *before* agent-level callbacks. A plugin returning non-None short-circuits all remaining plugins AND agent callbacks. This is critical for middleware design.

### 1.2 adk-fluent Construct Mapping Table

| ADK Construct      | ADK Source Location                  | adk-fluent v4 Equivalent                                                                     | Notes                                                                              |
| ------------------ | ------------------------------------ | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `App`              | `apps/app.py:102-155`                | `Pipeline.to_app()` or explicit `App(root_agent=pipeline.compile())`                         | adk-fluent pipelines compile to an agent tree; wrapping in App adds plugin support |
| `Runner`           | `runners.py`                         | `pipeline.run()` / `pipeline.stream()` auto-creates `InMemoryRunner`                         | The runner is infrastructure, not user-facing in adk-fluent                        |
| `Session`          | `sessions/session.py`                | Transparent — state flows through IR, backend manages sessions                               | Users interact with state via `S.*` transforms, not session objects                |
| `State`            | `sessions/state.py:20-82`            | `S.pick()`, `S.drop()`, `S.merge()`, `S.rename()`, `S.default()` + `StateKey("app:setting")` | v4 adds scope awareness to transforms                                              |
| `Agent` (LlmAgent) | `agents/llm_agent.py`                | `Agent("name", "model").instruct(...)`                                                       | Direct mapping; IR → `AgentNode` → backend compiles to `LlmAgent`                  |
| `SequentialAgent`  | `agents/sequential_agent.py`         | `a >> b >> c` (the `>>` operator)                                                            | IR → `SequenceNode`                                                                |
| `ParallelAgent`    | `agents/parallel_agent.py`           | `a \| b \| c` (the `\|` operator)                                                            | IR → `ParallelNode`                                                                |
| `LoopAgent`        | `agents/loop_agent.py`               | `loop(body, until=predicate, max=N)`                                                         | IR → `LoopNode`                                                                    |
| `Tool`             | `tools/function_tool.py`             | `.tool(fn)` on Agent builder                                                                 | FunctionTool wrapping happens at compile time                                      |
| `CallbackContext`  | `agents/callback_context.py`         | `.before_model(fn)`, `.after_model(fn)` on Agent builder                                     | Callbacks flow through IR → backend compiles to ADK callbacks                      |
| `ToolContext`      | `tools/tool_context.py`              | Auto-injected — tools with `tool_context: ToolContext` param get it                          | No adk-fluent wrapper needed; ADK's FunctionTool handles detection                 |
| `BasePlugin`       | `plugins/base_plugin.py`             | `Middleware` protocol → compiled to `BasePlugin` subclass by ADK backend                     | v4's key insight: middleware IS plugins                                            |
| `PluginManager`    | `plugins/plugin_manager.py`          | Transparent — backend registers compiled middleware as plugins on the App                    |                                                                                    |
| `EventActions`     | `events/event_actions.py`            | `AgentEvent.state_delta`, `AgentEvent.transfer_to`, `AgentEvent.escalate`                    | IR-level event representation                                                      |
| `Artifact`         | `artifacts/base_artifact_service.py` | `Artifact("filename")` helper + `ctx.save_artifact()` in tools                               | Pass-through to ADK's artifact system                                              |

### 1.3 The "Escape Hatch" Principle

Every adk-fluent construct must allow dropping to raw ADK when needed:

```python
# Start in adk-fluent
pipeline = Agent("classifier") >> Agent("resolver")

# Compile to ADK objects
adk_agent = pipeline.compile()  # Returns native ADK SequentialAgent

# Now you have a standard ADK agent — use it with raw ADK Runner, App, etc.
from google.adk.apps import App
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

app = App(name="my_app", root_agent=adk_agent)
runner = Runner(app_name="my_app", agent=app.root_agent,
                session_service=InMemorySessionService())

# Or: mix adk-fluent agents with raw ADK agents
from google.adk.agents import LlmAgent
raw_agent = LlmAgent(name="raw", model="gemini-2.5-flash", instruction="Hello")
pipeline = Agent("fluent_a") >> raw_agent >> Agent("fluent_c")
# The IR recognizes raw ADK agents as opaque nodes
```

______________________________________________________________________

## 2. Disfluency Addendums (New Findings from Codebase Examination)

These extend the v3 disfluency catalog with issues discovered by examining ADK's actual source.

### 2.1 State Transform Semantics Are Deeper Than v3 Identified

**v3 diagnosis:** `S.pick()` / `S.drop()` don't work because `_FnAgent` does additive merges.

**v4 addendum — scope-aware transforms required:**

From `state.py:23-25`:

```python
class State:
    APP_PREFIX = "app:"
    USER_PREFIX = "user:"
    TEMP_PREFIX = "temp:"
```

And from `base_session_service.py`, `append_event` skips `temp:` keys and routes `app:` / `user:` keys to separate storage. This means:

1. `S.pick("a")` returning a `StateReplacement` would **destroy** `app:*` and `user:*` keys — catastrophic for cross-session state
1. `S.drop("x")` needs to know whether `x` means session-scoped `x` or could be `app:x` or `user:x`
1. The `State` class has no `__delitem__` — you can set keys but not remove them. State "deletion" must be modeled as setting to a sentinel value or handled at the session service level.

**Revised transform semantics:**

```python
class TransformSemantics(Enum):
    MERGE = "merge"              # Additive: add/update keys
    REPLACE_SESSION = "replace_session"  # Replace only unprefixed keys
    DELETE_KEYS = "delete_keys"  # Explicit key removal (set to _DELETED sentinel)

_DELETED = object()  # Sentinel: when backend sees this, it removes the key

class S:
    @staticmethod
    def pick(*keys: str) -> TransformNode:
        """Keep only these session-scoped keys. Preserves app: and user: keys."""
        # Semantics: REPLACE_SESSION — only touches unprefixed keys
        ...

    @staticmethod
    def drop(*keys: str) -> TransformNode:
        """Remove these specific keys from state."""
        # Semantics: DELETE_KEYS with explicit key list
        ...

    @staticmethod
    def merge(*sources: str, into: str) -> TransformNode:
        """Merge values from multiple keys into one. Additive."""
        # Semantics: MERGE
        ...
```

The ADK backend implements `REPLACE_SESSION` by:

1. Scanning current state for unprefixed keys not in the replacement set
1. Setting them to `None` in `event_actions.state_delta` (ADK treats this as "overwrite with None")
1. Writing the replacement keys normally

The ADK backend implements `DELETE_KEYS` by setting those keys to `None` in `state_delta`.

### 2.2 The Plugin System Is the Middleware Compilation Target

**v3 proposed:** Middleware protocol compiled into ADK callbacks on the agent.

**v4 correction:** Middleware must compile into `BasePlugin` subclasses, not agent-level callbacks. Here's why (from `base_agent.py:270-301` and `plugin_manager.py:166-200`):

1. **Execution order:** ADK runs plugin callbacks FIRST, then agent callbacks. If middleware compiles to agent callbacks, it runs AFTER user-defined plugins — wrong priority.
1. **Scope:** Agent callbacks are per-agent. Plugin callbacks are global (all agents). Middleware concepts like `token_budget` and `cost_tracker` need global scope.
1. **Short-circuit propagation:** Plugin short-circuit prevents agent callbacks from running. If we want `cache` middleware to skip the LLM call, it must be a plugin, not an agent callback.
1. **Error handling:** Plugins have `on_model_error_callback` and `on_tool_error_callback` (added in recent ADK versions). Agent callbacks don't have error hooks.

**Revised compilation strategy:**

```python
# adk_fluent/backends/adk.py

class MiddlewarePlugin(BasePlugin):
    """Compiles adk-fluent middleware stack into an ADK Plugin."""

    def __init__(self, name: str, middlewares: list[Middleware]):
        super().__init__(name=name)
        self._stack = middlewares

    async def before_model_callback(
        self, *, callback_context, llm_request
    ):
        for mw in self._stack:
            result = await mw.on_llm_request(callback_context, llm_request)
            if result is not None:
                return result  # Short-circuit: skip LLM AND remaining middleware
        return None

    async def after_model_callback(
        self, *, callback_context, llm_response
    ):
        # Run in reverse order for after-callbacks (onion model)
        for mw in reversed(self._stack):
            result = await mw.on_llm_response(callback_context, llm_response)
            if result is not None:
                return result
        return None

    async def before_tool_callback(
        self, *, tool, tool_args, tool_context
    ):
        for mw in self._stack:
            result = await mw.on_tool_call(tool, tool_args, tool_context)
            if result is not None:
                return result
        return None

    async def on_model_error_callback(
        self, *, callback_context, llm_request, error
    ):
        for mw in self._stack:
            result = await mw.on_error(callback_context, error)
            if result is not None:
                return result
        return None

    # ... etc for all plugin callback types
```

This middleware plugin gets registered on the `App` or passed to the `Runner`:

```python
# User writes:
pipeline = (
    Agent("support")
    .use(token_budget(50_000))
    .use(cost_tracker(bq_sink))
    .build()
)

# ADK backend compiles to:
app = App(
    name="support_app",
    root_agent=compiled_agent,
    plugins=[
        MiddlewarePlugin("adk_fluent_middleware", [
            TokenBudgetMiddleware(50_000),
            CostTrackerMiddleware(bq_sink),
        ])
    ]
)
```

### 2.3 Backend Protocol Must Speak Events, Not Strings

**v3 proposed:** `Backend.run() -> str`, `Backend.stream() -> AsyncIterator[str]`

**v4 correction:** ADK's execution model is event-stream-centric. Every agent yields `Event` objects containing `content`, `actions` (state_delta, transfer_to_agent, escalate, artifact_delta), `author`, `branch`, `invocation_id`. Collapsing this to `str` loses:

- State delta propagation (can't test state changes)
- Transfer-to-agent signals (can't model delegation)
- Escalation flags (can't test loop termination)
- Tool call tracking (can't assert which tools were called)
- Artifact versioning (can't verify file operations)
- Event authorship (can't trace which agent produced what)

**Revised protocol:**

```python
from dataclasses import dataclass, field
from typing import Any, Protocol, AsyncIterator, runtime_checkable

@dataclass
class AgentEvent:
    """Backend-agnostic event representation.

    Maps to ADK's Event model but decoupled from Pydantic/genai types.
    """
    author: str
    content: str | None = None
    state_delta: dict[str, Any] = field(default_factory=dict)
    artifact_delta: dict[str, int] = field(default_factory=dict)
    transfer_to: str | None = None
    escalate: bool = False
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_responses: list[dict[str, Any]] = field(default_factory=list)
    is_final: bool = False
    invocation_id: str | None = None
    branch: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Backend(Protocol):
    """Compiles an IR graph into a runnable and executes it."""

    def compile(self, node: Node) -> Any:
        """Transform an IR node tree into a backend-specific runnable."""
        ...

    async def run(self, compiled: Any, prompt: str, **kwargs) -> list[AgentEvent]:
        """Execute a compiled graph and return all events."""
        ...

    async def stream(self, compiled: Any, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        """Stream events as they occur."""
        ...


# Convenience function for users who just want the answer
def final_text(events: list[AgentEvent]) -> str:
    """Extract the final response text from an event stream."""
    for event in reversed(events):
        if event.is_final and event.content:
            return event.content
    return ""
```

The ADK backend maps `Event → AgentEvent`:

```python
def _event_to_agent_event(event: Event) -> AgentEvent:
    return AgentEvent(
        author=event.author,
        content=event.content.parts[0].text if event.content and event.content.parts else None,
        state_delta=dict(event.actions.state_delta) if event.actions else {},
        artifact_delta=dict(event.actions.artifact_delta) if event.actions else {},
        transfer_to=event.actions.transfer_to_agent if event.actions else None,
        escalate=bool(event.actions.escalate) if event.actions else False,
        is_final=event.is_final_response(),
        invocation_id=event.invocation_id,
        branch=event.branch,
    )
```

### 2.4 DI Must Piggyback on ADK's ToolContext Injection

**v3 proposed:** Custom Resource/DI system with signature manipulation.

**v4 correction based on codebase analysis:** ADK's `FunctionTool` (`tools/function_tool.py`) already detects `ToolContext` parameters via `inspect.signature()` and injects them at call time, excluding them from the LLM schema. We should extend this pattern rather than fight it.

**Strategy: Closure injection at compile time with signature preservation:**

```python
import functools
import inspect

def _inject_resources(fn: Callable, resources: dict[str, Any]) -> Callable:
    """Wrap a tool function to inject resource dependencies.

    ADK's FunctionTool uses inspect.signature() to build the LLM schema.
    We must produce a wrapper whose signature excludes resource params
    so they don't appear in the function declaration sent to the LLM.
    """
    sig = inspect.signature(fn)
    # Identify which params are resources (matched by name)
    resource_params = {
        name for name in sig.parameters
        if name in resources and name != 'tool_context'
    }

    # Build new signature without resource params
    new_params = [
        p for name, p in sig.parameters.items()
        if name not in resource_params
    ]
    new_sig = sig.replace(parameters=new_params)

    @functools.wraps(fn)
    async def wrapped(*args, **kwargs):
        # Inject resources into kwargs
        for name in resource_params:
            if name not in kwargs:
                kwargs[name] = resources[name]
        if inspect.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)
        return fn(*args, **kwargs)

    wrapped.__signature__ = new_sig
    return wrapped
```

This preserves ADK's existing `ToolContext` detection while adding resource injection transparently.

### 2.5 Transfer-to-Agent Needs IR Awareness

From `event_actions.py:53-54`:

```python
transfer_to_agent: Optional[str] = None
"""If set, the event transfers to the specified agent."""
```

This is a first-class ADK concept used for LLM-driven delegation. When an `LlmAgent` with `sub_agents` decides to delegate, the LLM generates a `transfer_to_agent` function call, which becomes a `transfer_to_agent` field on EventActions. The Runner then routes the next invocation to the target agent.

The v3 IR doesn't model this. For the IR to accurately represent the execution graph:

```python
@dataclass(frozen=True)
class AgentNode:
    # ... existing fields ...
    transfer_targets: frozenset[str] = frozenset()

    # Auto-populated from sub_agents when building the IR:
    # If the agent has sub_agents, they become potential transfer targets
    # because ADK's LlmAgent auto-generates transfer tools for sub_agents
```

This lets the `VizBackend` draw transfer edges (dashed arrows) between agents, and the contract checker can verify that transfer targets exist in the graph.

### 2.6 ExecutionConfig Should Be IR-Level

From `run_config.py`, ADK's `RunConfig` carries:

- `max_llm_calls: int = 500` — hard loop safety valve
- `streaming_mode: StreamingMode` — none/sse/bidi
- `speech_config`, `response_modalities` — multimodal settings

These are execution constraints, not middleware concerns. The IR should carry them:

```python
@dataclass(frozen=True)
class ExecutionConfig:
    """Top-level execution constraints for a compiled pipeline."""
    max_llm_calls: int = 500
    timeout_seconds: float | None = None
    streaming_mode: Literal["none", "sse", "bidi"] = "none"
```

This gets attached to the pipeline at build time and passed to the backend at compile time:

```python
pipeline = (
    Agent("a") >> Agent("b")
).with_config(max_llm_calls=100, timeout_seconds=30)
```

______________________________________________________________________

## 3. The Revised IR (Seed-Generated + Hand-Extended)

### 3.1 Generated IR Node Types

These are produced by the seed generator from ADK's Pydantic models:

```python
# _ir_generated.py (OUTPUT of codegen/ir_seed.py)
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

@dataclass(frozen=True)
class AgentNode:
    """Generated from google.adk.agents.llm_agent.LlmAgent"""
    name: str
    model: str | None = None
    instruction: str | Callable | None = None
    description: str = ""
    tools: tuple[Any, ...] = ()
    output_key: str | None = None
    output_schema: type | None = None
    input_schema: type | None = None
    include_contents: str = "default"
    generate_content_config: dict[str, Any] = field(default_factory=dict)
    planner: Any | None = None
    code_executor: Any | None = None
    examples: tuple[Any, ...] = ()
    callbacks: dict[str, tuple[Callable, ...]] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)  # Passthrough for unknown fields

@dataclass(frozen=True)
class SequenceNode:
    """Generated from google.adk.agents.sequential_agent.SequentialAgent"""
    name: str
    description: str = ""
    children: tuple['Node', ...] = ()

@dataclass(frozen=True)
class ParallelNode:
    """Generated from google.adk.agents.parallel_agent.ParallelAgent"""
    name: str
    description: str = ""
    children: tuple['Node', ...] = ()

@dataclass(frozen=True)
class LoopNode:
    """Generated from google.adk.agents.loop_agent.LoopAgent"""
    name: str
    description: str = ""
    body: tuple['Node', ...] = ()
    max_iterations: int | None = None
```

### 3.2 Hand-Written IR Extensions

These capture adk-fluent concepts that don't exist in ADK:

```python
# _ir_extensions.py (HAND-WRITTEN, stable)
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

@dataclass(frozen=True)
class TransformNode:
    """adk-fluent state transform — no ADK equivalent."""
    name: str
    fn: Callable
    semantics: Literal["merge", "replace_session", "delete_keys"] = "merge"
    affected_keys: frozenset[str] | None = None  # For static analysis
    scope: Literal["session", "all"] = "session"

@dataclass(frozen=True)
class TapNode:
    """adk-fluent side-effect observation — no ADK equivalent."""
    name: str
    fn: Callable

@dataclass(frozen=True)
class GateNode:
    """adk-fluent approval gate — no ADK equivalent."""
    name: str
    predicate: Callable
    message: str = "Approval required"

@dataclass(frozen=True)
class FallbackNode:
    """adk-fluent try/except for agents — no ADK equivalent."""
    name: str
    children: tuple['Node', ...] = ()

@dataclass(frozen=True)
class RaceNode:
    """adk-fluent first-to-finish — no ADK equivalent."""
    name: str
    children: tuple['Node', ...] = ()

@dataclass(frozen=True)
class MapOverNode:
    """adk-fluent map-over-list — no ADK equivalent."""
    name: str
    list_key: str
    body: 'Node'
    item_key: str = "_item"
    output_key: str = "results"

@dataclass(frozen=True)
class TimeoutNode:
    """adk-fluent timeout wrapper — no ADK equivalent."""
    name: str
    body: 'Node'
    seconds: float

@dataclass(frozen=True)
class RouteNode:
    """adk-fluent conditional routing — no ADK equivalent."""
    name: str
    key: str | None = None
    rules: tuple[tuple[Callable, 'Node'], ...] = ()
    default: 'Node | None' = None

@dataclass(frozen=True)
class OpaqueADKNode:
    """Wraps a raw ADK BaseAgent that wasn't built via adk-fluent."""
    name: str
    adk_agent: Any  # The actual BaseAgent instance
```

### 3.3 IR Enrichment Protocol

The hand-written extensions add analytical capabilities to generated nodes:

```python
# _ir_analysis.py

def enrich_agent_node(node: AgentNode) -> AgentNode:
    """Add writes_keys and reads_keys based on output_key and instruction templates."""
    writes = set()
    reads = set()

    if node.output_key:
        writes.add(node.output_key)

    if isinstance(node.instruction, str):
        # Parse {template_var} patterns
        import re
        for match in re.finditer(r'\{(\w[\w:]*)\}', node.instruction):
            reads.add(match.group(1))

    # Return enriched node (frozen, so we create new)
    return AgentNode(
        **{f.name: getattr(node, f.name) for f in fields(node)},
        # These would be added to the extended version
    )
```

______________________________________________________________________

## 4. Middleware Protocol — Aligned with ADK's Plugin Architecture

### 4.1 The Middleware Protocol

Middleware in adk-fluent maps 1:1 to ADK's `BasePlugin` callback methods. The protocol uses the same signatures:

```python
from typing import Protocol, Any, Optional

class Middleware(Protocol):
    """A composable unit of cross-cutting behavior.

    Each method corresponds to an ADK BasePlugin callback.
    Return None to pass through; return a value to short-circuit.
    """

    @property
    def name(self) -> str: ...

    async def before_agent(self, agent: Any, ctx: Any) -> Optional[Any]:
        """Maps to BasePlugin.before_agent_callback"""
        return None

    async def after_agent(self, agent: Any, ctx: Any) -> Optional[Any]:
        """Maps to BasePlugin.after_agent_callback"""
        return None

    async def before_model(self, ctx: Any, request: Any) -> Optional[Any]:
        """Maps to BasePlugin.before_model_callback"""
        return None

    async def after_model(self, ctx: Any, response: Any) -> Optional[Any]:
        """Maps to BasePlugin.after_model_callback"""
        return None

    async def on_model_error(self, ctx: Any, request: Any, error: Exception) -> Optional[Any]:
        """Maps to BasePlugin.on_model_error_callback"""
        return None

    async def before_tool(self, tool: Any, args: dict, ctx: Any) -> Optional[dict]:
        """Maps to BasePlugin.before_tool_callback"""
        return None

    async def after_tool(self, tool: Any, args: dict, ctx: Any, result: dict) -> Optional[dict]:
        """Maps to BasePlugin.after_tool_callback"""
        return None

    async def on_tool_error(self, tool: Any, args: dict, ctx: Any, error: Exception) -> Optional[dict]:
        """Maps to BasePlugin.on_tool_error_callback"""
        return None
```

### 4.2 Built-in Middleware Implementations

```python
# adk_fluent/middleware/token_budget.py

class TokenBudgetMiddleware:
    """Enforce per-session token limits. Compiles to before_model + after_model plugin callbacks."""

    def __init__(self, max_tokens: int, scope: str = "session"):
        self.name = f"token_budget_{max_tokens}"
        self._max = max_tokens
        self._scope = scope
        self._state_key = f"temp:_token_count" if scope == "invocation" else f"_token_count"

    async def before_model(self, ctx, request):
        count = ctx.state.get(self._state_key, 0)
        if count >= self._max:
            from google.adk.models import LlmResponse
            return LlmResponse(
                content=types.Content(parts=[
                    types.Part(text=f"Token budget of {self._max} exceeded.")
                ])
            )
        return None  # Proceed

    async def after_model(self, ctx, response):
        # Count tokens from response and update state
        if hasattr(response, 'usage_metadata'):
            tokens = (response.usage_metadata.prompt_token_count or 0) + \
                     (response.usage_metadata.candidates_token_count or 0)
            current = ctx.state.get(self._state_key, 0)
            ctx.state[self._state_key] = current + tokens
        return None  # Pass through
```

### 4.3 Middleware → Plugin Compilation

The ADK backend compiles the middleware stack into a single `BasePlugin` subclass that gets registered on the `App`:

```python
class ADKBackend:
    def compile(self, node: Node, middlewares: list[Middleware] = None) -> BaseAgent:
        agent = self._compile_node(node)

        if middlewares:
            # Build App with middleware compiled as plugin
            plugin = MiddlewarePlugin("adk_fluent_mw", middlewares)
            return agent, [plugin]  # Backend returns agent + plugins

        return agent, []
```

______________________________________________________________________

## 5. Resource Lifecycle Mapping to ADK Constructs

### 5.1 Resource Scope → ADK Lifecycle Hook

| Resource Scope | ADK Lifecycle Point                | Implementation                                                                                        |
| -------------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `"app"`        | `App` initialization               | Created before Runner starts; stored as closure in compiled tool functions                            |
| `"session"`    | `session_service.create_session()` | Initialized in `before_run_callback` plugin; stored in `app:` state or closure                        |
| `"invocation"` | `Runner.run_async()` start         | Initialized in `before_run_callback` plugin; stored in `temp:` state; cleaned in `after_run_callback` |

### 5.2 The Lifespan → Plugin Bridge

```python
class LifespanPlugin(BasePlugin):
    """Manages resource lifecycles as an ADK plugin."""

    def __init__(self, resources: list[Resource]):
        super().__init__(name="adk_fluent_lifespan")
        self._resources = resources
        self._app_resources: dict[str, Any] = {}  # Shared across invocations
        self._initialized = False

    async def before_run_callback(self, *, invocation_context):
        # Initialize app-scoped resources (once)
        if not self._initialized:
            for r in self._resources:
                if r.scope == "app":
                    self._app_resources[r.name] = await r.factory().__aenter__()
            self._initialized = True

        # Initialize invocation-scoped resources
        for r in self._resources:
            if r.scope == "invocation":
                instance = await r.factory().__aenter__()
                invocation_context.session.state[f"temp:_resource_{r.name}"] = instance

        return None  # Don't short-circuit

    async def after_run_callback(self, *, invocation_context):
        # Cleanup invocation-scoped resources
        for r in self._resources:
            if r.scope == "invocation":
                instance = invocation_context.session.state.get(f"temp:_resource_{r.name}")
                if instance and hasattr(instance, '__aexit__'):
                    await instance.__aexit__(None, None, None)

    async def close(self):
        # Cleanup app-scoped resources
        for name, instance in self._app_resources.items():
            if hasattr(instance, '__aexit__'):
                await instance.__aexit__(None, None, None)
```

______________________________________________________________________

## 6. Testing Framework — Event-Stream-Aware

### 6.1 MockBackend with Event Streams

```python
class MockBackend:
    """Replaces all LLM calls with deterministic events."""

    def __init__(self, responses: dict[str, str | list[str] | AgentEvent]):
        self._responses = responses

    def compile(self, node: Node) -> MockRunner:
        return MockRunner(node, self._responses)

    async def run(self, compiled, prompt, **kwargs) -> list[AgentEvent]:
        runner = compiled
        events = []
        await runner.execute(prompt, events)
        return events

# Test assertions on the event stream
async def test_classifier_pipeline():
    backend = MockBackend({
        "classifier": AgentEvent(
            author="classifier",
            content="billing",
            state_delta={"intent": "billing", "confidence": 0.94},
            is_final=True,
        ),
        "resolver": AgentEvent(
            author="resolver",
            content="Ticket created",
            state_delta={"ticket_id": "1234"},
            tool_calls=[{"name": "create_ticket", "args": {"issue": "billing"}}],
            is_final=True,
        ),
    })

    events = await pipeline.run("My bill is wrong", backend=backend)

    # Assert on state propagation
    assert events[0].state_delta["intent"] == "billing"

    # Assert on tool usage
    assert events[1].tool_calls[0]["name"] == "create_ticket"

    # Assert on final answer
    assert final_text(events) == "Ticket created"
```

### 6.2 Dry-Run Contract Verification

```python
async def test_pipeline_contracts():
    trace = await dry_run(pipeline)

    # Verify data flow: classifier writes 'intent', resolver reads it
    classifier = trace.node("classifier")
    resolver = trace.node("resolver")

    assert "intent" in classifier.writes_keys
    assert "intent" in resolver.reads_keys

    # Verify type contracts if produces/consumes are declared
    assert classifier.produces_type.is_assignable_to(resolver.consumes_type)
```

______________________________________________________________________

## 7. Migration Path (v3 → v4)

### Phase 1: Seed Generator (non-breaking)

1. Build `codegen/ir_seed.py` that introspects ADK's Pydantic models
1. Generate `_ir_generated.py` with IR node types
1. Validate generated nodes match v3's hand-written nodes
1. Add `_ir_extensions.py` for adk-fluent-only concepts

### Phase 2: Event-Stream Protocol (backward-compatible)

1. Define `AgentEvent` dataclass
1. Update `Backend` protocol to return `list[AgentEvent]`
1. ADK backend maps `Event → AgentEvent`
1. Add `final_text()` convenience for string-only users
1. `.ask()` calls `final_text()` internally — no user-facing change

### Phase 3: Middleware-as-Plugin (backward-compatible)

1. Define `Middleware` protocol aligned with `BasePlugin` callbacks
1. Implement `MiddlewarePlugin` compiler
1. Build `token_budget`, `cost_tracker`, `cache`, `retry` middleware
1. `.use(middleware)` on builders accumulates middleware stack
1. Backend compiles stack into plugin at `App` creation time

### Phase 4: Scope-Aware State Transforms

1. Revise `S.pick()`, `S.drop()` with scope-aware semantics
1. Backend implements `REPLACE_SESSION` and `DELETE_KEYS` via state_delta
1. Add `StateKey("app:setting")` as first-class IR concept

### Phase 5: Seed-Based IR Pipeline

1. Run seed generator on every ADK release
1. Diff generated IR against previous version
1. Auto-generate backend dispatch stubs for new node types
1. Human reviews and adds behavioral code for new capabilities

______________________________________________________________________

## 8. Design Principles (Revised)

### 8.1 The Tide Principle (Unchanged)

> If ADK gets better, adk-fluent gets better for free. If ADK breaks, only the backend adapter needs fixing.

### 8.2 The Seed Principle (New)

> The IR is seeded from ADK's type system, not hand-coded to match it. When ADK adds a new agent type, the seed generator discovers it. When ADK changes a field name, the seed generator catches it. The meta-pattern applies to the IR itself.

### 8.3 The Construct Alignment Principle (New)

> Every adk-fluent abstraction maps to a named ADK construct. An ADK developer should be able to answer "where does this go in my App/Runner/Agent/Plugin?" for every adk-fluent feature. The escape hatch to raw ADK is always available.

### 8.4 The Event-Stream Principle (New)

> The execution model is event-stream-centric with delta-based state. Every node produces events, not results. Every state change is a delta, not a replacement. The Backend protocol speaks events. The IR models the state-flow graph, not just the agent topology.

### 8.5 Progressive Disclosure of Complexity (Unchanged)

```python
# Level 0: One import, one line
result = Agent("helper", "gemini-2.5-flash").instruct("Help.").ask("Hi")

# Level 1: Composition
pipeline = Agent("a") >> Agent("b")

# Level 2: State transforms (scope-aware)
pipeline = Agent("a").outputs("x") >> S.pick("x") >> Agent("b")

# Level 3: Middleware (compiles to ADK Plugin)
agent.use(token_budget(50_000)).use(cost_tracker(bq_sink))

# Level 4: Testing (event-stream assertions)
events = await pipeline.run("test", backend=mock_backend({...}))
assert events[0].state_delta["intent"] == "billing"

# Level 5: Escape hatch to raw ADK
adk_agent = pipeline.compile()  # Native ADK SequentialAgent
```

### 8.6 Zero Surprise Principle (Revised)

- `S.pick("a")` keeps only session-scoped "a" — `app:*` and `user:*` keys are preserved
- Middleware runs before agent callbacks — matches ADK's plugin-first order
- `.compile()` returns a native ADK `BaseAgent` — no wrapper types
- `pipeline.run()` returns `list[AgentEvent]` — full event visibility
- Typos in `Preset` fail at definition time, not runtime

______________________________________________________________________

## 9. Success Criteria (Revised)

1. **The 3-line hello world still works** — produces an ADK-compatible agent
1. **A 100-agent enterprise pipeline** has type-checked contracts, OpenTelemetry traces (via middleware-as-plugin), cost attribution, and event-stream-aware tests
1. **An ADK major version upgrade** requires re-running the seed generator + updating `backends/adk.py` — no user-facing changes
1. **`pip install adk-fluent` → `Agent("x").`** shows \<15 methods in autocomplete
1. **`pipeline.visualize()`** renders the agent graph with state-flow edges and transfer edges
1. **`pytest tests/ -v`** runs 1000+ tests against `MockBackend` with full event assertions in \<10s
1. **Existing ADK developers** can mix adk-fluent agents with raw ADK agents in the same `App`
1. **The IR seed generator** discovers new ADK agent types automatically on each release

______________________________________________________________________

*"The expression graph is the product. ADK is one backend. The seed generator ensures they stay in sync. The plugin system is the compilation target for cross-cutting concerns. The event stream is the execution model."*
