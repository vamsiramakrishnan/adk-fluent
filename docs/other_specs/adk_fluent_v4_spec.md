# ADK-FLUENT: Specification v4 — Comprehensive

**Status:** Supersedes SPEC_v3_findings.md\
**ADK Baseline:** google-adk v1.25.0 (`adk-python` main branch, Feb 2026)\
**Philosophy:** The expression graph is the product. ADK is one backend. The IR evolves with ADK automatically.\
**Architecture:** Expression IR → Backend Protocol → ADK (or anything else)

______________________________________________________________________

## 0. Preamble: What Changed Since v3

v3 was written against an older ADK. Examining ADK v1.25.0 source code reveals structural shifts that change the spec:

| v3 Assumed                                                             | ADK v1.25.0 Reality                                                                                                                                                          |
| ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Three-layer context: `ReadonlyContext → CallbackContext → ToolContext` | **Unified**: `CallbackContext = ToolContext = Context`. Single `Context` class extends `ReadonlyContext`                                                                     |
| Plugin callbacks: ~6 methods                                           | **13 callbacks** including `on_user_message_callback`, `before_run_callback`, `after_run_callback`, `on_event_callback`, `on_model_error_callback`, `on_tool_error_callback` |
| No resumability                                                        | Full `ResumabilityConfig` with agent state checkpointing via `BaseAgentState` and `rewind_async()`                                                                           |
| No event compaction                                                    | `EventsCompactionConfig` with sliding-window summarization and token-threshold triggers                                                                                      |
| `State.__delitem__` missing                                            | **Still missing** — confirms `StateReplacement` needs scope-aware delta emission                                                                                             |
| LlmAgent callback signatures per-field                                 | Callbacks are keyword-only, unified `Context` object passed everywhere                                                                                                       |
| No `tool_confirmation`                                                 | `ToolConfirmation` and `request_confirmation()` on `Context`                                                                                                                 |
| No custom metadata                                                     | `RunConfig.custom_metadata` propagated to events                                                                                                                             |
| No error recovery callbacks                                            | `on_model_error_callback` and `on_tool_error_callback` on both agents and plugins                                                                                            |

These aren't cosmetic — they change how the IR models execution, how middleware compiles, and what the backend adapter must implement.

______________________________________________________________________

## 1. ADK Construct Map for Existing Developers

This section maps every ADK primitive to its adk-fluent equivalent, its IR representation, and the mechanical behavior an existing ADK developer can expect. Each subsection cites the actual ADK source file where the behavior is implemented.

### 1.1 App → Root Expression + ExecutionConfig

**Source:** `src/google/adk/apps/app.py`

**ADK native:**

```python
from google.adk.apps.app import App, ResumabilityConfig, EventsCompactionConfig

app = App(
    name="support",
    root_agent=coordinator,
    plugins=[logging_plugin, analytics_plugin],
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=5, overlap_size=2
    ),
    resumability_config=ResumabilityConfig(is_resumable=True),
)
```

`App` is a Pydantic `BaseModel` with `extra='forbid'`. Its `name` must be a valid Python identifier (enforced by `validate_app_name()`). It holds `root_agent`, `plugins`, `events_compaction_config`, `context_cache_config`, and `resumability_config`.

**adk-fluent v4:**

```python
from adk_fluent import Agent, Pipeline
from adk_fluent.config import ExecutionConfig

pipeline = Agent("classifier") >> Agent("resolver") >> Agent("responder")
config = ExecutionConfig(
    app_name="support",
    resumable=True,
    compaction=CompactionConfig(interval=5, overlap=2),
)

# Get a native App object
app = pipeline.to_app(config)

# Or run directly (creates App + Runner internally)
result = await pipeline.run("My bill is wrong", config=config)
```

**IR mapping:** `ExecutionConfig` attaches to the root IR node at compile time. The ADK backend translates it to `App(name=..., root_agent=compiled, ...)`.

**What existing devs should know:** adk-fluent never hides the App — it generates one. `pipeline.to_app()` returns a native `App` object you can pass to `adk web`. `pipeline.to_runner(session_service=...)` returns a native `Runner`.

### 1.2 Session → Managed by Runner, Exposed via Context

**Source:** `src/google/adk/sessions/session.py`, `src/google/adk/sessions/state.py`

**ADK native:**

```python
session = await session_service.create_session(
    app_name="support", user_id="u1", session_id="s1"
)
# State lives on session.state: dict[str, Any]
# Events accumulate on session.events: list[Event]
```

`Session` is a Pydantic `BaseModel` with fields: `id`, `app_name`, `user_id`, `state: dict[str, Any]`, `events: list[Event]`, `last_update_time: float`. It uses camelCase alias generation for JSON serialization and `extra='forbid'`.

**adk-fluent v4:** Sessions are not modeled in the IR — they are a runtime concern. The backend's `run()` method manages session lifecycle:

```python
result = await pipeline.run(
    "My bill is wrong",
    user_id="u1",
    session_id="s1",
    session_service=SqliteSessionService("sessions.db"),
)
```

For quick prototyping: `InMemorySessionService` is the default. For production: pass any `BaseSessionService` subclass.

### 1.3 Agent → AgentNode (IR) → LlmAgent/BaseAgent (compiled)

**Source:** `src/google/adk/agents/llm_agent.py`, `src/google/adk/agents/base_agent.py`

**ADK native:**

