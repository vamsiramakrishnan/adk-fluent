# Namespace Expansion Design — G + T/M/S Fattening

**Date:** 2026-03-10
**Status:** Approved
**Scope:** Big-bang release — all changes ship together

___

## Design Principle

Each namespace answers exactly one question:

| Namespace | Question | Removal test |
| --- | --- | --- |
| **T** | What can this agent *do*? | Loses capability |
| **M** | How does this agent *stay healthy*? | Loses resilience |
| **G** | What must this agent *never* do? | Loses safety |
| **S** | How does data *flow*? | Loses state |
| **C** | What does this agent *see*? | Loses context |
| **P** | Who *is* this agent? | Loses personality |
| **A** | What does this agent *persist*? | Loses memory |
| **E** | How do I *measure* this agent? | Loses evaluation |

___

## 1. G Namespace — Guards (New Module)

**File:** `src/adk_fluent/_guards.py`
**Exports:** `G`, `GComposite`, `GGuard`, `GuardViolation`, `PIIDetector`, `ContentJudge`, `PIIFinding`, `JudgmentResult`
**Operator:** `|` (chain — all guards run, first failure aborts)
**Builder method:** `.guard(G.xxx() | G.yyy())`

### 1.1 API Surface

```python
from adk_fluent import G

# -- Content Safety --
G.pii(action="redact"|"block", detector=None, threshold=0.7, replacement="[{kind}]")
G.toxicity(threshold=0.8, judge=None)
G.topic(deny=["politics", "religion"])
G.regex(pattern, action="block"|"redact", replacement="[REDACTED]")

# -- Structural Validation --
G.output(schema_cls)
G.input(schema_cls)
G.json()
G.length(min=None, max=None)

# -- Cost & Rate Policy --
G.budget(max_tokens=5000)
G.rate_limit(rpm=60)
G.max_turns(n=10)

# -- Grounding --
G.grounded(sources_key="docs")
G.hallucination(threshold=0.7, sources_key="docs", judge=None)

# -- Composition --
G.when(predicate, guard)
```

### 1.2 Provider Protocols

Guards that perform detection or judgment delegate to pluggable providers.

#### PIIDetector Protocol

```python
class PIIDetector(Protocol):
    async def detect(self, text: str) -> list[PIIFinding]: ...

@dataclass(frozen=True)
class PIIFinding:
    kind: str           # "SSN", "EMAIL_ADDRESS", etc.
    start: int
    end: int
    confidence: float   # 0.0-1.0
    text: str
```

Built-in factories:

- `G.dlp(project, info_types=None, location="global")` — Google Cloud DLP (production)
- `G.regex_detector(patterns=None)` — Lightweight regex (dev/test only)
- `G.multi(*detectors)` — Union of findings from multiple detectors
- `G.custom(async_fn)` — Wrap any async callable

#### ContentJudge Protocol

```python
class ContentJudge(Protocol):
    async def judge(self, text: str, context: dict | None = None) -> JudgmentResult: ...

@dataclass(frozen=True)
class JudgmentResult:
    passed: bool
    score: float
    reason: str
```

Built-in factories:

- `G.llm_judge(model="gemini-2.5-flash")` — LLM-as-judge (default)
- `G.perspective_api(api_key)` — Google Perspective API
- `G.custom_judge(async_fn)` — Wrap any async callable

### 1.3 Compilation Strategy

Each `GGuard` carries an internal `_Phase` enum (never user-facing):

| Phase | Compiles to | Examples |
| --- | --- | --- |
| `pre_model` | `before_model_callback` | `G.input()`, `G.rate_limit()`, `G.max_turns()` |
| `post_model` | `after_model_callback` | `G.output()`, `G.json()`, `G.length()`, `G.toxicity()`, `G.pii()` |
| `pre_agent` | `before_agent_callback` | `G.max_turns()`, `G.budget()` (check) |
| `context` | `CRedact` injection | `G.pii(action="redact")` |
| `middleware` | Middleware wrapper | `G.budget()` (tracking), `G.rate_limit()` (global) |

When the builder encounters `.guard(composite)`, it iterates the chain, groups by phase, and compiles each to the correct enforcement layer. The user never thinks about placement.

### 1.4 NamespaceSpec Conformance

```python
class GGuard:
    _kind: str                           # "pii", "budget", etc.
    _phase: _Phase                       # internal routing
    _reads_keys: frozenset[str] | None   # e.g. G.grounded reads {"docs"}
    _writes_keys: frozenset[str] | None  # always frozenset() -- guards never write
    _compile: Callable                   # fn(builder) -> mutates builder
```

### 1.5 Error Behavior

```python
class GuardViolation(BuilderError):
    guard_kind: str
    phase: str
    detail: str
    value: Any
```

### 1.6 Builder Wiring

`.guard()` in `seed.manual.toml` changes from `dual_callback` to `runtime_helper` delegating to `_guard_dispatch`:

```python
def _guard_dispatch(builder, value):
    if isinstance(value, (GComposite, GGuard)):
        composite = value if isinstance(value, GComposite) else GComposite([value])
        composite._compile_into(builder)
    elif callable(value):
        # Backwards compatible -- existing dual-callback behavior
        builder._callbacks.setdefault("before_model_callback", []).append(value)
        builder._callbacks.setdefault("after_model_callback", []).append(value)
    else:
        raise TypeError(...)
```

