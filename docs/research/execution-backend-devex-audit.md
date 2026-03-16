---
orphan: true
---

# Execution Backend DevEx Audit: Definition to Deployment

## Executive Summary

This audit examines the developer experience across all five adk-fluent execution backends (ADK, Temporal, asyncio, Prefect, DBOS) through seven lifecycle phases. It identifies 10 critical gaps and proposes fixes for each.

**Key finding**: ADK is a *full SDK* (owns model calls, tools, state, deploy). Temporal, Prefect, and DBOS are *orchestrators* (own scheduling, durability, crash recovery) that delegate LLM execution to the compute layer. This fundamental distinction drives most of the DevEx gaps.

---

## The SDK vs. Orchestrator Distinction

This is the most important architectural concept to understand:

```
┌────────────────────────────────────────────────────────────┐
│  ADK Backend = FULL SDK                                     │
│                                                             │
│  ADK owns EVERYTHING:                                       │
│  ✓ Model calls (Gemini native, OpenAI via LiteLLM)         │
│  ✓ Tool execution (FunctionTool, AgentTool, MCPToolset)    │
│  ✓ State management (SessionService)                        │
│  ✓ Agent routing (transfer_to_agent)                        │
│  ✓ Packaging (adk deploy)                                   │
│  ✓ Local dev (adk web, adk run)                            │
│  ✓ Observability (events, plugins, traces)                  │
│                                                             │
│  When you use ADK backend, adk-fluent compiles IR to        │
│  native ADK objects and ADK handles everything.             │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│  Temporal / Prefect / DBOS = ORCHESTRATORS                  │
│                                                             │
│  These own SCHEDULING + DURABILITY:                         │
│  ✓ Step ordering (sequential, parallel, conditional)        │
│  ✓ Crash recovery (replay completed steps from cache)       │
│  ✓ Checkpointing (persist progress at each step)            │
│  ✓ Signals (human-in-the-loop via external input)           │
│  ✓ Distribution (run across multiple workers)               │
│                                                             │
│  They DO NOT own:                                           │
│  ✗ Model calls → delegated to ModelProvider (compute layer) │
│  ✗ Tool execution → delegated to ToolRuntime               │
│  ✗ State persistence → delegated to StateStore             │
│                                                             │
│  Why use them? Durability. If a 10-step pipeline crashes    │
│  at step 7, the orchestrator replays steps 1-6 from cache   │
│  (zero LLM cost) and re-executes only step 7+.             │
└────────────────────────────────────────────────────────────┘
```

### Why This Matters for DevEx

| Concern | ADK Backend | Orchestrator Backends |
|---------|------------|----------------------|
| **Model calls** | ADK handles internally | User must provide `ModelProvider` |
| **Tool execution** | ADK's `FunctionTool` | User must provide `ToolRuntime` |
| **State** | ADK's `SessionService` | User must provide `StateStore` |
| **Deploy** | `adk deploy` | Backend-specific (worker, flow, app) |
| **Debug** | ADK events + plugins | Backend's native UI (Temporal UI, Prefect UI) |

---

## Lifecycle Phase Analysis

### Phase 1: DEFINE (Builder API)

**Status: Complete for all backends** — The builder API is backend-agnostic by design.

```python
# This definition works identically across all 5 backends:
pipeline = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic.").writes("findings")
    >> Agent("writer", "gemini-2.5-flash")
    .instruct("Write about {findings}.")
)
```

Backend selection is a separate concern:
```python
pipeline.engine("temporal", client=client)    # Switch to Temporal
pipeline.engine("prefect", work_pool="gpu")   # Switch to Prefect
pipeline.engine("dbos", database_url="...")    # Switch to DBOS
```

| Backend | Define | Notes |
|---------|:------:|-------|
| ADK | Complete | No `.engine()` needed (default) |
| Temporal | Complete | `.engine("temporal", client=..., task_queue=...)` |
| asyncio | Complete | `.engine("asyncio")` |
| Prefect | Complete | `.engine("prefect", work_pool=...)` |
| DBOS | Complete | `.engine("dbos", database_url=...)` |

---

### Phase 2: COMPILE (IR → Backend Artifact)

| Backend | Compile | Output | Quality |
|---------|:-------:|--------|---------|
| ADK | Full | Native ADK objects (`LlmAgent`, `App`) | Production-ready |
| Temporal | Full | `TemporalRunnable` (execution plan) | Working, tested |
| asyncio | Full | `_AsyncioRunnable` (IR wrapper) | Working, interpreter |
| Prefect | Full | `PrefectRunnable` (execution plan) | New, needs testing |
| DBOS | Full | `DBOSRunnable` (execution plan) | New, needs testing |

All 5 backends now compile all 14 IR node types.

---

### Phase 3: TEST