```python
from google.adk.agents import Agent  # alias for LlmAgent

agent = Agent(
    name="classifier",
    model="gemini-2.5-flash",
    instruction="Classify the intent of: {user_query}",
    tools=[classify_tool],
    output_key="intent",
    before_model_callback=my_callback,
    sub_agents=[handler_a, handler_b],
)
```

`LlmAgent` extends `BaseAgent` (Pydantic BaseModel). Key fields: `model`, `instruction` (supports `{state_key}` template substitution), `tools`, `generate_content_config`, `output_schema`, `output_key`, `input_schema`, `include_contents`, `planner`, `code_executor`, and six callback fields (`before_model_callback`, `after_model_callback`, `on_model_error_callback`, `before_tool_callback`, `after_tool_callback`, `on_tool_error_callback`). Each callback field accepts a single callable or a list.

**adk-fluent v4:**

```python
from adk_fluent import Agent

agent = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the intent of: {user_query}")
    .tool(classify_tool)
    .outputs("intent")
    .before_model(my_callback)
    .delegate(handler_a, handler_b)
)
```

**IR produced:**

```python
AgentNode(
    name="classifier",
    model="gemini-2.5-flash",
    instruction="Classify the intent of: {user_query}",
    tools=(classify_tool,),
    output_key="intent",
    callbacks={"before_model": (my_callback,)},
    delegates=("handler_a", "handler_b"),
    writes_keys=frozenset({"intent"}),          # Derived from output_key
    reads_keys=frozenset({"user_query"}),        # Parsed from {template_vars}
)
```

**Mechanical detail — `@final` on `run_async()`:** `BaseAgent.run_async()` is decorated `@final` (line 270 of `base_agent.py`). It implements:

```
create invocation context → trace span → before_agent_callback → _run_async_impl() → after_agent_callback
```

The `_run_async_impl()` is the abstract async generator that subclasses override. This means adk-fluent's custom agents (`_FnAgent`, `_TapAgent` etc.) correctly override `_run_async_impl`, not `run_async`. The ADK backend still creates module-level `BaseAgent` subclasses, parameterized by IR data instead of closures.

**Callback execution order (from source):** For before-callbacks, plugin manager runs first. If no plugin short-circuits, agent-level callbacks run in list order. First non-None return wins and short-circuits the rest. This order is critical for middleware (§5).

### 1.4 Tool → Preserved As-Is (Zero Wrapping)

**Source:** `src/google/adk/tools/function_tool.py`

**ADK mechanics:** `FunctionTool` wraps a Python function. It uses `inspect.signature()` to extract parameters, excludes parameters named `tool_context` (now `Context`) from the LLM schema, and injects them at call time (line 165–166). It also converts dict arguments to Pydantic models when type hints indicate it (`_preprocess_args`), validates mandatory args, and supports both sync and async functions.

**adk-fluent v4:** Tools pass through unchanged. The IR stores tool references; the backend passes them to `LlmAgent(tools=[...])`.

```python
# All of these work directly:
agent = Agent("support").tool(search_tickets)           # Function
agent = Agent("support").tool(MyCustomBaseTool())        # BaseTool subclass
agent = Agent("support").tool(mcp_tool)                  # MCP tool
agent = Agent("support").tool(openapi_toolset)           # OpenAPI toolset
```

**What existing devs should know:** adk-fluent does not wrap, modify, or intercept tools. Your existing tool functions, `BaseTool` subclasses, MCP tools, OpenAPI tools, and toolsets all work directly.

### 1.5 Context → The Unified Runtime Object

**Source:** `src/google/adk/agents/context.py`, `src/google/adk/agents/callback_context.py`, `src/google/adk/tools/tool_context.py`

**ADK v1.25.0 change:** Both `callback_context.py` and `tool_context.py` now contain only:

```python
# callback_context.py
CallbackContext = Context

# tool_context.py
ToolContext = Context
```

The unified `Context` class extends `ReadonlyContext` and provides:

```
ReadonlyContext
  ├── invocation_id, agent_name, user_id, user_content
  ├── state (read-only MappingProxyType)
  ├── session, run_config
  └─ Context
      ├── state (mutable State proxy with delta tracking)
      ├── actions (EventActions)
      ├── function_call_id, tool_confirmation
      ├── Artifacts: save_artifact, load_artifact, list_artifacts, get_artifact_version
      ├── Credentials: save_credential, load_credential, request_credential, get_auth_response
      ├── Memory: search_memory, add_session_to_memory, add_events_to_memory, add_memory
      └── Tools: request_confirmation
```

**Impact on adk-fluent middleware:** Middleware receives `Context` objects uniformly. No need to discriminate between "callback context" and "tool context."

### 1.6 State → Delta-Tracked Dict with Scope Prefixes

**Source:** `src/google/adk/sessions/state.py` (82 lines total)

**ADK mechanics:**

```python
class State:
    APP_PREFIX = "app:"    # Shared across all users/sessions for this app
    USER_PREFIX = "user:"  # Shared across sessions for one user
    TEMP_PREFIX = "temp:"  # Ephemeral, never persisted
    # No prefix = session-scoped

    def __setitem__(self, key, value):
        self._value[key] = value   # Immediate visibility
        self._delta[key] = value   # Tracked for persistence

    def __getitem__(self, key):
        if key in self._delta:
            return self._delta[key]
        return self._value[key]
```

