---
orphan: true
---

# Execution Backend Feature Compatibility Matrix

This document provides comprehensive compatibility matrices across all five adk-fluent execution backends: **ADK**, **Temporal**, **asyncio**, **Prefect**, and **DBOS**.

## Backend Overview

| Backend | Status | Install | Infrastructure | Durability Model |
|---------|--------|---------|----------------|-----------------|
| **ADK** | Stable | `pip install adk-fluent` | None | None (ephemeral) |
| **Temporal** | In Development | `pip install adk-fluent[temporal]` | Temporal Server | Workflow replay from event history |
| **asyncio** | In Development | Included by default | None | None (ephemeral) |
| **Prefect** | In Development | `pip install adk-fluent[prefect]` | Prefect Server (optional) | Task result caching + retries |
| **DBOS** | In Development | `pip install adk-fluent[dbos]` | PostgreSQL | Deterministic replay from DB log |

---

## 1. Engine Capabilities Matrix

Every backend declares its capabilities via `EngineCapabilities`. The runtime uses these to validate feature compatibility and provide actionable warnings.

| Capability | ADK | Temporal | asyncio | Prefect | DBOS | Description |
|------------|:---:|:--------:|:-------:|:-------:|:----:|-------------|
| **streaming** | Yes | No | Yes | No | No | Real-time token streaming from LLM |
| **parallel** | Yes | Yes | Yes | Yes | Yes | Concurrent execution of branches |
| **durable** | No | Yes | No | Yes* | Yes | Survives process crash |
| **replay** | No | Yes | No | No | Yes | Deterministic replay from history |
| **checkpointing** | No | Yes | No | Yes* | Yes | Saves progress at each step |
| **signals** | No | Yes | No | Yes | Yes | External input during execution (HITL) |
| **dispatch_join** | Yes | Yes | Yes | Yes | Yes | Fire-and-forget + synchronize |
| **distributed** | No | Yes | No | Yes* | No | Runs across multiple processes/machines |

\* Prefect durability, checkpointing, and distribution require Prefect Server or Prefect Cloud. Without a server, Prefect runs locally without persistence.

### Capability Score

| Backend | Score | Profile |
|---------|-------|---------|
| **Temporal** | 7/8 | Full durability, no streaming |
| **DBOS** | 6/8 | Full durability, no streaming, no distribution |
| **Prefect** | 6/8 | Conditional durability (requires server), no streaming, no replay |
| **ADK** | 4/8 | Streaming + parallel, no durability |
| **asyncio** | 3/8 | Streaming + parallel, zero infrastructure |

---

## 2. IR Node Support Matrix

Every IR node type must map to a backend-specific concept. This matrix shows how each backend implements each node.

| IR Node | ADK | Temporal | asyncio | Prefect | DBOS |
|---------|-----|----------|---------|---------|------|
| **AgentNode** | `LlmAgent` | Activity | `ModelProvider.generate()` | `@task` | `@DBOS.step()` |
| **SequenceNode** | `SequentialAgent` | Workflow body | Sequential await | `@flow` body | `@DBOS.workflow()` body |
| **ParallelNode** | `ParallelAgent` | `asyncio.gather()` in workflow | `asyncio.gather()` | `.submit()` + `.result()` | `asyncio.gather()` in workflow |
| **LoopNode** | `LoopAgent` | `while` loop in workflow | `for` loop | `for` loop in flow | `for` loop in workflow |
| **TransformNode** | `FnAgent` | Inline workflow code | Inline interpreter | Inline flow code | Inline workflow code |
| **TapNode** | `TapAgent` | Inline (observation) | Inline (observation) | Inline (observation) | Inline (observation) |
| **RouteNode** | `FnAgent` + transfer | Inline `if/elif` | Conditional dispatch | `if/elif` in flow | Conditional in workflow |
| **FallbackNode** | `FallbackAgent` | `try/except` chain | `try/except` chain | `try/except` chain | `try/except` chain |
| **GateNode** | `GateAgent` | `workflow.wait_condition()` + Signal | `asyncio.Event` (limited) | `pause_flow_run()` | `DBOS.recv()` |
| **DispatchNode** | `DispatchAgent` | `start_child_workflow()` | `asyncio.create_task()` | `run_deployment()` | `DBOS.start_workflow()` |
| **JoinNode** | `JoinAgent` | Await workflow handle | Await task | Await flow run | Await workflow handle |
| **TimeoutNode** | `TimeoutAgent` | `asyncio.wait_for()` | `asyncio.wait_for()` | `task(timeout_seconds=)` | `asyncio.wait_for()` |
| **RaceNode** | `RaceAgent` | First-completed parallel | `FIRST_COMPLETED` | `FIRST_COMPLETED` | `FIRST_COMPLETED` |
| **MapOverNode** | `MapOverAgent` | Loop + activity per item | Loop + interpret per item | `task.map()` | Loop + step per item |

### Node Coverage Summary

| Backend | Nodes Handled | Coverage |
|---------|:------------:|:--------:|
| **ADK** | 14/14 | 100% |
| **Temporal** | 14/14 | 100% |
| **asyncio** | 14/14 | 100% |
| **Prefect** | 14/14 | 100% |
| **DBOS** | 14/14 | 100% |

---

## 3. Determinism Classification

Each backend classifies IR nodes as deterministic (safe to replay) or non-deterministic (must cache/record results).

