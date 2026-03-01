# SPEC v5 Gap Analysis: Spec vs. Repo Reality

**Repo:** github.com/vamsiramakrishnan/adk-fluent (master, 70 commits)\
**Version:** 0.5.2 (PyPI-published)\
**Codebase:** 29 source files, ~12,600 lines, 51 examples, ~9,500 lines of tests\
**Current Spec in Repo:** SPEC_v2.md (published), v3/v4 specs in docs/other_specs/

______________________________________________________________________

## 1. What Exists and Works (The Foundation)

The repo has completed what corresponds to **v4 Phases 1–4** from the spec lineage. This is real, shipped, tested code — not design docs.

### 1.1 Codegen Pipeline (Spec v2 — Complete)

| Component      | File                              | Status                                                 |
| -------------- | --------------------------------- | ------------------------------------------------------ |
| Scanner        | `scripts/scanner.py` (18K)        | ✅ Introspects installed ADK via Pydantic model_fields |
| Manifest       | `manifest.json` (818K)            | ✅ Complete snapshot of google-adk 1.25.0              |
| Seed           | `seeds/seed.toml` (60K)           | ✅ Human intent for all builders                       |
| Generator      | `scripts/generator.py` (42K)      | ✅ Produces builders + .pyi stubs + tests              |
| IR Generator   | `scripts/ir_generator.py` (11K)   | ✅ Produces \_ir_generated.py from manifest            |
| Seed Generator | `scripts/seed_generator.py` (25K) | ✅ Auto-generates seed.toml from manifest              |

This is the Tide Principle in practice: when ADK releases a new version, `scanner.py` runs, `manifest.json` updates, and the generator produces updated builders. The cost of tracking upstream is one auto-PR per release cycle.

### 1.2 IR Layer (Spec v4 — Complete)

**Hand-written nodes** (`_ir.py`): TransformNode, TapNode, FallbackNode, RaceNode, GateNode, MapOverNode, TimeoutNode, RouteNode, TransferNode — these represent concepts ADK doesn't have.

**Generated nodes** (`_ir_generated.py`): AgentNode, SequenceNode, ParallelNode, LoopNode — mirror ADK's agent hierarchy with extension fields (writes_keys, reads_keys, produces_type, consumes_type).

**FullNode** type union covers all 13 node types.

**AgentEvent** — backend-agnostic event representation with content, state_delta, artifact_delta, transfer_to, escalate, tool_calls, tool_responses.

### 1.3 Builder Layer (Complete)

**Generated builders** (from seed.toml): Agent, BaseAgent, Pipeline, FanOut, Loop, plus ~130 config/tool/service/plugin/executor/planner builders covering the full ADK surface.

**BuilderBase** (`_base.py`, 1549 lines): operator overloading (`>>`, `|`, `*`), dynamic `__getattr__` field forwarding with Pydantic validation, `__repr__`, callback composition, `_prepare_build_config()`, `to_ir()`.

**Key ergonomics**: `.instruct()`, `.writes()`, `.tool()`, `.model()`, `.describe()`, `.history()`, `.static()` — all with .pyi type stubs for IDE autocomplete.

### 1.4 Composition Primitives (Complete)

| Primitive                | Implementation                | Builds To                |
| ------------------------ | ----------------------------- | ------------------------ |
| `a >> b`                 | Pipeline (SequentialAgent)    | SequenceNode             |
| `a \| b`                 | FanOut (ParallelAgent)        | ParallelNode             |
| `a * 5`                  | Loop (LoopAgent)              | LoopNode                 |
| `a * until(pred)`        | Loop + CheckpointAgent        | LoopNode + escalate      |
| `a // b`                 | FallbackBuilder               | FallbackNode             |
| `a @ fn`                 | TapBuilder                    | TapNode                  |
| `>> fn`                  | FnAgent (zero-cost transform) | TransformNode            |
| `>> dict`                | Route from dict               | RouteNode                |
| Route()                  | Deterministic routing         | RouteNode → \_RouteAgent |
| `S.pick/drop/rename/...` | State transforms              | TransformNode            |