**Critical observations from source:**

1. **No `__delitem__`** — keys can be set to `None` but never removed
1. **No `__iter__`** or `keys()` — you must use `to_dict()` to enumerate
1. `__contains__` checks both `_value` and `_delta`
1. The `_delta` dict is the same object as `EventActions.state_delta` — writes to state are immediately reflected in the event actions

### 1.7 Events → The Execution Atom

**Source:** `src/google/adk/events/event.py`, `src/google/adk/events/event_actions.py`

`EventActions` carries the full side-effect vocabulary:

- `state_delta: dict[str, object]`
- `artifact_delta: dict[str, int]`
- `transfer_to_agent: Optional[str]`
- `escalate: Optional[bool]`
- `end_of_agent: Optional[bool]`
- `agent_state: Optional[dict[str, Any]]` — for resumability checkpoints
- `requested_auth_configs: dict[str, AuthConfig]`
- `requested_tool_confirmations: dict[str, ToolConfirmation]`
- `compaction: Optional[EventCompaction]`
- `rewind_before_invocation_id: Optional[str]`
- `skip_summarization: Optional[bool]`

### 1.8 Runner → The Orchestration Engine

**Source:** `src/google/adk/runners.py` (1551 lines)

`Runner.__init__` accepts: `app` (or `app_name` + `agent`), `session_service`, `artifact_service`, `memory_service`, `credential_service`, `auto_create_session`.

`Runner.run_async()` flow:

1. Get or create session
1. Append user message
1. Create `InvocationContext` with all services
1. Wrap in OTel trace span
1. Execute via `agent.run_async(ctx)` — yields events
1. For each non-partial event: persist via `session_service.append_event()`
1. Yield events to caller
1. Run event compaction if configured

**New in v1.25.0:** `Runner.rewind_async()` reverses state/artifact deltas to before a specified invocation.

### 1.9 Plugin System → The Extension Mechanism

**Source:** `src/google/adk/plugins/base_plugin.py`, `src/google/adk/plugins/plugin_manager.py`

`BasePlugin` now has 13 callback methods:

| Callback                   | When                  | Short-Circuit Behavior                 |
| -------------------------- | --------------------- | -------------------------------------- |
| `on_user_message_callback` | User message received | Return Content → replaces message      |
| `before_run_callback`      | Before runner starts  | Return Content → halts execution       |
| `on_event_callback`        | After event yielded   | Return Event → replaces event          |
| `after_run_callback`       | After runner finishes | No short-circuit (returns None)        |
| `before_agent_callback`    | Before agent runs     | Return Content → skips agent           |
| `after_agent_callback`     | After agent runs      | Return Content → appends as response   |
| `before_model_callback`    | Before LLM call       | Return LlmResponse → skips LLM         |
| `after_model_callback`     | After LLM response    | Return LlmResponse → replaces response |
| `on_model_error_callback`  | LLM call failed       | Return LlmResponse → replaces error    |
| `before_tool_callback`     | Before tool call      | Return dict → skips tool               |
| `after_tool_callback`      | After tool result     | Return dict → replaces result          |
| `on_tool_error_callback`   | Tool call failed      | Return dict → replaces error           |
| `close`                    | Runner shutdown       | Cleanup                                |

`PluginManager` executes plugins in registration order with early-exit on non-None returns. Plugins run **before** agent-level callbacks.

______________________________________________________________________

## 2. Updated Disfluencies (v3 + New Findings from v1.25.0)

### 2.1–2.11 [Retained from v3]

All eleven disfluencies from v3 §1 remain valid and are incorporated by reference. The proposed fixes are unchanged. Summary:

1. `__getattr__` pandemic (132 copies) → `BuilderBase` with `_ADK_TARGET_CLASS`
1. State transforms broken → `StateDelta` vs `StateReplacement` (revised below in §6)
1. Inner classes in `build()` → module-level agents
1. Callback merging fragile → compose into single callable
1. Full state copy per function step → read-only view for taps
1. `__init__.py` exports 136 symbols → tiered imports
1. `@agent` decorator monkey-patches → `AgentDecorator` wrapper
1. No "Not Set" vs "Set to None" distinction → `_UNSET` sentinel
1. Generated mega-files → split by logical group
1. `Preset` has no validation → validate against known fields
1. `_clone_shallow` vs `clone()` naming → `_fork_for_operator` vs `clone()`

### 2.12 Context Unification Not Reflected (NEW)

**Finding:** v3 middleware protocol has separate method signatures assuming different context types (`CallbackContext`, `ToolContext`). ADK v1.25.0 unified both into `Context`. The middleware protocol must accept `Context` uniformly.

### 2.13 Missing Error Callbacks (NEW)

**Finding:** ADK v1.25.0 added `on_model_error_callback` and `on_tool_error_callback` to both `BasePlugin` and `LlmAgent`. These enable retry, circuit-breaker, and error-rate monitoring without ad-hoc exception handling. The middleware protocol must include these.

### 2.14 No Awareness of Resumability (NEW)

**Finding:** ADK's `ResumabilityConfig` enables pause/resume. `SequentialAgent` saves `SequentialAgentState(current_sub_agent=...)` via `_create_agent_state_event()` on each step. The IR has no concept of checkpoint boundaries.

**Fix:** `ExecutionConfig.resumable = True` passes through to `App.resumability_config`. The ADK backend handles agent state events automatically since `BaseAgent.run_async()` is `@final`.