| IR Node | Classification | Temporal | Prefect | DBOS |
|---------|---------------|----------|---------|------|
| **AgentNode** | Non-deterministic | Activity (cached) | Task (cached) | Step (recorded) |
| **SequenceNode** | Deterministic | Workflow code | Flow code | Workflow code |
| **ParallelNode** | Deterministic | Workflow code | Flow code | Workflow code |
| **LoopNode** | Deterministic | Workflow code | Flow code | Workflow code |
| **TransformNode** | Deterministic | Inline | Inline | Inline |
| **TapNode** | Deterministic | Inline | Inline | Inline |
| **RouteNode** | Deterministic | Inline | Inline | Inline |
| **FallbackNode** | Deterministic | Workflow code | Flow code | Workflow code |
| **GateNode** | Deterministic* | Signal wait | Pause | Recv |
| **DispatchNode** | Deterministic | Child workflow | Deployment | Child workflow |
| **JoinNode** | Deterministic | Await handle | Await handle | Await handle |
| **TimeoutNode** | Deterministic | Workflow code | Flow code | Workflow code |
| **RaceNode** | Non-deterministic** | Workflow code | Flow code | Workflow code |
| **MapOverNode** | Deterministic | Workflow code | Flow code | Workflow code |

\* GateNode is deterministic in orchestration but waits for non-deterministic external input.
\** RaceNode result depends on execution timing.

---

## 4. Deployment & DevEx Matrix

| Aspect | ADK | Temporal | asyncio | Prefect | DBOS |
|--------|-----|----------|---------|---------|------|
| **Installation** | `pip install adk-fluent` | `pip install adk-fluent[temporal]` | Included | `pip install adk-fluent[prefect]` | `pip install adk-fluent[dbos]` |
| **Infrastructure** | None | Temporal Server | None | Prefect Server (optional) | PostgreSQL |
| **Local development** | `adk web` / `adk run` | `temporal server start-dev` | Just Python | `prefect server start` | `dbos start` |
| **Worker codegen** | N/A (native ADK) | `temporal_worker.py` | N/A (interpreter) | `prefect_worker.py` | `dbos_worker.py` |
| **Cloud deployment** | Cloud Run, Vertex AI, Agent Engine | Temporal Cloud | Any container platform | Prefect Cloud | DBOS Cloud |
| **Observability** | ADK events, M namespace | Temporal UI + history | Custom (M namespace) | Prefect UI + dashboard | DBOS Dashboard + PG |
| **Cost on crash** | Full re-run (all LLM calls) | Replay: cached steps are free | Full re-run | Retry: cached tasks are free | Replay: recorded steps are free |
| **HITL support** | None | Signals + queries | None (limited) | `pause_flow_run()` + `resume` | `DBOS.recv()` |
| **Crash recovery** | None | Automatic from event history | None | Retry with result cache | Automatic from DB log |
| **Multi-tenancy** | Via ADK session service | Via task queues + namespaces | N/A | Via work pools | Via database schemas |
| **Testing** | `.test()`, `.mock()`, `.eval()` | Compile-only + mock client | Mock ModelProvider | Compile-only | Compile-only |
| **Introspection** | `.explain()`, `.doctor()`, `.to_mermaid()` | Plan inspection (`.node_plan`) | Event inspection | Plan inspection | Plan inspection |

---

## 5. When to Use Which Backend

| Use Case | Recommended Backend | Why |
|----------|-------------------|-----|
| **Prototyping / local dev** | ADK (default) | Zero setup, `adk web` for instant UI |
| **Production without durability** | ADK | Battle-tested with Google's ADK ecosystem |
| **Unit testing backend abstraction** | asyncio | No external dependencies, pure Python |
| **Long-running pipelines (hours/days)** | Temporal | Full durability, crash recovery, zero-cost replay |
| **Distributed multi-worker execution** | Temporal or Prefect | Both support worker pools across machines |
| **Team already uses Prefect** | Prefect | Familiar UI/patterns, existing infrastructure |
| **Lightweight durability, minimal infra** | DBOS | Only needs PostgreSQL, no separate server |
| **Human-in-the-loop approvals** | Temporal, Prefect, or DBOS | All three support external signals |
| **Cost-sensitive (crash recovery matters)** | Temporal or DBOS | Replay = zero LLM cost for completed steps |
| **Streaming real-time output** | ADK or asyncio | Only backends with native streaming |

---

## 6. Crash Recovery Comparison

### Scenario: 5-step pipeline crashes at step 4

```
Pipeline: researcher → analyst → writer → reviewer → publisher
                                          ↑
                                      CRASH HERE
```

| Backend | Recovery Behavior | LLM Cost on Recovery |
|---------|-------------------|---------------------|
| **ADK** | Full re-run from step 1 | 5x (all steps re-execute) |
| **asyncio** | Full re-run from step 1 | 5x |
| **Temporal** | Replay steps 1-3 from history, re-execute step 4+ | 2x (only steps 4-5) |
| **Prefect** | Retry flow, steps 1-3 return cached results, re-execute step 4+ | 2x |
| **DBOS** | Replay steps 1-3 from DB log, re-execute step 4+ | 2x |

### Cost savings with 10-step pipeline, crash at step 8

| Backend | Steps re-executed | LLM calls saved |
|---------|:-----------------:|:---------------:|
| **ADK / asyncio** | 10 | 0 |
| **Temporal / DBOS** | 3 | 7 (70% savings) |
| **Prefect** | 3 | 7 (70% savings) |