### 1.5 Backend Layer (Complete)

**Backend protocol** (`_protocol.py`): `compile(node, config) → Any`, `run(compiled, prompt) → list[AgentEvent]`, `stream(compiled, prompt) → AsyncIterator[AgentEvent]`.

**ADK backend** (`backends/adk.py`, 377 lines): Compiles all 13 IR node types to native ADK agents. Creates `App` with `ResumabilityConfig`, `EventsCompactionConfig`, and middleware-to-plugin conversion.

### 1.6 Middleware Layer (Partial)

**Protocol** (`middleware.py`): 13-callback protocol matching ADK's BasePlugin signature. `_MiddlewarePlugin` adapter compiles a middleware stack into a single ADK plugin.

**Built-in implementations**: Only RetryMiddleware and StructuredLogMiddleware exist.

### 1.7 Testing (Partial)

**check_contracts**: Adjacent-pair reads-before-writes checking on SequenceNode children only.
**mock_backend**: Simple mock that records events.
**harness**: Test harness skeleton.
**Generated tests**: ~9,500 lines of builder tests.
**Manual tests**: Expression language, transforms, IR conversion, routing, primitives, algebra, viz.

### 1.8 Other Infrastructure

- `viz.py`: ir_to_mermaid graph visualization
- `_prompt.py`: Prompt template handling
- `di.py`: Dependency injection
- `presets.py`: Preset agent configurations
- `decorators.py`: @agent decorator
- `.pyi` stubs for all generated builders
- Sphinx documentation site
- CI/CD via GitHub Actions
- Pre-commit hooks, ruff, pyright

______________________________________________________________________

## 2. What v5 Spec Calls For: Section-by-Section Gap

### §1 Typed State System — 🔴 Not Started

| v5 Component                                                   | Repo State                                                                                 | Gap                                                                  |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| `StateSchema` base class                                       | ❌ Does not exist                                                                          | New `state/_schema.py` needed                                        |
| Scope annotations (SessionScoped, UserScoped, AppScoped, Temp) | ❌ Does not exist                                                                          | New `state/_field_ref.py` needed                                     |
| `StateFieldRef` descriptor                                     | ❌ Does not exist                                                                          | Part of `_field_ref.py`                                              |
| `bind()` proxy for typed access                                | ❌ Does not exist                                                                          | New `state/_proxy.py` needed                                         |
| Schema-bound agents (`.writes(BillingState.intent)`)           | ⚠️ `.writes()`, `.produces()`, `.consumes()` exist but use untyped strings/Pydantic models | Need to accept StateFieldRef                                         |
| Full-graph contract checking (topological order)               | ⚠️ `check_contracts()` exists but only checks adjacent SequenceNode pairs                  | Must generalize to full DAG traversal with type checking             |
| Schema composition (multiple inheritance)                      | ❌ Does not exist                                                                          | Part of `_schema.py`                                                 |
| Backward compatibility (mixed typed/untyped)                   | ⚠️ AgentNode has `writes_keys: frozenset[str]` and `reads_keys: frozenset[str]`            | Need to support both `frozenset[str]` and `frozenset[StateFieldRef]` |

**Size estimate:** ~500 lines new code across 3 files + modifications to AgentNode, check_contracts, and builder `.writes()`/`.reads()` methods.

### §2 Streaming Edge Semantics — 🔴 Not Started