`.guard()` is also added to Pipeline, FanOut, Loop builders.

### 1.7 IR Integration

`AgentNode` gets one new optional field:

```python
guard_specs: tuple[Any, ...] | None = None
```

Preserved for diagnostics and contract checking. Actual callbacks are already wired into `_callbacks` by the compile step.

### 1.8 Contract Checker — Pass 15

Validates `GGuard._reads_keys` against upstream key availability. Same pattern as Pass 13 for ToolSchema/CallbackSchema.

___

## 2. T Namespace Expansion — Tools

**File:** `src/adk_fluent/_tools.py` (extend existing)

### 2.1 New Methods

```python
# -- Toolset Shortcuts --
T.mcp(url_or_params, *, tool_filter=None, prefix=None)
T.openapi(spec, *, tool_filter=None, auth=None)
T.retrieval(corpus, *, top_k=5)
T.code_exec(executor=None)

# -- Tool Wrappers --
T.confirm(tool_or_composite, message=None)
T.timeout(tool_or_composite, seconds=30)
T.cache(tool_or_composite, ttl=300, key_fn=None)
T.transform(tool_or_composite, *, pre=None, post=None)
T.mock(name, *, returns=None, side_effect=None)
```

### 2.2 Wrapper Classes

Three new `BaseTool` subclasses (internal):

- `_ConfirmWrapper` — delegates to inner tool, sets `require_confirmation=True`
- `_TimeoutWrapper` — wraps `run_async` with `asyncio.wait_for`
- `_CachedWrapper` — in-memory LRU keyed by args with TTL

All pass through the existing `_add_tools()` pipeline unchanged because they are `BaseTool` subclasses.

### 2.3 Toolset Shortcuts

`T.mcp()` and `T.openapi()` are thin factories over existing generated builders (`McpToolset`, `OpenAPIToolset`). No new classes — just ergonomic shortcuts that call `.build()` and wrap the result in `TComposite`.

### 2.4 T.mock()

Creates a `FunctionTool` wrapping a mock callable. For unit testing without API calls:

```python
agent.tools(T.mock("search", returns={"results": [...]}))
```

___

## 3. M Namespace Expansion — Middleware

**File:** `src/adk_fluent/_middleware.py` (factory methods) + `src/adk_fluent/middleware.py` (classes)

### 3.1 New Methods

```python
# -- Resilience --
M.circuit_breaker(threshold=5, reset_after=60)
M.timeout(seconds=30)
M.fallback_model(model="gemini-2.0-flash")

# -- Efficiency --
M.cache(ttl=300, key_fn=None)
M.dedup(window=10)

# -- Observability --
M.trace(exporter=None)
M.metrics(collector=None)
M.sample(rate, mw)
```

### 3.2 New Middleware Classes

- `CircuitBreakerMiddleware` — tracks consecutive failures per agent, trips open after threshold, auto-resets
- `TimeoutMiddleware` — per-agent execution timeout via deadline tracking in `before_agent`/`before_model`
- `FallbackModelMiddleware` — catches model errors, retries with fallback model
- `ModelCacheMiddleware` — caches LLM responses keyed by request content with TTL
- `DedupMiddleware` — suppresses duplicate model calls within a sliding window
- `TraceMiddleware` — OpenTelemetry span export (optional dep, graceful no-op)
- `MetricsMiddleware` — Prometheus/StatsD counter export (optional dep, graceful no-op)
- `_SampledMiddleware` — probabilistic wrapper (same pattern as `_ScopedMiddleware`)

All follow the existing `Middleware` protocol.

### 3.3 Layer Distinction from T and G

- `M.cache()` — model-level response caching
- `T.cache()` — tool-level result caching
- `M.timeout()` — per-agent execution timeout
- `T.timeout()` — per-tool call timeout
- `M.circuit_breaker()` — operational resilience (trips and recovers)
- `G.budget()` — safety policy (trips and kills)

### 3.4 Optional Dependencies

```toml
[project.optional-dependencies]
observability = ["opentelemetry-api>=1.20", "opentelemetry-sdk>=1.20"]
```

___

## 4. S Namespace Expansion — State Transforms

**File:** `src/adk_fluent/_transforms.py` (extend existing `S` class)

### 4.1 New Methods

```python
# -- Accumulation --
S.accumulate(key, *, into=None)       # Append value to running list
S.counter(key, step=1)                # Increment numeric value
S.history(key, max_size=10)           # Rolling window of past values

# -- Validation --
S.validate(schema_cls, *, strict=False)  # Pydantic/dataclass validation
S.require(*keys)                         # Assert keys exist and are truthy

# -- Structure --
S.flatten(key, separator=".")         # Nested dict -> dotted keys
S.unflatten(separator=".")            # Dotted keys -> nested dict
S.zip(*keys, into="zipped")          # Zip parallel lists
S.group_by(items_key, key_fn, into)   # Group list items
```

### 4.2 Key Design Decisions

