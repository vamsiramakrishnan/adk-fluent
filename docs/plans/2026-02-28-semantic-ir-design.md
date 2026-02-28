# Semantic IR: Framework-Agnostic Intermediate Representation

**Date**: 2026-02-28
**Status**: Design — pending implementation plan
**Goal**: Make adk-fluent resilient to ADK changes, auto-inherit new features, and enable multi-backend portability

## Problem

adk-fluent is tightly coupled to Google ADK at three levels:

1. **Import-time**: ~180 direct ADK class imports across generated builders
1. **Build-time**: `.build()` instantiates ADK classes directly; `__getattr__` validates against ADK Pydantic fields
1. **IR-time**: IR nodes (`AgentNode`, `SequenceNode`) mirror ADK's class hierarchy field-for-field

Any non-trivial ADK change (field rename, class restructure, new agent type) requires manifest rebuild + code regeneration. There's no portability path to other frameworks. The IR is a frozen mirror of ADK, not an abstraction.

## Core Insight

P, C, and S already solved this problem. They're framework-agnostic descriptor algebras:

- **P**: `P.role("x") + P.task("y")` → frozen descriptor tree → compiles to instruction string
- **C**: `C.window(3) + C.user_only()` → frozen descriptor tree → compiles to include_contents
- **S**: `StateSchema` → frozen metadata → compiles to typed state accessors

None import ADK. They describe *intent*. A backend compiles them to *mechanism*. Extend this pattern to everything.

## Five Foundational Decisions

### 1. The IR owns the schema, not ADK

IR nodes use adk-fluent's vocabulary, not ADK's. The backend maps our vocabulary to theirs.

```python
# Current (ADK vocabulary leaks into IR)
AgentNode(include_contents="default", generate_content_config={...})

# Proposed (our vocabulary, backend translates)
SAgentNode(context=C.window(3), generation=GenerationDesc(temperature=0.7))
```

### 2. Escape hatches are typed, not Any

Framework-specific configuration that doesn't have a semantic equivalent uses a typed wrapper:

```python
@dataclass(frozen=True)
class NativeExtension:
    """Framework-specific config. Backends that match target_backend apply extras; others ignore."""
    target_backend: str  # "adk", "langgraph", etc.
    extras: dict[str, Any] = field(default_factory=dict)
```

User surface: `agent.native_ext("adk", disallow_transfer_to_parent=True)`. ADK backend applies it. LangGraph backend ignores it. No silent failures.

### 3. Tools are descriptors with a capability taxonomy

One unified tool descriptor, discriminated by `kind`:

```python
@dataclass(frozen=True)
class ToolDesc:
    kind: ToolKind                    # function | toolset | agent_tool | retrieval | code_exec
    name: str = ""
    description: str = ""
    impl: Callable | None = None     # For function tools
    parameters: type | None = None   # Pydantic model or JSON schema
    provider: str | None = None      # "bigquery", "gmail", "mcp", ... (for toolsets)
    provider_config: dict[str, Any] = field(default_factory=dict)
    agent_ref: SNode | None = None   # Inner agent (for agent-as-tool)
    auth: AuthDesc | None = None

class ToolKind(Enum):
    FUNCTION = "function"
    TOOLSET = "toolset"
    AGENT_TOOL = "agent_tool"
    RETRIEVAL = "retrieval"
    CODE_EXEC = "code_exec"
```

Backends map `ToolDesc(kind=TOOLSET, provider="bigquery", ...)` to their native toolset class. The tool registry is auto-generated from the capability map.

### 4. The scanner becomes a compatibility validator

Today: scanner introspects ADK → generates manifest → generator produces code.

Proposed: scanner introspects ADK → produces a **capability map** → validator checks IR-to-capability alignment → reports gaps.

```python
# Capability map structure
{
    "agents": {
        "LlmAgent": {
            "fields": {"instruction": "str|Callable", "model": "str", ...},
            "removed_since": {},
            "added_since": {"new_field": "1.26.0"},
        }
    },
    "toolsets": {
        "bigquery": {"class": "google.adk.tools.BigQueryToolset", "config_fields": {...}},
    },
    "version_range": {"min": "1.24.0", "max": "1.26.0"},
}
```

`just scan` updates the capability map. `just validate` checks IR coverage. Breaking changes surface as explicit validation errors.

### 5. Builders keep their current API

