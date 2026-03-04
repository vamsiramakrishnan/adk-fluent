# Upstream ADK Impact Analysis & Generator Architecture

This document maps out how changes in the upstream `google-adk` package
propagate through adk-fluent's meta-engineering pipeline, which parts of
the codebase absorb those changes automatically, and which require manual
intervention.

## Architecture at a Glance

adk-fluent splits into two ownership planes:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HANDCODED PLANE                            │
│                                                                     │
│  _base.py          BuilderBase, operators (>> | * // @), COW       │
│  _context.py       C namespace — context engineering DSL           │
│  _prompt.py        P namespace — prompt composition DSL            │
│  _transforms.py    S namespace — state transform DSL               │
│  _artifacts.py     A namespace — artifact operations DSL           │
│  _middleware.py    M namespace — middleware composition DSL         │
│  _tools.py         T namespace — tool composition DSL              │
│  _primitives.py    FnAgent, TapAgent, FallbackAgent, RaceAgent…   │
│  _primitive_builders.py   tap(), gate(), race(), dispatch()…       │
│  _routing.py       Route — deterministic state-based routing       │
│  _helpers.py       run_one_shot, ChatSession, deep_clone…          │
│  _ir.py            TransformNode, TapNode, RouteNode… (hand IR)    │
│  middleware.py     RetryMiddleware, CostTracker, LatencyMiddleware  │
│  patterns.py       review_loop, map_reduce, cascade, fan_out_merge │
│  testing/          contracts.py, diagnosis.py                      │
│  seeds/seed.manual.toml   Human-curated overrides                  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                       AUTO-GENERATED PLANE                         │
│                                                                     │
│  manifest.json     ← scanner.py reads google-adk via reflection    │
│  seeds/seed.toml   ← seed_generator merges manifest + manual.toml │
│  agent.py (2)      ← generator combines seed + manifest           │
│  workflow.py (3)   ← Pipeline, FanOut, Loop                       │
│  config.py (38)    ← AgentConfig, LlmAgentConfig, RunConfig…      │
│  tool.py (51)      ← FunctionTool, GoogleSearchTool, MCPToolset…  │
│  service.py (15)   ← SessionService, ArtifactService, Memory…     │
│  plugin.py (12)    ← BasePlugin, LoggingPlugin…                   │
│  executor.py (5)   ← CodeExecutor variants                        │
│  planner.py (3)    ← BasePlanner, BuiltInPlanner                  │
│  runtime.py (3)    ← App, Runner, InMemoryRunner                  │
│  _ir_generated.py  ← AgentNode, SequenceNode… (frozen dataclasses)│
│  *.pyi stubs       ← IDE autocomplete and type checking           │
│  tests/generated/  ← Equivalence test scaffolds                   │
│  docs/generated/   ← API reference, migration guides              │
│  CLAUDE.md, .cursor/rules, .windsurfrules, etc.                   │
│                                                                     │
│  Total: 132 builders across 9 modules                              │
└─────────────────────────────────────────────────────────────────────┘
```

## The Meta-Engineering Pipeline

The generation pipeline has five stages. Each stage's output feeds the next:

```
                  ┌──────────────┐
                  │  google-adk  │  (installed pip package)
                  └──────┬───────┘
                         │
            ┌────────────▼─────────────┐
 Stage 1    │     scripts/scanner.py    │  Reflection-based introspection
            │  pkgutil.walk_packages()  │  of all Pydantic BaseModel classes
            └────────────┬─────────────┘
                         │
                  ┌──────▼───────┐
                  │ manifest.json │  Machine truth: 443 classes, 779 fields
                  └──────┬───────┘
                         │
            ┌────────────▼─────────────┐    ┌───────────────────┐
 Stage 2    │ scripts/seed_generator/   │◄───│ seed.manual.toml  │
            │  classifier → aliases →   │    │ (human overrides) │
            │  extras → emitter         │    └───────────────────┘
            └────────────┬─────────────┘
                         │
                  ┌──────▼───────┐
                  │  seed.toml   │  Human intent + machine truth merged
                  └──────┬───────┘
                         │
            ┌────────────▼─────────────┐
 Stage 3    │  scripts/generator/       │
            │  spec → ir_builders →     │
            │  module_builder → emit    │
            └────────────┬─────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │  .py code │   │ .pyi stubs│   │  tests/  │
   │ (builders)│   │ (types)   │   │generated │
   └──────────┘   └──────────┘   └──────────┘

 Stage 4    scripts/doc_generator.py → docs/generated/
 Stage 5    scripts/llms_generator.py → CLAUDE.md, editor rules
```

### Stage 1: Scanner — The Reflection Engine

`scripts/scanner.py` uses `pkgutil.walk_packages()` to discover every
module under `google.adk`, then inspects every public class to extract:

| Extracted | How | Used For |
|-----------|-----|----------|
| Class names & qualnames | `cls.__module__`, `cls.__name__` | Import paths in generated code |
| Pydantic fields | `cls.model_fields` | Builder setter methods |
| Field types | `get_type_hints(cls)` | Type annotations in stubs |
| Defaults | `FieldInfo.default` | Optional vs required detection |
| Callbacks | Heuristic: `"Callable" in type_str` | Additive `.before_model()` methods |
| Inheritance (MRO) | `cls.__mro__` | Field origin tracking |
| Init signatures | `inspect.signature(cls.__init__)` | Non-Pydantic class support |
| Docstrings | `cls.__doc__` | Generated API docs |

The scanner also has a **diff engine** (`diff_manifests()`) that compares
a previous manifest to the current one, reporting added/removed classes and
fields. This powers `just diff` and `just diff-md`.

### Stage 2: Seed Generator — Classification & Policy

The seed generator transforms raw manifest data into builder specifications:

1. **Classifier** (`classifier.py`): Tags each class by semantic role
   using MRO and naming conventions:
   - `BaseAgent` in MRO → `agent`
   - Name ends with `Service` → `service`
   - Name ends with `Tool`/`Toolset` → `tool`
   - Name ends with `Config` → `config`
   - etc.

2. **Builder-worthiness filter**: Only tags in `{agent, config, runtime,
   executor, planner, service, plugin, tool}` get builders. Classes tagged
   `eval`, `auth`, or `data` are skipped.

3. **Field policy** (`field_policy.py`): Decides per-field behavior:
   - `skip`: Parent references, internal fields → hidden from user
   - `additive`: Callback fields → `.before_model(fn)` appends
   - `list_extend`: List fields like `tools`, `sub_agents` → extend semantics

4. **Alias engine** (`aliases.py`): Derives ergonomic method names using
   morphological suffix rules:
   - `description` → `describe` (suffix `ription` → `ribe`)
   - `instruction` → `instruct` (suffix `ruction` → `ruct`)
   - `configuration` → `configure` (suffix `uration` → `ure`)
   - Plus semantic overrides: `output_key` → `outputs`, etc.

5. **Extras inference** (`extras.py`): Detects type-driven patterns and
   generates extra methods (e.g., `.tool()`, `.sub_agent()`, `.delegate()`).

6. **Manual merge**: `seed.manual.toml` overrides are applied last,
   providing human-curated renames (`LlmAgent` → `Agent`),
   optional constructor args, deprecated aliases, and hand-written
   extra method definitions.

### Stage 3: Code Generator — IR to Python

The generator uses a two-phase approach:

**Phase A: Spec → IR** (`ir_builders.py`)

Each `BuilderSpec` is converted into a `ClassNode` containing:
- `_ALIASES`, `_CALLBACK_ALIASES`, `_ADDITIVE_FIELDS` class attributes
- `_ADK_TARGET_CLASS` pointing to the real ADK class
- `__init__` with positional constructor args
- Fluent setter methods for every field
- Callback accumulation methods
- Extra behavioral methods (`.tool()`, `.ask()`, `.stream()`, etc.)
- `.build()` terminal delegating to `_safe_build()`

**Phase B: IR → Python** (`code_ir/emitters.py`)

The `emit_python()` function renders ClassNode IR into formatted Python
source. The emitter integrates ruff formatting inline, so output is
always canonical.

### Stage 4-5: Docs & LLM Context

Downstream generators read the same seed + manifest inputs to produce:
- Sphinx-compatible API reference pages
- Migration guides (ADK class → adk-fluent builder mapping)
- Cookbook examples with side-by-side comparisons
- LLM context files for every major AI coding tool

---

## Impact Classification: What Happens When ADK Changes

### Category 1: New Classes Added to ADK

**Example**: Google adds `VertexAiSearchToolV2`, a new tool class.

**Impact**: Fully automatic. Zero manual work.

| Stage | What Happens |
|-------|-------------|
| Scanner | Discovers new class, adds to manifest.json |
| Seed Generator | Classifies as `tool` (name ends in `Tool`), generates builder spec |
| Code Generator | Emits new `VertexAiSearchToolV2` builder in `tool.py` |
| Stubs | New `.pyi` entries with full type annotations |
| Tests | New equivalence test scaffold |
| Docs | New API reference entry |

**Action required**: `just all && just test` — that's it.

**Exception**: If the new class requires special treatment (custom
constructor, semantic renames, extra methods), add entries to
`seeds/seed.manual.toml` and re-run `just seed && just generate`.

### Category 2: New Fields Added to Existing Classes

**Example**: Google adds `reasoning_effort: str` to `LlmAgent`.

**Impact**: Fully automatic.

| Stage | What Happens |
|-------|-------------|
| Scanner | Captures new field in manifest.json under `LlmAgent` |
| Seed Generator | Includes field in builder spec; applies alias rules |
| Code Generator | Emits `.reasoning_effort(value)` setter on `Agent` builder |
| BuilderBase | `__getattr__` already forwards unknown fields dynamically |

The new field is accessible two ways:
1. Via the generated explicit setter method (after regeneration)
2. Via `BuilderBase.__getattr__` dynamic forwarding (works immediately
   even *before* regeneration, since it validates against `model_fields`)

**Action required**: `just all` to get explicit methods and type stubs.

### Category 3: Fields Removed from Existing Classes

**Example**: Google removes `deprecated_field` from `RunConfig`.

**Impact**: Partially automatic. May require manual cleanup.

| Stage | What Happens |
|-------|-------------|
| Scanner | Field disappears from manifest.json |
| Diff engine | `just diff` reports it as a removed field |
| Seed Generator | No longer includes field in spec |
| Code Generator | No longer emits setter method |
| Type stubs | Removed from `.pyi` — IDE shows errors for callers |

**Risk**: User code calling `.deprecated_field()` will break at the
*builder* level (method not found) rather than at ADK construction time.
The diff engine's `"breaking": true` flag surfaces this.

**Action required**:
1. `just archive` (saves current manifest as `manifest.previous.json`)
2. `just scan && just diff-md` (generates Markdown changelog)
3. Review breaking changes
4. `just all && just test`
5. Update user-facing migration guides if needed

### Category 4: Fields Renamed in Existing Classes

**Example**: Google renames `output_key` → `output_state_key` on `LlmAgent`.

**Impact**: Requires manual intervention in `seed.manual.toml`.

| Component | Impact |
|-----------|--------|
| Scanner | Sees removal of `output_key` + addition of `output_state_key` |
| Seed generator | Generates new alias for `output_state_key` automatically |
| Existing aliases | `outputs` alias (pointing to `output_key`) breaks |
| User code | `.outputs(key)` and `.output_key(key)` both break |

**Action required**:
1. Update alias in `seed.manual.toml`: `outputs = "output_state_key"`
2. Add deprecated alias to preserve backward compatibility:
   ```toml
   [builders.Agent.deprecated_aliases]
   output_key = { field = "output_state_key", use = "outputs" }
   ```
3. `just seed && just generate && just test`

### Category 5: Class Renamed or Moved

**Example**: Google moves `google.adk.tools.function_tool.FunctionTool`
to `google.adk.tools.core.FunctionTool`.

**Impact**: Automatic for the scanner (uses qualname), but seed.manual.toml
entries keyed by `source_class` need updating.

| Component | Impact |
|-----------|--------|
| Scanner | Discovers class at new qualname |
| Seed generator | Matches by qualname; if manual entries used old qualname, they won't match |
| Generated imports | Automatically use new import path |

**Action required**: Update `source_class` in `seed.manual.toml` if the
class was manually configured. The scanner falls back to matching by
short class name, so most cases resolve automatically.

### Category 6: Inheritance Hierarchy Changes

**Example**: Google inserts a new base class `EnhancedAgent` between
`BaseAgent` and `LlmAgent`, adding new fields.

**Impact**: Mostly automatic.

| Component | Impact |
|-----------|--------|
| Scanner | Captures new MRO chain; new inherited fields appear |
| Classifier | Still tags as `agent` (BaseAgent still in MRO) |
| Field origin | `inherited_from` tracking correctly attributes fields |
| Generator | Emits setters for all fields (own + inherited) |

**Action required**: `just all`. New inherited fields get methods
automatically. If the new base class itself deserves a builder, the
classifier handles it.

### Category 7: Callback Signature Changes

**Example**: Google changes `before_model_callback` from
`Callable[[CallbackContext], Content]` to
`Callable[[CallbackContext, ModelConfig], Content]`.

**Impact**: Transparent to the generated code, but affects handcoded
callback composition in `_base.py`.

| Component | Impact |
|-----------|--------|
| Scanner | Captures new type string |
| Generator | Updates type annotation in generated setter |
| Type stubs | Updated `.pyi` reflects new signature |
| `_base.py` | `_compose_callbacks()` may need signature adaptation |

**Action required**:
1. `just all` for type stub updates
2. Review `_base.py:_compose_callbacks()` if composition logic is
   signature-sensitive
3. Review handcoded middleware in `middleware.py` that wraps callbacks

### Category 8: New Pydantic Validators Added

**Example**: Google adds a validator that enforces
`max_iterations >= 1` on `LoopAgent`.

**Impact**: Transparent to generators. Surfaced at `.build()` time.

| Component | Impact |
|-----------|--------|
| Scanner | Captures validator names in manifest |
| Generator | No change needed (validators aren't generated) |
| `_safe_build()` | Catches `ValidationError` and provides clear error message |
| `validate()` | Pre-flight checks can catch this before build |

**Action required**: None. The existing error handling in `BuilderBase._safe_build()`
already wraps Pydantic `ValidationError` with user-friendly diagnostics.

### Category 9: Breaking API Changes (Major Version Bump)

**Example**: ADK 2.0 replaces Pydantic v1 models with v2, renames
`LlmAgent` to `Agent`, restructures the module tree.

**Impact**: Significant manual work, but the pipeline absorbs most of it.

| Component | Impact |
|-----------|--------|
| Scanner | Must handle Pydantic v2 API (`model_fields` vs `__fields__`) |
| Scanner | New module paths discovered automatically |
| Seed generator | Renames and overrides in `seed.manual.toml` need updating |
| `_base.py` | `__getattr__` validation via `model_fields` still works (Pydantic v2 compatible) |
| `_safe_build()` | Pydantic v2 `ValidationError` format may differ |

**Action required**:
1. Update scanner if Pydantic introspection API changed
2. `just scan` to get new manifest
3. Review `seed.manual.toml` for stale entries
4. `just all && just test`
5. Update handcoded files that import ADK types directly

---

## Handcoded Components: Upstream Sensitivity Matrix

Each handcoded file has different sensitivity to upstream changes:

| File | Sensitivity | What Would Break It |
|------|------------|-------------------|
| `_base.py` | **Medium** | Changes to Pydantic `model_fields` API; callback signature changes; new ADK base classes that need special handling in `_prepare_build_config()` |
| `_context.py` | **Low** | Changes to ADK's `include_contents` enum or `InstructionProvider` protocol |
| `_prompt.py` | **Low** | Changes to ADK's `instruction` field type or `InstructionProvider` |
| `_transforms.py` | **Low** | Changes to ADK's session state API (`session.state` dict interface) |
| `_artifacts.py` | **Low** | Changes to ADK's artifact service API (`save_artifact`, `load_artifact`) |
| `_middleware.py` | **Low** | Changes to ADK's callback protocol signatures |
| `_tools.py` | **Low** | Changes to `FunctionTool` or `BaseTool` constructor |
| `_primitives.py` | **High** | Changes to `BaseAgent.run_async_impl()` or `InvocationContext` API |
| `_helpers.py` | **High** | Changes to `Runner`, `InMemoryRunner`, `Session` APIs |
| `_routing.py` | **Medium** | Changes to how `sub_agents` are structured or transfer works |
| `_ir.py` | **Low** | Changes to agent class names (cosmetic only) |
| `middleware.py` | **Medium** | Changes to ADK's callback/event lifecycle |
| `patterns.py` | **Low** | Composed from other handcoded components; transitive sensitivity |
| `_interop.py` | **High** | Direct ADK API surface adapter; any restructuring breaks it |

### The Highest-Risk Handcoded Files

**`_primitives.py`** — Defines custom `BaseAgent` subclasses (`FnAgent`,
`TapAgent`, `FallbackAgent`, `MapOverAgent`, `RaceAgent`, etc.) that
override `_run_async_impl()`. Any change to ADK's agent execution
protocol directly breaks these.

**`_helpers.py`** — Contains execution helpers (`run_one_shot`,
`run_stream`, `ChatSession`) that instantiate ADK `Runner` and
`InMemorySessionService` directly. Changes to these ADK APIs require
manual updates.

**`_base.py`** — The `_prepare_build_config()` method contains
logic that introspects ADK class fields at build time. Changes to
Pydantic's model API or ADK's field naming conventions affect this.
The `__getattr__` dynamic forwarding validates against
`_ADK_TARGET_CLASS.model_fields`.

---

## Generator Components: What Would We Change

When upstream ADK changes require generator modifications, here's what
to touch and why:

### Scanner Changes (`scripts/scanner.py`)

| Upstream Change | Scanner Modification |
|----------------|---------------------|
| New inspection pattern (not Pydantic, not `__init__`) | Add new `inspection_mode` in `scan_class()` |
| New field metadata (e.g., field groups, access level) | Extend `FieldInfo` dataclass, update `scan_class()` |
| Module restructuring | No change — auto-discovery via `pkgutil.walk_packages()` |
| New base class hierarchy | No change — MRO is captured automatically |
| Non-public API surfacing | Update `discover_classes()` filter logic |

### Seed Generator Changes (`scripts/seed_generator/`)

| Upstream Change | Seed Generator Modification |
|----------------|---------------------------|
| New semantic category of classes | Add tag to `classifier.py` and `_BUILDER_WORTHY_TAGS` |
| New field naming conventions | Update `aliases.py` suffix rules or `SEMANTIC_OVERRIDES` |
| New callback patterns | Update `generate_callback_aliases()` in `aliases.py` |
| New field policy needs | Update `field_policy.py` inference rules |
| New method generation patterns | Add to `extras.py` type-driven inference |

### Code Generator Changes (`scripts/generator/`)

| Upstream Change | Generator Modification |
|----------------|----------------------|
| New builder behavior pattern | Add new `behavior` case in `ir_extra_methods()` (`ir_builders.py`) |
| New code IR node type needed | Add to `scripts/code_ir/nodes.py` and `emitters.py` |
| Change to build protocol | Update `ir_build_method()` in `ir_builders.py` |
| New import resolution needs | Update `imports.py` |
| New type normalization | Update `type_normalization.py` |
| Change to stub format | Update `stubs.py` |

### Seed Manual Overrides (`seeds/seed.manual.toml`)

This is the **human intent layer** — the file where developers express
decisions that can't be inferred automatically:

```toml
# Rename ADK class → fluent builder name
[renames]
LlmAgent = "Agent"
SequentialAgent = "Pipeline"
ParallelAgent = "FanOut"
LoopAgent = "Loop"

# Optional constructor args (not required, but convenient)
[builders.Agent]
optional_constructor_args = ["model"]

# Hand-written extra methods
[[builders.Agent.extras]]
name = "tool"
signature = "(self, fn_or_tool: Any) -> Self"
behavior = "list_append"
target_field = "tools"
doc = "Add a tool (function or BaseTool instance)."

# Deprecated aliases with migration path
[builders.Agent.deprecated_aliases]
save_as = { field = "output_key", use = "writes" }
output_schema = { field = "output_schema", use = "returns" }
```

When ADK adds a class that needs special treatment beyond what the
seed generator infers, add entries here.

---

## Upgrade Runbook: Step-by-Step

When a new ADK version is released:

```bash
# 1. Archive current state for diff comparison
just archive

# 2. Upgrade ADK
pip install --upgrade google-adk

# 3. Scan the new ADK
just scan

# 4. Review what changed
just diff           # JSON summary
just diff-md        # Publishable Markdown changelog

# 5. Check if seed.manual.toml needs updates
#    (renamed classes, moved fields, new extras)
#    Edit seeds/seed.manual.toml if needed

# 6. Regenerate everything
just all

# 7. Verify
just test           # Run full test suite
just typecheck      # Verify type stubs
just ci             # Full local CI

# 8. Review generated diff
git diff --stat

# 9. Commit
git add -A && git commit -m "chore: upgrade to google-adk X.Y.Z"
```

### When `just diff` Reports Breaking Changes

If the diff output shows `"breaking": true`:

1. Check `removed_classes` — do we have manual overrides for them?
2. Check `removed_fields` — do we have aliases pointing to them?
3. Update `seed.manual.toml` to add deprecated aliases for removed
   fields (smooth migration for downstream users)
4. Review handcoded files in the sensitivity matrix above
5. Run `just all && just test` to verify

---

## Design Principles of the Meta-Engineering Pattern

### 1. Machine Truth + Human Intent = Generated Code

The pipeline separates concerns:
- **manifest.json** captures *what ADK exposes* (machine truth via reflection)
- **seed.manual.toml** captures *what we want* (human intent via curation)
- The generator combines them deterministically

This means upstream changes are absorbed by re-scanning (new machine truth),
and human decisions persist across regenerations (stable human intent).

### 2. Idempotent & Deterministic

Running `just generate` twice produces identical output. This is enforced
by the `just check-gen` CI gate, which regenerates and diffs.

### 3. Escape Hatch: Dynamic Forwarding

`BuilderBase.__getattr__` validates method calls against the ADK target
class's `model_fields` at runtime. This means new ADK fields work
*immediately* even before regeneration — the generated explicit methods
are an optimization for discoverability and type safety, not a requirement.

### 4. IR-Based Code Generation

The generator doesn't emit Python strings directly. It builds an
intermediate representation (`ClassNode`, `MethodNode`, etc. in
`scripts/code_ir/nodes.py`) and then emits from that IR. This enables:
- Multiple output formats from the same IR (`.py`, `.pyi`, tests)
- Structural validation before emission
- Consistent formatting (ruff is applied to emitter output)

### 5. Progressive Enhancement

The codebase layers capabilities:
1. **Auto-generated builders** — zero-effort field access for any ADK class
2. **Handcoded DSLs** (S, C, P, A, M, T) — rich composition on top
3. **Expression operators** (>>, |, *, //, @) — concise syntax on top
4. **Patterns** (review_loop, cascade) — reusable architectures on top

Upstream changes only affect layer 1. Layers 2-4 are stable across
ADK versions because they compose *builders*, not ADK internals directly.