### 2.15 Event Compaction Invisible (NEW)

**Finding:** `EventsCompactionConfig` with `compaction_interval`, `overlap_size`, `token_threshold`, `event_retention_size` — all invisible to adk-fluent users.

**Fix:** `ExecutionConfig.compaction = CompactionConfig(...)` passes through to `App.events_compaction_config`.

### 2.16 No Rewind Support (NEW)

**Finding:** `Runner.rewind_async()` can rewind to before a specific invocation.

**Fix:** Expose on the pipeline: `await pipeline.rewind(session_id=..., before_invocation_id=...)`.

### 2.17 ToolConfirmation Flow Missing (NEW)

**Finding:** `Context.request_confirmation()` enables human-in-the-loop tool approval. `FunctionTool` supports `require_confirmation`.

**Fix:** Builder method `.tool(my_fn, require_confirmation=True)` passes through to `FunctionTool(func=my_fn, require_confirmation=True)`. Also expose `tool_approval` middleware.

______________________________________________________________________

## 3. The Intermediate Representation (IR) — v4

### 3.1 Design Change: Seed-Based IR Evolution

**The meta-pattern continued:** Instead of hand-coding IR node types, v4 generates them from ADK's own Pydantic model definitions. ADK's agent classes are all Pydantic `BaseModel`s with typed fields. The IR generator:

1. **Scans** ADK's agent model fields via `LlmAgent.model_fields`, `SequentialAgent.model_fields`, etc.
1. **Extracts** field names, types, and defaults
1. **Generates** frozen dataclass IR nodes that mirror the field set
1. **Adds** adk-fluent extensions (`writes_keys`, `reads_keys`, `produces_type`, `consumes_type`)
1. **Re-runs** whenever ADK is updated, producing a diff report

```python
# _codegen/ir_generator.py — the seed-based IR codegen
import inspect
from dataclasses import dataclass, field
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.parallel_agent import ParallelAgent

# Map of IR node name → ADK source class
AGENT_CLASSES = {
    "AgentNode": LlmAgent,
    "SequenceNode": SequentialAgent,
    "LoopNode": LoopAgent,
    "ParallelNode": ParallelAgent,
}

# Fields to skip (internal ADK machinery)
SKIP_FIELDS = {"parent_agent", "model_config", "config_type"}

# Fields to rename for IR clarity
RENAMES = {"sub_agents": "children"}

def scan_adk_fields(adk_class: type) -> dict[str, FieldInfo]:
    """Extract public fields from an ADK Pydantic model."""
    return {
        RENAMES.get(name, name): info
        for name, info in adk_class.model_fields.items()
        if name not in SKIP_FIELDS
    }

def generate_ir_module(output_path: str):
    """Generate _ir_generated.py from current ADK installation."""
    lines = [
        '"""Auto-generated IR nodes from ADK model introspection."""',
        '# ADK version: ' + get_adk_version(),
        'from dataclasses import dataclass, field',
        'from typing import Any, Callable, Literal',
        '',
    ]
    for node_name, adk_class in AGENT_CLASSES.items():
        fields = scan_adk_fields(adk_class)
        lines.append(generate_node_class(node_name, fields))
    
    write_file(output_path, '\n'.join(lines))
```

**Why seed-based:** When ADK v1.26.0 adds a new field to `LlmAgent` (e.g., `context_cache_config`, a new callback type), the IR generator picks it up automatically. When ADK adds a new agent type (e.g., `ConditionalAgent`), we add one entry to `AGENT_CLASSES`. The hand-coded IR from v3 §2 becomes a generated artifact.

### 3.2 IR Node Types

**Generated from ADK models** (produced by `ir_generator.py`):

- `AgentNode` — from `LlmAgent`
- `SequenceNode` — from `SequentialAgent`
- `ParallelNode` — from `ParallelAgent`
- `LoopNode` — from `LoopAgent`

Each generated node includes all ADK fields as frozen attributes, plus adk-fluent extensions:

```python
    # adk-fluent extensions (hand-written, appended by generator)
    writes_keys: frozenset[str] = frozenset()
    reads_keys: frozenset[str] = frozenset()
    produces_type: type | None = None
    consumes_type: type | None = None
```

**Hand-written (adk-fluent primitives with no ADK counterpart):**

```python
@dataclass(frozen=True)
class TransformNode:
    name: str
    fn: Callable
    semantics: Literal["merge", "replace_session", "delete_keys"] = "merge"
    scope: Literal["session", "all"] = "session"
    affected_keys: frozenset[str] | None = None

@dataclass(frozen=True)
class RouteNode:
    name: str
    key: str | None = None
    rules: tuple[tuple[Callable, 'Node'], ...] = ()
    default: 'Node | None' = None

@dataclass(frozen=True)
class FallbackNode:
    name: str
    children: tuple['Node', ...] = ()

@dataclass(frozen=True)
class RaceNode:
    name: str
    children: tuple['Node', ...] = ()

@dataclass(frozen=True)
class GateNode:
    name: str
    predicate: Callable
    message: str = "Approval required"

@dataclass(frozen=True)
class TapNode:
    name: str
    fn: Callable

@dataclass(frozen=True)
class MapOverNode:
    name: str
    list_key: str
    body: 'Node'
    item_key: str = "_item"
    output_key: str = "results"

@dataclass(frozen=True)
class TimeoutNode:
    name: str
    body: 'Node'
    seconds: float

@dataclass(frozen=True)
class TransferNode:
    """Represents a hard agent transfer (ADK's transfer_to_agent)."""
    name: str
    target: str
    condition: Callable | None = None
```