| Backend | Test Support | Gap |
|---------|:----------:|-----|
| ADK | `.test()`, `.mock()`, `.eval()` | None — comprehensive |
| Temporal | Compile-only | **G3**: No end-to-end test without Temporal server |
| asyncio | Mock `ModelProvider` | Adequate for reference impl |
| Prefect | Compile-only | **G4**: No mock Prefect server for testing |
| DBOS | Compile-only | **G4**: No mock DBOS for testing |

---

### Phase 4: PACKAGE

| Backend | Packaging | Artifact | Gap |
|---------|----------|----------|-----|
| ADK | `adk deploy` | Docker image | None |
| Temporal | `temporal_worker.py` codegen | Python worker source | **G9**: Manual Dockerfile needed |
| asyncio | N/A (just Python) | Python script | N/A |
| Prefect | `prefect_worker.py` codegen | Flow source | **G9**: Manual deployment YAML needed |
| DBOS | `dbos_worker.py` codegen | App source | **G9**: Manual dbos.yaml needed |

---

### Phase 5: DEPLOY

| Backend | Deploy Method | Target | Gap |
|---------|:------------:|--------|-----|
| ADK | `adk deploy cloud_run` | Cloud Run, Vertex AI, Agent Engine | None |
| Temporal | Manual worker deploy | Temporal Cloud, self-hosted | **G5, G8**: No adk-fluent deploy command |
| asyncio | Manual | Any container | N/A |
| Prefect | `prefect deploy` | Prefect Cloud, self-hosted | **G5, G8**: No adk-fluent deploy command |
| DBOS | `dbos deploy` | DBOS Cloud, self-hosted | **G5, G8**: No adk-fluent deploy command |

---

### Phase 6: OBSERVE

| Backend | Observability | Gap |
|---------|:------------:|-----|
| ADK | ADK events + M namespace middleware | **G6**: M namespace tested only on ADK |
| Temporal | Temporal UI + workflow history | Native UI is excellent |
| asyncio | Custom (M namespace) | Basic event logging |
| Prefect | Prefect UI + flow run dashboard | Native UI is excellent |
| DBOS | DBOS Dashboard + PostgreSQL queries | Native dashboard available |

---

### Phase 7: DEBUG

| Backend | Debug Tools | Gap |
|---------|:----------:|-----|
| ADK | `.explain()`, `.doctor()`, `.to_mermaid()`, `.diagnose()` | Comprehensive |
| Temporal | `.node_plan` inspection, Temporal UI history | **G10**: No capability mismatch warnings |
| asyncio | Event inspection | Minimal |
| Prefect | `.node_plan` inspection | **G10**: No capability mismatch warnings |
| DBOS | `.node_plan` inspection | **G10**: No capability mismatch warnings |

---

## Gap Inventory

### G1: ADK Backend `run()`/`stream()` Not Implemented

**Severity**: Medium (workaround exists via `_helpers.py`)

The `ADKBackend.run()` and `ADKBackend.stream()` raise `NotImplementedError`. Users must go through `_helpers.py:run_one_shot_async()` which directly imports `InMemoryRunner`.

**Impact**: The five-layer architecture is incomplete — the ADK backend doesn't satisfy the full `Backend` protocol.

**Fix**: Implement `run()`/`stream()` in `ADKBackend` by moving logic from `_helpers.py`.

---

### G2: Asyncio Backend Was Missing 6 IR Node Handlers

**Severity**: High → **RESOLVED**

Previously handled 8/14 nodes. Now handles all 14:
- Added: `GateNode`, `DispatchNode`, `JoinNode`, `TimeoutNode`, `RaceNode`, `MapOverNode`

---

### G3: No End-to-End Test Without Backend Infrastructure

**Severity**: Medium

Temporal requires a running server, Prefect requires a server for durability, DBOS requires PostgreSQL. Unit tests can only verify `compile()`, not `run()`.

**Fix**: Create mock backends for each orchestrator that simulate the run path without real infrastructure. Similar to how asyncio backend serves as a reference.

---

### G4: Prefect and DBOS Backends Were Missing

**Severity**: High → **RESOLVED**

Both backends now implemented with full IR node classification:
- `src/adk_fluent/backends/prefect_backend.py` + `prefect_worker.py`
- `src/adk_fluent/backends/dbos_backend.py` + `dbos_worker.py`

---

### G5: No Backend-Aware Packaging CLI

**Severity**: Medium

`adk deploy` only works for the ADK backend. There's no unified CLI for deploying to Temporal, Prefect, or DBOS.

**Current state**: Users must manually:
1. Generate worker code via codegen module
2. Write their own Dockerfile / deployment config
3. Deploy to their target platform

**Fix**: Add `adk-fluent package --backend temporal` that generates a deployment-ready directory with:
- Worker/flow/app source code
- Dockerfile
- Configuration files (temporal YAML, prefect deployment YAML, dbos.yaml)
- README with deploy instructions

---

### G6: M Namespace Middleware Untested on Non-ADK Backends

**Severity**: Medium