```python
# Unchanged user code
agent = (
    Agent("reviewer")
    .model("gemini-2.5-flash")
    .instruct(P.role("Senior reviewer.") + P.task("Review code."))
    .tools(review_fn)
    .build()
)
```

What changes underneath: `.build()` becomes `ADKBackend().compile(self.to_ir())`.

## Semantic IR Schema

### Node Types

```python
# Framework-agnostic agent node
@dataclass(frozen=True)
class SAgentNode:
    name: str
    model: str = ""
    prompt: PTransform | str = ""
    context: CTransform | None = None
    tools: tuple[ToolDesc, ...] = ()
    output_schema: type | None = None
    output_key: str | None = None
    generation: GenerationDesc | None = None
    callbacks: CallbackDesc = CallbackDesc()
    children: tuple[SNode, ...] = ()
    native_extensions: tuple[NativeExtension, ...] = ()
    # Dataflow
    writes_keys: frozenset[str] = frozenset()
    reads_keys: frozenset[str] = frozenset()

@dataclass(frozen=True)
class SSequenceNode:
    name: str
    children: tuple[SNode, ...] = ()
    callbacks: CallbackDesc = CallbackDesc()

@dataclass(frozen=True)
class SParallelNode:
    name: str
    children: tuple[SNode, ...] = ()
    callbacks: CallbackDesc = CallbackDesc()

@dataclass(frozen=True)
class SLoopNode:
    name: str
    children: tuple[SNode, ...] = ()
    max_iterations: int | None = None
    callbacks: CallbackDesc = CallbackDesc()
```

Existing primitive nodes (`TransformNode`, `TapNode`, `RouteNode`, `FallbackNode`, `RaceNode`, `GateNode`, `MapOverNode`, `TimeoutNode`, `CaptureNode`, `DispatchNode`, `JoinNode`, `TransferNode`) are already framework-agnostic and remain unchanged.

### Supporting Descriptors

```python
@dataclass(frozen=True)
class GenerationDesc:
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_tokens: int | None = None
    stop_sequences: tuple[str, ...] = ()
    safety_settings: tuple[SafetyDesc, ...] = ()
    extras: dict[str, Any] = field(default_factory=dict)  # Framework-specific

@dataclass(frozen=True)
class CallbackDesc:
    """Lifecycle hooks — framework-agnostic names, backend maps to framework events."""
    before_agent: tuple[Callable, ...] = ()
    after_agent: tuple[Callable, ...] = ()
    before_model: tuple[Callable, ...] = ()
    after_model: tuple[Callable, ...] = ()
    on_model_error: tuple[Callable, ...] = ()
    before_tool: tuple[Callable, ...] = ()
    after_tool: tuple[Callable, ...] = ()
    on_tool_error: tuple[Callable, ...] = ()

@dataclass(frozen=True)
class AuthDesc:
    """Framework-agnostic auth descriptor."""
    scheme: str = ""  # "oauth2", "api_key", "service_account", etc.
    config: dict[str, Any] = field(default_factory=dict)

SNode = (
    SAgentNode | SSequenceNode | SParallelNode | SLoopNode
    | TransformNode | TapNode | FallbackNode | RaceNode
    | GateNode | MapOverNode | TimeoutNode | RouteNode
    | TransferNode | CaptureNode | DispatchNode | JoinNode
)
```

## Backend Protocol

```python
class Backend(Protocol):
    """Compiles semantic IR to framework-specific objects."""

    def compile(self, node: SNode, config: ExecutionConfig | None = None) -> Any: ...

    async def run(self, compiled: Any, prompt: str, **kwargs) -> list[AgentEvent]: ...

    async def stream(self, compiled: Any, prompt: str, **kwargs) -> AsyncIterator[AgentEvent]: ...

    def supports(self, feature: str) -> bool:
        """Check if this backend supports a given feature/toolset provider."""
        ...

    def capability_map(self) -> dict[str, Any]:
        """Return the backend's capability map for validation."""
        ...
```

## ADK Backend Compilation

The ADK backend is the sole owner of all ADK imports. It maps semantic IR to ADK objects:

| Semantic IR                 | ADK Target                                    | Mapping                                                            |
| --------------------------- | --------------------------------------------- | ------------------------------------------------------------------ |
| `SAgentNode`                | `LlmAgent`                                    | prompt→instruction, context→include_contents, tools→compiled tools |
| `SSequenceNode`             | `SequentialAgent`                             | children→sub_agents                                                |
| `SParallelNode`             | `ParallelAgent`                               | children→sub_agents (+ observability hooks)                        |
| `SLoopNode`                 | `LoopAgent`                                   | children→sub_agents, max_iterations                                |
| `ToolDesc(kind=FUNCTION)`   | `FunctionTool(impl)`                          | Direct wrap                                                        |
| `ToolDesc(kind=TOOLSET)`    | Registry lookup → `BigQueryToolset(...)` etc. | Provider→class mapping                                             |
| `ToolDesc(kind=AGENT_TOOL)` | `AgentTool(agent=compiled_child)`             | Recursive compile                                                  |
| `GenerationDesc`            | `GenerateContentConfig(...)`                  | Field mapping + extras merge                                       |
| `CallbackDesc`              | Composed async callbacks                      | Same composition as today                                          |
| `NativeExtension("adk")`    | Merged into constructor kwargs                | Direct pass-through                                                |
| `NativeExtension("other")`  | Ignored                                       | Safe no-op                                                         |

Tool registry auto-generated from capability map:

```python
_TOOLSET_REGISTRY = {
    "bigquery": lambda c: BigQueryToolset(**c),
    "gmail": lambda c: GmailToolset(**c),
    "mcp": lambda c: MCPToolset(**c),
    # ... auto-generated from scan
}
```

## Migration Phases

### Phase 0: Semantic IR types (additive, zero risk)

- Create `src/adk_fluent/_semantic_ir.py` with all new node and descriptor types
- Unit tests: construction, serialization, fingerprinting
- No behavior change

### Phase 1: Dual-path `.to_ir()` (additive, low risk)

- Builders grow `.to_semantic_ir()` alongside `.to_ir()`
- Tool wrapping: detect ADK tool objects → wrap in `ToolDesc`
- ADK-specific fields → `NativeExtension`
- Validation tests: both paths produce equivalent agent graphs

### Phase 2: ADK backend compiles from Semantic IR (medium risk)

- Rewrite `backends/adk.py` to compile `SNode` trees
- Auto-generate tool registry from capability map
- P/C compilation paths unchanged (already work)
- Test: `backend.compile(agent.to_semantic_ir())` matches `agent.build()`

### Phase 3: Cutover — `.build()` routes through Semantic IR (high risk)

- `.build()` becomes `ADKBackend().compile(self.to_ir())`
- Remove `_prepare_build_config()` and `_safe_build()` from `_base.py`
- `.to_ir()` becomes alias for `.to_semantic_ir()`
- Delete old `_ir_generated.py` (AgentNode, SequenceNode, etc.)
- All ~180 ADK imports move from generated builders into `backends/adk.py`

### Phase 4: Scanner as capability validator (low risk)

- Rework scanner to produce capability maps
- `just scan` updates capability map JSON
- `just validate` checks IR↔ADK alignment
- CI gate: validation failure on ADK version bump

### Phase 5: Portability proof (additive)

- `DryRunBackend`: validates IR without framework dependency
- Optional: `LangGraphBackend` stub for topology + tool mapping
- Proves the abstraction works across frameworks

## What This Unlocks

| Capability        | Before                               | After                                                                                |
| ----------------- | ------------------------------------ | ------------------------------------------------------------------------------------ |
| ADK field added   | Manual: scan → regenerate → test     | Automatic: scan validates, builder exposes via `__getattr__`, backend passes through |
| ADK field removed | Silent runtime error                 | Explicit: validator flags incompatibility before deployment                          |
| ADK class renamed | All imports break                    | Backend updates one mapping entry                                                    |
| New ADK toolset   | Manual: add to seed.toml, regenerate | Automatic: scan adds to capability map, registry entry auto-generated                |
| Non-ADK backend   | Impossible                           | Implement `Backend` protocol, map IR nodes to framework                              |
| IR testing        | Requires ADK installed               | `DryRunBackend` validates without any framework                                      |
| Type stubs        | Reference ~180 ADK types             | Reference semantic IR types (framework-agnostic)                                     |

## Non-Goals

- Full parity with every ADK feature on day one. `NativeExtension` covers the long tail.
- Abstracting LLM providers. Model selection stays as a string; model-level abstraction is a separate concern.
- Backward compatibility with the old IR format. Internal IR is not a public API.