### 3.3 ExecutionConfig

```python
@dataclass(frozen=True)
class ExecutionConfig:
    app_name: str = "adk_fluent_app"
    max_llm_calls: int = 500
    timeout_seconds: float | None = None
    streaming_mode: Literal["none", "sse", "bidi"] = "none"
    resumable: bool = False
    compaction: CompactionConfig | None = None
    custom_metadata: dict[str, Any] | None = None

@dataclass(frozen=True)
class CompactionConfig:
    interval: int = 10
    overlap: int = 2
    token_threshold: int | None = None
    event_retention_size: int | None = None
```

### 3.4 Data-Flow Edges

Auto-populated by the builder:

```python
import re

def _extract_template_vars(instruction: str | Callable | None) -> frozenset[str]:
    if not isinstance(instruction, str):
        return frozenset()
    return frozenset(re.findall(r'\{(\w+)\}', instruction))

def _extract_output_keys(output_key: str | None, output_schema: type | None) -> frozenset[str]:
    keys = set()
    if output_key:
        keys.add(output_key)
    if output_schema and hasattr(output_schema, 'model_fields'):
        keys.update(output_schema.model_fields.keys())
    return frozenset(keys)
```

The `VizBackend` draws data-flow edges. The contract checker verifies reads-after-writes ordering (§9).

### 3.5 Tracking ADK Changes (Diff Report)

```python
def generate_and_diff(adk_version: str) -> DiffReport:
    """Generate IR and compare against previous version."""
    current_fields = scan_all_adk_fields()
    previous_fields = load_previous_scan()

    added = current_fields - previous_fields
    removed = previous_fields - current_fields
    changed = {f for f in current_fields & previous_fields
               if current_fields[f].type != previous_fields[f].type}

    report = DiffReport(
        adk_version=adk_version,
        added=added,       # Safe to auto-merge
        removed=removed,   # BREAKING — requires human review
        changed=changed,   # BREAKING — requires human review
    )
    report.save(f"ir_diff_{adk_version}.json")
    return report
```

**Auto-merge rule:** Only `added` fields → regenerate and merge. Any `removed` or `changed` → flag for human review, generate migration notes.

______________________________________________________________________

## 4. The Backend Protocol — v4

### 4.1 AgentEvent: Backend-Agnostic Event

```python
@dataclass
class AgentEvent:
    """Backend-agnostic representation of an ADK Event."""
    author: str
    content: str | None = None
    state_delta: dict[str, Any] = field(default_factory=dict)
    artifact_delta: dict[str, int] = field(default_factory=dict)
    transfer_to: str | None = None
    escalate: bool = False
    tool_calls: list[ToolCallInfo] = field(default_factory=list)
    tool_responses: list[ToolResponseInfo] = field(default_factory=list)
    is_final: bool = False
    is_partial: bool = False
    end_of_agent: bool = False
    agent_state: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

@dataclass
class ToolCallInfo:
    tool_name: str
    args: dict[str, Any]
    call_id: str

@dataclass
class ToolResponseInfo:
    tool_name: str
    result: Any
    call_id: str
```

### 4.2 Protocol Definition

```python
@runtime_checkable
class Backend(Protocol):
    def compile(self, node: Node, config: ExecutionConfig | None = None) -> Any:
        """Transform IR node tree into a backend-specific runnable."""
        ...

    async def run(self, compiled: Any, prompt: str, **kwargs) -> list[AgentEvent]:
        """Execute and return all events."""
        ...

    async def stream(self, compiled: Any, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]:
        """Stream events as they occur."""
        ...
```

**Convenience utility:**

```python
def final_text(events: list[AgentEvent]) -> str:
    """Extract the final response text from an event list."""
    for event in reversed(events):
        if event.is_final and event.content:
            return event.content
    return ""
```

### 4.3 ADK Backend

The ADK backend compiles IR → native ADK objects and manages Runner lifecycle. The compile method for ADK agent types is **partially generated** by `backend_generator.py` (which reads the IR node definitions and emits match cases), while compile methods for adk-fluent-only node types (Transform, Route, Tap, etc.) are hand-written.