`M.log()`, `M.cost()`, `M.trace()` work via `DefaultRuntime`'s middleware hooks, but these have only been tested with the ADK backend.

**Fix**: Add integration tests verifying middleware fires correctly on asyncio, Temporal, Prefect, and DBOS backends.

---

### G7: Silent Capability Fallbacks

**Severity**: Low

When a user tries streaming on Temporal (`agent.stream("...")`), it silently falls back to batch execution. No warning is emitted.

**Fix**: Emit a `UserWarning` at compile time when the IR uses features the backend doesn't support:
```python
warnings.warn(
    f"Backend '{backend.name}' does not support streaming. "
    f"Falling back to batch execution.",
    UserWarning,
    stacklevel=2,
)
```

---

### G8: No Deployment Scaffold Per Backend

**Severity**: Medium

Each backend has unique deployment requirements:
- **Temporal**: Worker code + Temporal server config + Dockerfile
- **Prefect**: Flow code + deployment YAML + work pool config
- **DBOS**: App code + dbos.yaml + PostgreSQL migration

Users must assemble these manually.

**Fix**: `adk-fluent scaffold --backend temporal` generates a complete deployment project.

---

### G9: Worker Codegen Parity

**Severity**: Low → **RESOLVED**

Worker codegen now exists for all three orchestrator backends:
- `temporal_worker.py` — `generate_worker_code()`
- `prefect_worker.py` — `generate_flow_code()`
- `dbos_worker.py` — `generate_app_code()`

---

### G10: No Capability Negotiation at Builder Level

**Severity**: Medium

`.engine("asyncio")` silently ignores GateNode's HITL capabilities. `.validate()` doesn't check IR node compatibility against engine capabilities.

**Fix**: Extend `.validate()` to cross-reference IR nodes against `EngineCapabilities`:
```python
def validate(self):
    ...
    ir = self.to_ir()
    if self._engine:
        backend = get_backend(self._engine)
        caps = backend.capabilities
        if _has_gate_nodes(ir) and not caps.signals:
            warnings.append(f"IR uses GateNode but {self._engine} doesn't support signals")
        if _has_dispatch_nodes(ir) and not caps.distributed:
            warnings.append(f"IR uses DispatchNode but {self._engine} isn't distributed")
```

---

## Recommendations Priority

| Priority | Gap | Effort | Impact |
|----------|-----|--------|--------|
| **P0** | G2 — asyncio node coverage | Done | All 14 nodes now handled |
| **P0** | G4 — Prefect/DBOS backends | Done | 5 backends available |
| **P0** | G9 — Worker codegen parity | Done | All orchestrators have codegen |
| **P1** | G1 — ADK `run()`/`stream()` | Medium | Completes Backend protocol |
| **P1** | G7 — Capability warnings | Low | Better DevEx, fewer surprises |
| **P1** | G10 — Capability negotiation | Medium | Catches mismatches early |
| **P2** | G3 — Mock backends for testing | Medium | Enables CI without infra |
| **P2** | G6 — Cross-backend middleware tests | Medium | Validates M namespace portability |
| **P2** | G5 — Unified packaging CLI | High | Streamlines deployment |
| **P3** | G8 — Deployment scaffolds | High | Complete DevEx end-to-end |

---

## Appendix: Backend Architecture Deep Dive

### How ADK Backend Works

```
Builder → .to_ir() → IR → ADKBackend.compile() → native ADK objects
                                                      ↓
                     ADK owns everything:        InMemoryRunner
                     - Model calls (Gemini)       - SessionService
                     - Tool execution              - EventLoop
                     - Agent routing               - Plugins
```

ADK is self-contained. The compile step transforms IR into native ADK agent objects (`LlmAgent`, `SequentialAgent`, etc.) that ADK's `InMemoryRunner` executes directly.

### How Orchestrator Backends Work

```
Builder → .to_ir() → IR → TemporalBackend.compile() → execution plan
                                                           ↓
                     Temporal owns orchestration:     Worker process
                     - Step ordering                   - Activities (→ ModelProvider)
                     - Crash recovery                  - Workflow replay
                     - Checkpointing                   - Signal handling
                                                           ↓
                     Compute layer owns execution:     ModelProvider
                     - LLM calls                       - StateStore
                     - Tool execution                  - ToolRuntime
```

Orchestrator backends produce an *execution plan* that describes how to run the pipeline. The actual LLM calls are handled by a `ModelProvider` from the compute layer. This is why orchestrator backends require additional configuration (model_provider, database_url, etc.) that ADK doesn't need.

### Why Use an Orchestrator?

1. **Crash recovery**: 10-step pipeline crashes at step 7 → replay steps 1-6 from cache, re-execute only 7+ (saves 60% LLM cost)
2. **Human-in-the-loop**: Pause execution, wait for human approval, resume
3. **Distribution**: Run steps across multiple workers/machines
4. **Durability**: Pipeline survives process restarts, server reboots
5. **Observability**: Temporal UI / Prefect UI provide rich execution history
