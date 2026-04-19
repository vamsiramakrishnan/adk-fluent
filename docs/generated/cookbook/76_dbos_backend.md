# DBOS Backend -- Durable Functions for Agent Pipelines

The DBOS backend compiles IR nodes to DBOS durable workflows and steps
backed by PostgreSQL. Steps (LLM calls) are durably recorded -- on
recovery, completed steps return their cached results (zero LLM cost).

Key mappings:
  AgentNode     → @DBOS.step()    (non-deterministic, durably recorded in PG)
  SequenceNode  → @DBOS.workflow() (deterministic, replayed from DB log)
  ParallelNode  → asyncio.gather   (concurrent steps in workflow)
  LoopNode      → for loop         (iteration in workflow body)
  TransformNode → Inline           (deterministic, replayed)
  GateNode      → DBOS.recv()      (external signal for HITL)
  DispatchNode  → DBOS.start_workflow() (child workflow)

Key difference from Temporal: DBOS requires only PostgreSQL (no separate
server process). Lighter infrastructure, similar durability guarantees.

Usage requires: pip install adk-fluent[dbos]

:::{tip} What you'll learn
How to compose agents into a sequential pipeline.
:::

_Source: `76_dbos_backend.py`_

```python
from adk_fluent import Agent, Pipeline, FanOut, Loop
from adk_fluent.backends.dbos_backend import DBOSBackend, DBOSRunnable
from adk_fluent.backends.dbos_worker import (
    DBOSWorkerConfig,
    generate_app_code,
    _collect_steps,
)
from adk_fluent.compile import EngineCapabilities

# 1. Create a DBOS backend (offline mode -- no database needed for compilation)
backend = DBOSBackend(database_url="postgresql://localhost:5432/agents")

# 2. Compile a research pipeline
research_pipeline = (
    Agent("researcher").instruct("Research the topic.").writes("findings")
    >> Agent("analyst").instruct("Analyze the findings: {findings}.").writes("analysis")
    >> Agent("writer").instruct("Write report from {analysis}.")
)

ir = research_pipeline.to_ir()
compiled = backend.compile(ir)

# 3. The compiled result is a DBOSRunnable with an execution plan
assert isinstance(compiled, DBOSRunnable)
plan = compiled.node_plan

# 4. Each node has DBOS type annotations
#    Steps (LLM calls) are durably recorded in PostgreSQL.
#    Workflow code (orchestration) is replayed from DB log.
steps = _collect_steps(plan)

print(f"Steps (durably recorded in PG): {len(steps)}")
for s in steps:
    print(f"  @DBOS.step() {s['name']}: model={s.get('model', 'default')}")

# 5. Check backend capabilities
caps = backend.capabilities
assert isinstance(caps, EngineCapabilities)
assert caps.durable is True  # PostgreSQL-backed
assert caps.replay is True  # Deterministic replay from DB log
assert caps.parallel is True  # asyncio.gather in workflow
assert caps.signals is True  # DBOS.recv() for HITL
assert caps.checkpointing is True  # Per-step recording
assert caps.distributed is False  # Single-process (PG stores state)
assert caps.streaming is False  # No native streaming

print(f"\nCapabilities: {caps}")

# 6. Generate DBOS application code (write to file for deployment)
config = DBOSWorkerConfig(
    workflow_name="research_pipeline",
    database_url="postgresql://localhost:5432/agents",
)
app_code = generate_app_code(compiled, config)
print(f"\n--- Generated DBOS App Code ({len(app_code.splitlines())} lines) ---")
print(app_code[:500] + "...")

# 7. Compile via the compile() entry point
from adk_fluent.compile import compile

result = compile(ir, backend=backend)
assert result.backend_name == "dbos"
assert result.capabilities.durable is True
assert result.capabilities.replay is True
print(f"\nCompile result: backend={result.backend_name}, warnings={result.warnings}")

# 8. Compare DBOS vs Temporal capabilities
from adk_fluent.backends.temporal import TemporalBackend

temporal = TemporalBackend()
dbos_caps = backend.capabilities
temporal_caps = temporal.capabilities

print("\n--- DBOS vs Temporal ---")
print(f"  durable:     DBOS={dbos_caps.durable}  Temporal={temporal_caps.durable}")
print(f"  replay:      DBOS={dbos_caps.replay}  Temporal={temporal_caps.replay}")
print(f"  distributed: DBOS={dbos_caps.distributed}  Temporal={temporal_caps.distributed}")
print("  Infra:       DBOS=PostgreSQL only  Temporal=Temporal Server")

# 9. Crash recovery scenario
print("\n--- Crash Recovery Scenario ---")
print("Pipeline: researcher → analyst → writer (3 steps)")
print("Crash at step 3 (writer):")
print("  DBOS replays steps 1-2 from DB log (zero LLM cost)")
print("  Only step 3 re-executes (1 LLM call instead of 3)")
print("  Cost savings: 67%")

print("\nAll assertions passed!")
```