```python
class ADKBackend:
    def __init__(
        self,
        session_service: BaseSessionService | None = None,
        artifact_service: BaseArtifactService | None = None,
        memory_service: BaseMemoryService | None = None,
        credential_service: BaseCredentialService | None = None,
    ):
        self._session_service = session_service or InMemorySessionService()
        self._artifact_service = artifact_service
        self._memory_service = memory_service
        self._credential_service = credential_service

    def compile(self, node: Node, config: ExecutionConfig | None = None) -> App:
        config = config or ExecutionConfig()
        root_agent = self._compile_node(node)
        plugins = self._compile_middleware_stack(node)

        return App(
            name=config.app_name,
            root_agent=root_agent,
            plugins=plugins,
            resumability_config=(
                ResumabilityConfig(is_resumable=True) if config.resumable else None
            ),
            events_compaction_config=(
                self._to_compaction_config(config.compaction)
                if config.compaction else None
            ),
        )

    async def run(self, compiled: App, prompt: str, **kwargs) -> list[AgentEvent]:
        runner = Runner(
            app=compiled,
            session_service=self._session_service,
            artifact_service=self._artifact_service,
            memory_service=self._memory_service,
            credential_service=self._credential_service,
        )
        user_id = kwargs.get("user_id", "default_user")
        session_id = kwargs.get("session_id", "default_session")

        events = []
        async for adk_event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user", parts=[types.Part.from_text(prompt)]
            ),
            run_config=RunConfig(max_llm_calls=kwargs.get("max_llm_calls", 500)),
        ):
            events.append(self._to_agent_event(adk_event))
        return events

    def _to_agent_event(self, event: Event) -> AgentEvent:
        """Convert an ADK Event to a backend-agnostic AgentEvent."""
        return AgentEvent(
            author=event.author,
            content=self._extract_text(event.content),
            state_delta=dict(event.actions.state_delta) if event.actions else {},
            artifact_delta=dict(event.actions.artifact_delta) if event.actions else {},
            transfer_to=event.actions.transfer_to_agent if event.actions else None,
            escalate=bool(event.actions.escalate) if event.actions else False,
            is_final=event.is_final_response(),
            is_partial=bool(event.partial),
            end_of_agent=bool(event.actions.end_of_agent) if event.actions else False,
            tool_calls=[...],  # Extract from event.get_function_calls()
            timestamp=event.timestamp,
        )
```

### 4.4 Mock Backend

```python
class MockBackend:
    def __init__(self, responses: dict[str, str | dict]):
        self._responses = responses

    def compile(self, node: Node, config=None) -> Any:
        return MockRunner(node, self._responses)

    async def run(self, compiled, prompt, **kwargs) -> list[AgentEvent]:
        return await compiled.execute(prompt)
```

### 4.5 Viz Backend

```python
class VizBackend:
    def compile(self, node: Node, config=None) -> str:
        return self._to_mermaid(node)

    def _to_mermaid(self, node: Node, depth=0) -> str:
        match node:
            case SequenceNode():
                # Emit sequential flow with data-flow edge annotations
                ...
            case ParallelNode():
                # Emit parallel fork/join
                ...
            case AgentNode():
                # Emit node with writes_keys/reads_keys annotations
                ...
```

______________________________________________________________________

## 5. Middleware Protocol — v4

### 5.1 Aligned with ADK v1.25.0 Plugin Signatures

The middleware protocol mirrors `BasePlugin`'s 13 callbacks. Each method is optional (default implementation returns None / does nothing).

```python
class Middleware(Protocol):
    """A composable unit of cross-cutting behavior."""

    # Runner lifecycle
    async def on_user_message(self, ctx: Context, message: Any) -> Any | None: ...
    async def before_run(self, ctx: Context) -> Any | None: ...
    async def after_run(self, ctx: Context) -> None: ...
    async def on_event(self, ctx: Context, event: AgentEvent) -> AgentEvent | None: ...

    # Agent lifecycle
    async def before_agent(self, ctx: Context, agent_name: str) -> Any | None: ...
    async def after_agent(self, ctx: Context, agent_name: str) -> Any | None: ...

    # Model lifecycle
    async def before_model(self, ctx: Context, request: Any) -> Any | None: ...
    async def after_model(self, ctx: Context, response: Any) -> Any | None: ...
    async def on_model_error(self, ctx: Context, request: Any, error: Exception) -> Any | None: ...

    # Tool lifecycle
    async def before_tool(self, ctx: Context, tool_name: str, args: dict) -> dict | None: ...
    async def after_tool(self, ctx: Context, tool_name: str, args: dict, result: dict) -> dict | None: ...
    async def on_tool_error(self, ctx: Context, tool_name: str, args: dict, error: Exception) -> dict | None: ...
```

### 5.2 Compilation to ADK Plugin

```python
class _MiddlewarePlugin(BasePlugin):
    """Compiles a middleware stack into a single ADK-compatible plugin.

    ADK execution order: plugins first → agent callbacks second.
    This ensures middleware has priority over user-defined callbacks.
    """

    def __init__(self, name: str, stack: list[Middleware]):
        super().__init__(name=name)
        self._stack = stack

    async def before_model_callback(self, *, callback_context, llm_request):
        for mw in self._stack:
            if hasattr(mw, 'before_model') and mw.before_model is not None:
                result = await mw.before_model(callback_context, llm_request)
                if result is not None:
                    return result  # Short-circuit
        return None

    async def on_model_error_callback(self, *, callback_context, llm_request, error):
        for mw in self._stack:
            if hasattr(mw, 'on_model_error') and mw.on_model_error is not None:
                result = await mw.on_model_error(callback_context, llm_request, error)
                if result is not None:
                    return result  # Short-circuit (provides fallback response)
        return None  # Let error propagate

    # ... same pattern for all 13 callbacks
```

### 5.3 Built-In Middleware