| v5 Component                        | Repo State                            | Gap                                                                   |
| ----------------------------------- | ------------------------------------- | --------------------------------------------------------------------- |
| `EdgeSemantics` dataclass           | ❌                                    | New in `_ir.py` or `streaming/_edge.py`                               |
| `.stream_to()` builder method       | ❌                                    | Add to BuilderBase                                                    |
| `SequenceNode.edge_semantics` field | ❌ SequenceNode has no edge metadata  | Add to \_ir_generated.py (may need manual override or seed extension) |
| `ParallelNode.merge` field          | ❌ ParallelNode has no merge strategy | Same                                                                  |
| Streaming contract checking         | ❌                                    | New checker                                                           |
| ADK backend streaming adapters      | ❌                                    | New `streaming/_adapters.py`                                          |

**Complication:** SequenceNode and ParallelNode are **generated** from seed.toml/manifest.json. Adding v5 extension fields requires either: (a) modifying the IR generator to inject extension fields, or (b) making \_ir_generated.py hand-written (breaking the codegen pipeline). The current IR generator already adds `writes_keys`, `reads_keys`, `produces_type`, `consumes_type` — the same pattern can add `edge_semantics` and `merge`.

**Size estimate:** ~400 lines across 3 files + IR generator modification.

### §3 Cost-Aware Routing — 🔴 Not Started

| v5 Component                               | Repo State                             | Gap                                        |
| ------------------------------------------ | -------------------------------------- | ------------------------------------------ |
| `ModelSelectorNode`                        | ❌                                     | New IR node in `_ir.py`                    |
| `ModelCandidate`                           | ❌                                     | Dataclass in `cost/_selector.py`           |
| Selection strategies                       | ❌                                     | Implementation in `cost/_selector.py`      |
| `CostModel` / `estimate_cost()`            | ❌                                     | New `cost/_model.py`, `cost/_estimator.py` |
| `CostAttributionMiddleware` (OTel metrics) | ❌ Only StructuredLogMiddleware exists | New `middleware/cost_attribution.py`       |
| `.model_select()` builder method           | ❌                                     | Add to Agent builder                       |
| `TrafficAssumptions`                       | ❌                                     | Part of `cost/_model.py`                   |
| OTel metric emission                       | ❌ No OTel dependency at all           | New dependency: `opentelemetry-api`        |

**Dependency impact:** v5 introduces `opentelemetry-api` as a required dependency (or optional extra). Currently `pyproject.toml` only depends on `google-adk>=1.20.0`.

**Size estimate:** ~600 lines across 4 new files + new IR node + builder method + new dependency.

### §4 A2A Protocol Interop — 🔴 Not Started

| v5 Component                     | Repo State                                                                            | Gap                         |
| -------------------------------- | ------------------------------------------------------------------------------------- | --------------------------- |
| `RemoteAgentNode`                | ❌                                                                                    | New IR node                 |
| `_A2AAgent` (BaseAgent subclass) | ❌                                                                                    | New in `a2a/_remote.py`     |
| `AgentCard` generation           | ❌                                                                                    | New `a2a/_card.py`          |
| `A2AServer`                      | ❌                                                                                    | New `a2a/_server.py`        |
| `AgentDirectory`                 | ❌                                                                                    | New `a2a/_directory.py`     |
| `RemoteAgent` builder            | ❌                                                                                    | New builder class           |
| `RetryConfig`                    | ⚠️ Exists as a generated config builder, but it's ADK's RetryConfig, not adk-fluent's | May need A2A-specific retry |

**Size estimate:** ~800 lines across 5 new files + new IR node + new builder.

### §5 Telemetry Integration — 🔴 Not Started