- `S.accumulate("finding", into="findings")` reads `{"finding", "findings"}`, writes `{"findings"}`. Precise contract metadata.
- `S.require(*keys)` is syntactic sugar for the most common `S.guard()` pattern but with precise `_reads_keys` (unlike lambda-based guards which are opaque).
- `S.validate()` duck-types Pydantic (`model_validate`) and dataclasses (`__init__`). No hard dependency.
- All new methods return `STransform`. Compose with `>>` and `+` unchanged.

___

## 5. Cross-Module Interplay

### 5.1 Dependency Graph

```
G (Guards)
 |- compiles to -> before_model_callback, after_model_callback
 |- compiles to -> CRedact (for G.pii("redact"))
 |- compiles to -> middleware wrapper (for G.budget, G.rate_limit)
 |- imports from -> middleware.CostTracker (shared token counting)
 |- imports from -> _llm_judge (shared LLM-as-judge utility)
 |- imports from -> _predicate_utils.evaluate_predicate
 '- raises -> GuardViolation(BuilderError)

T (Tools) -- self-contained, no cross-module imports
M (Middleware) -- self-contained, no dependency on G or T
S (State) -- self-contained, no dependency on G, T, or M
```

### 5.2 Shared Utilities

`_llm_judge.py` (new) — extracted from `_eval.py`. Contains LLM-as-judge prompt template and response parsing. Used by both `E` (evaluation criteria) and `G` (runtime guards).

### 5.3 Guard Execution Order

Guards fire inside the middleware stack:

1. Middleware `before_agent` hooks fire
2. `G.max_turns()` fires (pre\_agent phase)
3. Middleware `before_model` hooks fire
4. `G.rate_limit()`, `G.input()` fire (pre\_model phase)
5. LLM call executes
6. `G.output()`, `G.pii()`, `G.toxicity()` fire (post\_model phase)
7. Middleware `after_model` hooks fire
8. Middleware `after_agent` hooks fire

Guard violations propagate through middleware. `M.retry()` does NOT retry guard violations — only model errors.

### 5.4 Cache Layering

```
User request
 -> M.cache check (model-level, TTL 60s)
    -> HIT: return cached LLM response, skip everything
    -> MISS: LLM call
       -> LLM invokes tool
          -> T.cache check (tool-level, TTL 600s)
             -> HIT: return cached API result
             -> MISS: call actual API
```

Two caches at two layers. Coherent, no confusion.

___

## 6. File Map

| File | Change |
| --- | --- |
| `src/adk_fluent/_guards.py` | **NEW** — G, GGuard, GComposite, GuardViolation, PIIDetector, ContentJudge |
| `src/adk_fluent/_llm_judge.py` | **NEW** — shared LLM-as-judge utility |
| `src/adk_fluent/_tools.py` | **EXTEND** — 5 new static methods, 3 wrapper classes |
| `src/adk_fluent/_middleware.py` | **EXTEND** — 6 new static methods |
| `src/adk_fluent/middleware.py` | **EXTEND** — 6 new middleware classes |
| `src/adk_fluent/_transforms.py` | **EXTEND** — 8 new static methods |
| `src/adk_fluent/_eval.py` | **REFACTOR** — extract `_llm_judge` to shared module |
| `src/adk_fluent/_helpers.py` | **MODIFY** — `_guard_dispatch` (backwards compatible) |
| `src/adk_fluent/__init__.py` | **AUTO** — regenerated by `just generate` |
| `src/adk_fluent/prelude.py` | **EXTEND** — add G to Tier 2 |
| `seeds/seed.manual.toml` | **MODIFY** — `.guard()` extra → runtime\_helper |
| `scripts/ir_generator.py` | **MODIFY** — add `guard_specs` to AgentNode |
| `tests/manual/test_guards.py` | **NEW** |
| `tests/manual/test_guards_integration.py` | **NEW** |
| `tests/manual/test_tools_t_expanded.py` | **NEW** |
| `tests/manual/test_tools_t_wrappers.py` | **NEW** |
| `tests/manual/test_middleware_expanded.py` | **NEW** |
| `tests/manual/test_transforms_expanded.py` | **NEW** |
| `tests/manual/test_interplay.py` | **NEW** |
| `tests/manual/test_contracts_guards.py` | **NEW** |
| `docs/user-guide/guards.md` | **NEW** |
| `docs/generated/cookbook/XX_guards.md` | **NEW** |
| `pyproject.toml` | **MODIFY** — add optional deps `[pii]`, `[observability]` |

___

## 7. Optional Dependencies

```toml
[project.optional-dependencies]
pii = ["google-cloud-dlp>=3.12"]
observability = ["opentelemetry-api>=1.20", "opentelemetry-sdk>=1.20"]
```

All optional providers degrade gracefully with `ImportError` and a clear message.

___

## 8. Backwards Compatibility

- `.guard(callable)` continues to work as dual-callback (existing behavior)
- All existing T, M, S methods unchanged
- No modifications to generated files except `__init__.py` (auto-regenerated)
- No changes to the code generation pipeline
- Single builder pipeline modification: `_guard_dispatch` in `_helpers.py`