```python
from adk_fluent.middleware import (
    # Model-layer
    token_budget,       # Enforces token limits (before_model + after_model)
    cost_tracker,       # Accumulates cost (after_model)
    cache,              # Response caching (before_model → return cached, after_model → store)
    rate_limiter,       # Token bucket (before_model)

    # Error-layer
    retry,              # Exponential backoff (on_model_error, on_tool_error)
    circuit_breaker,    # Fail-fast (on_model_error, on_tool_error, before_model)

    # Tool-layer
    tool_approval,      # Human-in-the-loop (before_tool → request_confirmation)

    # Observability
    structured_log,     # JSON logs (all lifecycle hooks)
    pii_filter,         # Redact PII (before_model, after_tool)
)

# Example: retry middleware uses the error callbacks
class RetryMiddleware:
    def __init__(self, max_attempts=3, backoff_base=1.0):
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self._attempt_counts: dict[str, int] = {}

    async def on_model_error(self, ctx, request, error):
        key = ctx.agent_name
        self._attempt_counts[key] = self._attempt_counts.get(key, 0) + 1
        if self._attempt_counts[key] < self.max_attempts:
            delay = self.backoff_base * (2 ** self._attempt_counts[key])
            await asyncio.sleep(delay)
            return None  # Let ADK retry (don't short-circuit)
        return None  # Exhausted retries, let error propagate

    async def on_tool_error(self, ctx, tool_name, args, error):
        # Similar retry logic for tools
        ...
```

______________________________________________________________________

## 6. State Transform Semantics — v4

### 6.1 The Problem (Confirmed by v1.25.0 Source)

`State.__setitem__` writes to both `_value` and `_delta`. There is no `__delitem__`. The `_delta` dict is the same object as `EventActions.state_delta`. When `session_service.append_event()` persists the event, only `state_delta` entries are applied — there is no "delete" operation.

Scope prefixes route deltas: `app:` → app storage, `user:` → user storage, `temp:` → ephemeral, no prefix → session storage.

### 6.2 Scope-Aware Transform Semantics

```python
@dataclass(frozen=True)
class TransformNode:
    name: str
    fn: Callable
    semantics: Literal["merge", "replace_session", "delete_keys"] = "merge"
    scope: Literal["session", "all"] = "session"
    affected_keys: frozenset[str] | None = None
```

| Transform             | Semantics               | Behavior                                    |
| --------------------- | ----------------------- | ------------------------------------------- |
| `S.set(k=v)`          | `merge`                 | Additive write to state                     |
| `S.default(k=v)`      | `merge`                 | Write only if key absent                    |
| `S.merge(...)`        | `merge`                 | Merge multiple keys                         |
| `S.pick("a", "b")`    | `replace_session`       | Set all other session-scoped keys to `None` |
| `S.drop("x", "y")`    | `delete_keys`           | Set named session-scoped keys to `None`     |
| `S.rename(old="new")` | `merge` + `delete_keys` | Set `new=old_value`, set `old=None`         |

**Implementation in `_FnAgent`:**

```python
if self._mode == "replace_session":
    current = context.state.to_dict()
    result = self._fn(current)
    # Set all session-scoped keys not in result to None
    for key in current:
        if not key.startswith(("app:", "user:", "temp:")) and key not in result:
            context.state[key] = None
    # Write result keys
    for k, v in result.items():
        context.state[k] = v
elif self._mode == "delete_keys":
    for key in self._affected_keys:
        if not key.startswith(("app:", "user:", "temp:")):
            context.state[key] = None
```

______________________________________________________________________

## 7. Inter-Agent Contracts

### 7.1 `produces()` / `consumes()`

```python
from pydantic import BaseModel

class Intent(BaseModel):
    category: str
    confidence: float

pipeline = (
    Agent("classifier").produces(Intent)
    >> Agent("resolver").consumes(Intent).produces(Resolution)
)
```

At `build()` time, the builder populates `writes_keys` from the `produces` schema's fields and `reads_keys` from the `consumes` schema's fields. At `compile()` time, the contract checker (`check_contracts()`) verifies that step N's `writes_keys` satisfies step N+1's `reads_keys`.

### 7.2 Backward Compatibility

Both methods are optional. Untyped agents interoperate freely. The contract is only checked when both sides declare types.

______________________________________________________________________

## 8. Dependency Injection

### 8.1 Closure Injection with Signature Manipulation

```python
def _inject_resources(fn: Callable, resources: dict[str, Any]) -> Callable:
    """Wraps a tool function with resource injection.
    Modifies __signature__ so FunctionTool excludes resource params from LLM schema.
    """
    sig = inspect.signature(fn)
    resource_params = {
        name for name in sig.parameters
        if name in resources and name not in ('tool_context',)
    }

    @functools.wraps(fn)
    async def wrapped(**kwargs):
        kwargs.update({k: resources[k] for k in resource_params if k not in kwargs})
        if inspect.iscoroutinefunction(fn):
            return await fn(**kwargs)
        return fn(**kwargs)

    new_params = [p for name, p in sig.parameters.items() if name not in resource_params]
    wrapped.__signature__ = sig.replace(parameters=new_params)
    return wrapped
```

### 8.2 Resource Lifecycle Mapping to ADK

| Resource Scope | ADK Lifecycle Hook                             | Implementation                                                 |
| -------------- | ---------------------------------------------- | -------------------------------------------------------------- |
| `"app"`        | `ADKBackend.compile()`                         | Created once, stored on backend instance                       |
| `"session"`    | `before_run_callback` plugin                   | Created per session, stored in `state["app:_resource_{name}"]` |
| `"invocation"` | `before_agent_callback` / `after_run_callback` | Created/destroyed per invocation                               |

______________________________________________________________________

## 9. Testing Framework