| v5 Component                                               | Repo State                                                                       | Gap                                        |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------ |
| `OTelEnrichmentMiddleware`                                 | ❌ StructuredLogMiddleware exists (captures JSON logs, doesn't touch OTel spans) | **Replace** StructuredLogMiddleware        |
| OTel metric definitions                                    | ❌                                                                               | New `telemetry/_metrics.py`                |
| `TelemetryConfig`                                          | ❌ ExecutionConfig exists but has no telemetry fields                            | Add to ExecutionConfig or new config class |
| Configuration pass-through (`--trace_to_cloud` → env vars) | ❌                                                                               | New `telemetry/_config.py`                 |

**Critical finding:** `StructuredLogMiddleware` in `middleware.py` (lines 265-310) is exactly the v4-era approach that v5 replaces. It captures structured event logs in memory — useful for dev, but duplicates ADK's OTel spans in production. The v5 spec replaces this with `OTelEnrichmentMiddleware` that annotates ADK's existing spans.

**Size estimate:** ~300 lines across 3 new files + StructuredLogMiddleware replacement.

### §6 Evaluation Harness — 🔴 Not Started

| v5 Component                               | Repo State | Gap                             |
| ------------------------------------------ | ---------- | ------------------------------- |
| `FluentEvalSuite`                          | ❌         | New `eval/_suite.py`            |
| `FluentCase` → `EvalCase` compilation      | ❌         | New `eval/_case.py`             |
| `FluentJudge` → MetricEvaluatorRegistry    | ❌         | New `eval/_judge.py`            |
| `FluentEvalReport` (wraps EvalCaseResult)  | ❌         | New `eval/_report.py`           |
| `UserSimulation` → UserSimulatorProvider   | ❌         | New `eval/_simulation.py`       |
| File format interop (.evalset.json ↔ YAML) | ❌         | New `eval/_loader.py`           |
| Sub-graph targeting                        | ❌         | Logic in `eval/_suite.py`       |
| Typed state assertions                     | ❌         | New `eval/_state_assertions.py` |

**Size estimate:** ~1,200 lines across 7 new files. Largest new subsystem.

### §7 Multi-Modal Content Contracts — 🔴 Not Started

| v5 Component                                          | Repo State | Gap                          |
| ----------------------------------------------------- | ---------- | ---------------------------- |
| `ContentSpec`                                         | ❌         | New `content/_spec.py`       |
| `Modality` enum                                       | ❌         | Part of `_spec.py`           |
| `.accepts()` / `.produces_modality()` builder methods | ❌         | Add to Agent builder         |
| Modality contract checking                            | ❌         | New `content/_validation.py` |

**Size estimate:** ~200 lines across 2 new files + builder methods.

### §8 Event Replay — 🟡 Partially Exists (Different Architecture)

| v5 Component                                       | Repo State                                       | Gap                                                         |
| -------------------------------------------------- | ------------------------------------------------ | ----------------------------------------------------------- |
| `RecordingsPlugin` builder                         | ✅ Exists (generated, wraps ADK's native plugin) | Not v5's Recorder — different purpose                       |
| `ReplayPlugin` builder                             | ✅ Exists (generated, wraps ADK's native plugin) | Not v5's ReplayerBackend — different purpose                |
| `Recorder` (OTel span exporter + event middleware) | ❌                                               | New `debug/_recorder.py`                                    |
| `Recording` format (spans + events + state)        | ❌                                               | New `debug/_recording.py`                                   |
| `ReplayerBackend` (deterministic via span data)    | ❌                                               | New `debug/_replayer.py` (also new in `backends/replay.py`) |
| `diff_events()`                                    | ❌                                               | New `debug/_diff.py`                                        |

**Note:** The repo's RecordingsPlugin/ReplayPlugin are generated fluent builders for ADK's *native* CLI plugins. These record/replay at the ADK level. The v5 Recorder is an adk-fluent concept that captures IR-correlated OTel spans + events for pipeline-level replay and diffing. They complement each other but serve different purposes.

**Size estimate:** ~600 lines across 4 new files + new backend.

### §9 Execution Boundaries — 🔴 Not Started

| v5 Component                           | Repo State | Gap                                 |
| -------------------------------------- | ---------- | ----------------------------------- |
| `ExecutionBoundary`                    | ❌         | New `distributed/_boundary.py`      |
| `TransportConfig` / `ScalingConfig`    | ❌         | Part of `_boundary.py`              |
| Pipeline segmentation                  | ❌         | New `distributed/_segmenter.py`     |
| State serialization at boundaries      | ❌         | New `distributed/_serialization.py` |
| `.execution_boundary()` builder method | ❌         | Add to Agent builder                |

**Size estimate:** ~500 lines across 3 new files + builder methods.

### §10 Unified Contract Checker — 🟡 Partially Exists

| v5 Component                | Repo State                                                            | Gap                             |
| --------------------------- | --------------------------------------------------------------------- | ------------------------------- |
| `check_all()`               | ❌ Only `check_contracts()` exists (adjacent-pair, SequenceNode only) | New `contracts/_checker.py`     |
| `ContractReport`            | ❌ Returns `list[str]` currently                                      | New dataclass                   |
| Checker registry            | ❌                                                                    | New `contracts/_registry.py`    |
| `check_dataflow_contracts`  | ⚠️ Exists as `check_contracts` but limited                            | Generalize to full DAG          |
| `check_type_contracts`      | ❌                                                                    | New (depends on §1 StateSchema) |
| `check_streaming_contracts` | ❌                                                                    | New (depends on §2)             |
| `check_modality_contracts`  | ❌                                                                    | New (depends on §7)             |
| `check_boundary_contracts`  | ❌                                                                    | New (depends on §9)             |
| `check_a2a_contracts`       | ❌                                                                    | New (depends on §4)             |
| `check_cost_contracts`      | ❌                                                                    | New (depends on §3)             |

**Size estimate:** ~400 lines for the framework + each individual checker is ~50–100 lines.

### §11 Updated Middleware — 🟡 Partial

| v5 Middleware             | Repo State                                              |
| ------------------------- | ------------------------------------------------------- |
| `RetryMiddleware`         | ✅ Exists                                               |
| `StructuredLogMiddleware` | ⚠️ Exists but v5 removes it in favor of otel_enrichment |
| `otel_enrichment`         | ❌                                                      |
| `cost_attribution`        | ❌                                                      |
| `token_budget`            | ❌                                                      |
| `cache`                   | ❌                                                      |
| `rate_limiter`            | ❌                                                      |
| `circuit_breaker`         | ❌                                                      |
| `tool_approval`           | ❌                                                      |
| `pii_filter`              | ❌                                                      |
| `recorder`                | ❌                                                      |

**Of the 11 middleware listed in v5, only 1 (retry) exists. StructuredLog exists but is marked for replacement.**

### §12 Module Architecture — 🟡 Flat vs. Nested

**Current structure** (flat):

```
src/adk_fluent/
  __init__.py, _base.py, _ir.py, _ir_generated.py, _helpers.py, _transforms.py,
  _routing.py, _prompt.py, agent.py, workflow.py, config.py, tool.py, service.py,
  plugin.py, executor.py, planner.py, runtime.py, middleware.py, viz.py,
  di.py, decorators.py, presets.py
  backends/ (3 files)
  testing/ (4 files)
```

**v5 target** (nested):

```
src/adk_fluent/
  (all existing files retained)
  state/         (3 files — §1)
  cost/          (3 files — §3)
  a2a/           (5 files — §4)
  telemetry/     (3 files — §5)
  eval/          (7 files — §6)
  debug/         (4 files — §8)
  streaming/     (2 files — §2)
  content/       (2 files — §7)
  distributed/   (3 files — §9)
  contracts/     (9 files — §10)
  backends/      (+replay.py)
  middleware/    (promoted from single file to package with per-middleware files)
```

______________________________________________________________________

## 3. What Exists That the Spec PRESERVES Unchanged

These files need zero modification for v5:

| File                                                                 | Size                        | Reason                                                       |
| -------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------ |
| `_base.py`                                                           | 1549 lines                  | Operator overloading, BuilderBase — untouched                |
| `_transforms.py`                                                     | 230 lines                   | S transforms — untouched                                     |
| `_routing.py`                                                        | 211 lines                   | Route builder — untouched                                    |
| `_prompt.py`                                                         | ~150 lines                  | Prompt templating — untouched                                |
| `agent.py`                                                           | 427 lines                   | Generated builders — untouched (codegen produces these)      |
| `workflow.py`                                                        | 269 lines                   | Pipeline/FanOut/Loop builders — untouched                    |
| `config.py`                                                          | 2400+ lines                 | Generated config builders — untouched                        |
| `tool.py`                                                            | 2800+ lines                 | Generated tool builders — untouched                          |
| `service.py`, `plugin.py`, `executor.py`, `planner.py`, `runtime.py` | Generated                   | Untouched                                                    |
| All `.pyi` stubs                                                     | Generated                   | Untouched                                                    |
| `backends/_protocol.py`                                              | 34 lines                    | Backend protocol — untouched                                 |
| `testing/mock_backend.py`                                            | ~60 lines                   | Mock backend — untouched                                     |
| `testing/harness.py`                                                 | ~20 lines                   | Test harness — untouched                                     |
| `scripts/`                                                           | All 6 scripts               | Codegen pipeline — untouched                                 |
| `seeds/`                                                             | seed.toml, seed.manual.toml | Untouched                                                    |
| All 51 examples                                                      | Existing examples           | Untouched (new examples may be added)                        |
| All tests                                                            | ~9,500 lines                | Existing tests pass — new tests added alongside new features |

## 4. What Exists That Needs MODIFICATION

| File                                              | Change                                                                                                                                                                                                                                           | Complexity               |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------ |
| `_ir.py`                                          | Add `ModelSelectorNode`, `RemoteAgentNode`, `ExecutionBoundary` and related dataclasses. Extend `ExecutionConfig` with telemetry fields. Update `Node` union.                                                                                    | Medium                   |
| `_ir_generated.py` (or `scripts/ir_generator.py`) | AgentNode needs `content_spec`, `execution_boundary`, `model_selector`, `state_schema` fields. SequenceNode needs `edge_semantics`. ParallelNode needs `merge`. Either modify the IR generator to inject these, or add them to seed.manual.toml. | Medium — touches codegen |
| `middleware.py`                                   | Replace `StructuredLogMiddleware` with `OTelEnrichmentMiddleware`. Can either refactor in-place or split into a middleware package.                                                                                                              | Low                      |
| `testing/contracts.py`                            | Current `check_contracts()` becomes `check_dataflow_contracts()` inside the new `contracts/` package. Existing logic preserved, just moved and generalized.                                                                                      | Low                      |
| `viz.py`                                          | Add cost annotations, modality labels, streaming edge decorations to Mermaid output.                                                                                                                                                             | Low                      |
| `backends/adk.py`                                 | Add dispatch entries for `ModelSelectorNode`, `RemoteAgentNode`. Extend `compile()` to handle new ExecutionConfig fields (telemetry, execution boundaries).                                                                                      | Medium                   |
| `_helpers.py`                                     | Extend `_agent_to_ir()` to populate new AgentNode fields (content_spec, etc.) from builder config.                                                                                                                                               | Low                      |
| `pyproject.toml`                                  | Add `opentelemetry-api` dependency (required or optional extra). Add `pyyaml` if not already required for eval YAML loading.                                                                                                                     | Trivial                  |

______________________________________________________________________

## 5. Implementation Roadmap: Ordered by Dependencies

```
Phase 5a: Typed State (§1)                    ~500 lines   [no dependencies]
    └── state/_schema.py, state/_field_ref.py, state/_proxy.py
    └── Modify: AgentNode, check_contracts, _helpers.py

Phase 5b: Telemetry Integration (§5)          ~300 lines   [no dependencies]
    └── telemetry/_enrichment.py, telemetry/_metrics.py, telemetry/_config.py
    └── Modify: middleware.py (replace StructuredLogMiddleware), pyproject.toml (add otel dep)
    └── Modify: ExecutionConfig (add TelemetryConfig)

Phase 5c: Unified Contract Checker (§10)      ~500 lines   [depends on 5a]
    └── contracts/_checker.py, contracts/_registry.py, contracts/_dataflow.py, ...
    └── Move: testing/contracts.py → contracts/_dataflow.py (generalize)

Phase 5d: Cost-Aware Routing (§3)             ~600 lines   [depends on 5b]
    └── cost/_model.py, cost/_selector.py, cost/_estimator.py
    └── New middleware: cost_attribution.py
    └── New IR node: ModelSelectorNode
    └── Modify: backends/adk.py (add compile dispatch)

Phase 5e: Streaming Edge Semantics (§2)       ~400 lines   [depends on 5c for contract checking]
    └── streaming/_edge.py, streaming/_adapters.py
    └── Modify: _ir_generated.py or ir_generator.py (add edge_semantics, merge)

Phase 5f: Multi-Modal Content (§7)            ~200 lines   [depends on 5c for contract checking]
    └── content/_spec.py, content/_validation.py

Phase 5g: Evaluation Harness (§6)             ~1200 lines  [depends on 5a, 5b]
    └── eval/_suite.py, _case.py, _judge.py, _report.py, _simulation.py, _loader.py, _state_assertions.py

Phase 5h: Event Replay (§8)                   ~600 lines   [depends on 5b]
    └── debug/_recorder.py, _recording.py, _replayer.py, _diff.py
    └── New backend: backends/replay.py

Phase 5i: A2A Protocol Interop (§4)           ~800 lines   [parallel track]
    └── a2a/_remote.py, _card.py, _client.py, _server.py, _directory.py
    └── New IR node: RemoteAgentNode

Phase 5j: Execution Boundaries (§9)           ~500 lines   [depends on 5a for schema serialization]
    └── distributed/_boundary.py, _serialization.py, _segmenter.py

Phase 5k: Remaining Middleware (§11)          ~600 lines   [depends on 5b]
    └── middleware/token_budget.py, cache.py, rate_limiter.py, circuit_breaker.py,
        tool_approval.py, pii_filter.py, recorder.py
```

**Total new code estimate:** ~6,200 lines across ~45 new files\
**Total modification estimate:** ~500 lines across 8 existing files\
**Current codebase:** ~12,600 lines across 29 source files\
**Post-v5 codebase estimate:** ~19,300 lines across ~74 source files

______________________________________________________________________

## 6. Risk Analysis

### 6.1 Codegen Pipeline Interaction (HIGH RISK)

The biggest architectural risk: v5 needs extension fields on **generated** IR nodes (AgentNode, SequenceNode, ParallelNode). Currently `scripts/ir_generator.py` adds `writes_keys`, `reads_keys`, `produces_type`, `consumes_type` as hardcoded extensions. v5 needs to add more: `content_spec`, `execution_boundary`, `model_selector`, `state_schema`, `edge_semantics`, `merge`.

**Options:**

1. **Extend ir_generator.py** to support a "v5 extensions" config that adds fields to generated nodes. Pro: preserves codegen. Con: more generator complexity.
1. **Make \_ir_generated.py hand-maintained** for the 4 core node types. Pro: simple. Con: breaks the fully-automated codegen story.
1. **Use class inheritance** — generate base nodes, hand-write v5 extensions as subclasses. Pro: clean separation. Con: type union gets complex.

**Recommendation:** Option 1. The IR generator already has the extension pattern. Add a `[ir_extensions]` section to seed.toml that declares additional fields per node type. This is the cleanest approach and preserves the codegen pipeline.

### 6.2 OpenTelemetry Dependency (MEDIUM RISK)

v5 introduces `opentelemetry-api` as a dependency for telemetry enrichment and cost metrics. ADK already depends on OTel internally, but adk-fluent currently doesn't import it directly.

**Risk:** Version conflicts between adk-fluent's OTel dependency and ADK's internal OTel dependency.
**Mitigation:** Use the same OTel version range that google-adk pins. Or make telemetry features optional: `pip install adk-fluent[telemetry]`.

### 6.3 ADK Evaluation API Stability (MEDIUM RISK)

v5's eval harness deeply wraps ADK's `EvalSet`, `EvalCase`, `LocalEvalService`, `MetricEvaluatorRegistry`. These are relatively new ADK APIs.

**Risk:** ADK changes eval API between releases, breaking FluentEvalSuite compilation.
**Mitigation:** The v5 spec already lists these in the compatibility matrix (§17) as "behavioral changes requiring manual review." The eval module should have integration tests that run against the installed ADK version.

### 6.4 Scope Creep: v5 Is a ~50% Codebase Expansion (LOW-MEDIUM)

Going from 12,600 → ~19,300 lines in one spec revision is substantial. Each phase has internal dependencies that create a critical path.

**Mitigation:** The roadmap (§5 above) is phased so each phase produces independently useful, testable features. Phase 5a (typed state) and 5b (telemetry) are the foundation — everything else can be deferred or reordered.

______________________________________________________________________

## 7. The One Structural Decision

The repo currently has a **two-layer architecture**: builders call `.build()` to produce native ADK agents directly. The IR exists (`.to_ir()`) but is optional — you can use adk-fluent without ever touching the IR.

v5 assumes a **three-layer architecture**: builders → IR → backend → ADK. The IR is the central artifact. Features like `estimate_cost()`, `check_all()`, `FluentEvalSuite`, edge semantics, and execution boundaries all operate on the IR, not on builders or ADK agents.

**Current state:** Both paths exist. `.build()` calls ADK constructors directly. `.to_ir()` produces IR nodes. `ADKBackend().compile(node)` compiles IR to ADK. But the `.build()` path is more exercised — most examples use `.build()`, not `.to_ir() → backend.compile()`.

**v5 implication:** The direct `.build()` path stays for simplicity (Level 0 progressive disclosure). But v5 features only work through the IR path. This means users who want typed state checking, cost estimation, modality contracts, eval, or replay must use the IR. This is fine — it's the progressive disclosure principle at work — but the repo needs to make the IR path a first-class citizen with equal documentation and testing.

______________________________________________________________________

## 8. Summary Scorecard

| v5 Section                | Repo State               | Phase           | Est. Lines         |
| ------------------------- | ------------------------ | --------------- | ------------------ |
| §1 Typed State            | 🔴 Not started           | 5a              | 500                |
| §2 Streaming Edges        | 🔴 Not started           | 5e              | 400                |
| §3 Cost Routing           | 🔴 Not started           | 5d              | 600                |
| §4 A2A Interop            | 🔴 Not started           | 5i              | 800                |
| §5 Telemetry              | 🔴 Not started           | 5b              | 300                |
| §6 Evaluation             | 🔴 Not started           | 5g              | 1200               |
| §7 Multi-Modal            | 🔴 Not started           | 5f              | 200                |
| §8 Event Replay           | 🟡 Different arch exists | 5h              | 600                |
| §9 Exec Boundaries        | 🔴 Not started           | 5j              | 500                |
| §10 Contract Checker      | 🟡 Basic version exists  | 5c              | 500                |
| §11 Middleware            | 🟡 2 of 11 exist         | 5k              | 600                |
| §12 Module Structure      | 🟡 Flat, needs nesting   | All phases      | 0 (reorganization) |
| §13–17 Principles/Budgets | ✅ Foundational          | —               | 0                  |
| ADRs                      | 🔴 Not written           | With each phase | docs only          |

**Bottom line:** The foundation is solid and well-tested. Everything in v4 Phases 1–4 is implemented and shipping. v5 is 100% new work — ~6,200 lines across 11 new subpackages — but it builds cleanly on top of the existing architecture without disrupting what's already working.