```python
from adk_fluent.testing import mock_backend, check_contracts, AgentHarness

# 1. Mock backend — deterministic, no LLM
async def test_pipeline():
    backend = mock_backend({
        "classifier": {"intent": "billing"},
        "resolver": "Ticket #1234 created.",
    })
    events = await pipeline.run("My bill is wrong", backend=backend)
    assert any(e.is_final and "1234" in e.content for e in events)

# 2. Contract verification — no execution needed
def test_contracts():
    issues = check_contracts(pipeline.build())
    assert not issues

# 3. Event stream assertions
async def test_state_flow():
    events = await pipeline.run("test", backend=mock_backend({...}))
    classifier_events = [e for e in events if e.author == "classifier"]
    assert classifier_events[0].state_delta.get("intent") is not None

# 4. Harness with fixtures
async def test_with_harness():
    harness = AgentHarness(pipeline, backend=mock_backend({...}))
    response = await harness.send("Hi")
    assert response.final_text
    assert not response.errors
```

______________________________________________________________________

## 10. Module Architecture

```
adk_fluent/
  __init__.py              # Layer 0: Agent, Pipeline, FanOut, Loop, S, Route

  # Core (hand-written)
  _ir.py                   # Hand-written IR (TransformNode, RouteNode, etc.)
  _base.py                 # BuilderBase
  _operators.py            # >>, |, *, //, @
  _transforms.py           # S transform factories
  _routing.py              # Route builder
  _helpers.py              # StateKey, Artifact
  _presets.py              # Preset class

  # Backends
  backends/
    _protocol.py           # Backend protocol + AgentEvent
    adk.py                 # ADK backend (hand-written structure + generated compile cases)
    mock.py                # Mock backend
    trace.py               # Tracing backend
    viz.py                 # Visualization backend
    dry_run.py             # Contract verification

  # Middleware
  middleware/
    _protocol.py           # Aligned with ADK v1.25.0 BasePlugin (13 callbacks)
    _plugin_adapter.py     # _MiddlewarePlugin: stack → ADK plugin
    token_budget.py
    cost_tracker.py
    cache.py
    retry.py               # Uses on_model_error / on_tool_error
    circuit_breaker.py
    tool_approval.py       # ToolConfirmation integration
    structured_log.py
    pii_filter.py

  # Testing
  testing/
    mock_backend.py
    contracts.py           # writes_keys / reads_keys verification
    harness.py
    pytest_plugin.py

  # Generated (auto-updated by codegen pipeline)
  generated/
    _ir_nodes.py           # IR dataclasses from ADK model introspection
    _builders.py           # Builder classes from ADK model fields
    _adk_compile.py        # Backend compile cases

  # Codegen tools (development only, not shipped)
  _codegen/
    ir_generator.py
    builder_generator.py
    backend_generator.py
    diff_report.py
```

______________________________________________________________________

## 11. Migration Path

### Phase 1: Fix Disfluencies (non-breaking)

All 11 v3 fixes + update for unified `Context`.

### Phase 2: Seed-Based IR

1. Build `ir_generator.py`
1. Generate IR nodes from ADK v1.25.0 models
1. Change `.build()` to return IR
1. Implement ADK backend with generated + hand-written compile
1. Auto-compile in `.ask()`, `.stream()`, `.run()`

### Phase 3: Middleware

1. Protocol aligned with all 13 ADK plugin callbacks
1. `_MiddlewarePlugin` adapter
1. Built-in middleware (retry with error callbacks, circuit breaker, etc.)

### Phase 4: New Capabilities

1. `produces()` / `consumes()` + `check_contracts()`
1. Resource DI with closure injection
1. Event-based testing with `AgentEvent`
1. Graph visualization with data-flow edges
1. ExecutionConfig pass-through (resumability, compaction)
1. ToolConfirmation support
1. Rewind API

______________________________________________________________________

## 12. Design Principles

### 12.1 The Tide Principle

> If ADK gets better, adk-fluent gets better for free. If ADK breaks, only the backend adapter needs fixing.

The seed-based IR generator is the mechanical embodiment. When ADK adds a field, the generator picks it up. When ADK removes one, the diff report flags it.

### 12.2 Progressive Disclosure

Each level introduces new imports from deeper submodules. The top-level namespace stays clean.

### 12.3 Zero Surprise

- `S.pick("a")` keeps only "a" among session-scoped keys
- Middleware compiles to ADK plugins (respects plugin-first order)
- `Context` is the same object everywhere
- Error callbacks exist and work

### 12.4 ADK Developer Familiarity

- `pipeline.to_app()` → native `App`
- `pipeline.to_runner()` → native `Runner`
- Tools pass through unchanged
- State scope prefixes respected

______________________________________________________________________

## 13. Success Criteria

1. **3-line hello world** produces an ADK-compatible `App`
1. **100-agent pipeline** has type-checked contracts, OTel traces, cost attribution, deterministic tests
1. **ADK version upgrade** requires: run `ir_generator.py`, review diff, update backend if breaking
1. **Existing ADK devs** can adopt incrementally: `to_app()`, `to_runner()` return familiar objects
1. **Middleware → ADK plugin** compilation with correct execution order
1. **1000+ tests, zero LLM calls, \<10 seconds**
1. **`pipeline.visualize()`** renders agent graph with data-flow edges

______________________________________________________________________

*"The goal is not to hide ADK. The goal is to express intent in a form that ADK — or whatever comes next — can execute. The IR evolves with ADK because it grows from ADK's own seeds."*
