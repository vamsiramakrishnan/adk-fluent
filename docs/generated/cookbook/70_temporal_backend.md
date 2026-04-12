# Temporal Backend -- Durable Execution for Agent Pipelines

The Temporal backend compiles IR nodes to Temporal workflows and
activities. If a 10-step pipeline crashes at step 7, Temporal replays
steps 1-6 from cached results (zero LLM cost) and re-executes only
step 7+.

Key mappings:
  AgentNode     → Activity  (non-deterministic: LLM call, cached on replay)
  SequenceNode  → Workflow  (deterministic orchestration)
  ParallelNode  → Workflow  (concurrent activities)
  LoopNode      → Workflow  (iteration with checkpoints)
  TransformNode → Inline    (deterministic, replayed from history)
  GateNode      → Signal    (human-in-the-loop approval)
  DispatchNode  → Child WF  (durable background task)

Usage requires: pip install adk-fluent[temporal]

:::{tip} What you'll learn
How to compose agents into a sequential pipeline.
:::

_Source: `70_temporal_backend.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, Pipeline, FanOut, Loop
from adk_fluent.backends.temporal import TemporalBackend, TemporalRunnable
from adk_fluent.backends.temporal_worker import (
    TemporalWorkerConfig,
    generate_worker_code,
    _collect_activities,
)
from adk_fluent.compile import EngineCapabilities

# 1. Create a Temporal backend (offline mode -- no client needed for compilation)
backend = TemporalBackend(task_queue="research-queue")

# 2. Compile a research pipeline
research_pipeline = (
    Agent("researcher").instruct("Research the topic.").writes("findings")
    >> Agent("analyst").instruct("Analyze the findings: {findings}.").writes("analysis")
    >> Agent("writer").instruct("Write report from {analysis}.")
)

ir = research_pipeline.to_ir()
compiled = backend.compile(ir)

# 3. The compiled result is a TemporalRunnable with an execution plan
assert isinstance(compiled, TemporalRunnable)
plan = compiled.node_plan

# 4. Each node in the plan has determinism annotations
#    Activities (LLM calls) are non-deterministic -- Temporal caches their results.
#    Workflows (orchestration) are deterministic -- Temporal replays from history.
activities = _collect_activities(plan)

# 5. Generate Temporal worker code from the plan
#    This produces Python source with @activity.defn and @workflow.defn
config = TemporalWorkerConfig(
    task_queue="research-queue",
    activity_timeout_seconds=120,
)
code = generate_worker_code(compiled, config)

# 6. The generated code includes activities for each AgentNode
#    and a workflow class that orchestrates them
assert "@activity.defn" in code
assert "@workflow.defn" in code
assert "researcher" in code
assert "analyst" in code
assert "writer" in code

# 7. Parallel pipelines generate concurrent activity calls
fanout_ir = (Agent("web_search").instruct("Search web.") | Agent("paper_search").instruct("Search papers.")).to_ir()
fanout_compiled = backend.compile(fanout_ir)
fanout_code = generate_worker_code(fanout_compiled)
assert "start_activity" in fanout_code  # parallel uses start_activity

# 8. Loops generate iteration code with checkpointing
loop_ir = (
    Loop("refine")
    .step(Agent("writer").instruct("Write."))
    .step(Agent("critic").instruct("Critique."))
    .max_iterations(3)
    .to_ir()
)
loop_compiled = backend.compile(loop_ir)
loop_code = generate_worker_code(loop_compiled)
assert "range(3)" in loop_code

# 9. Builder shorthand: .engine("temporal")
agent = Agent("solver").instruct("Solve.").engine("temporal", task_queue="my-queue")
assert agent._config["_engine"] == "temporal"
assert agent._config["_engine_kwargs"]["task_queue"] == "my-queue"
```
:::
::::

## Equivalence

```python
# Temporal capabilities: durable, replay, distributed
caps = backend.capabilities
assert isinstance(caps, EngineCapabilities)
assert caps.durable is True
assert caps.replay is True
assert caps.checkpointing is True
assert caps.signals is True
assert caps.distributed is True
assert caps.parallel is True
assert caps.streaming is False

# Backend name
assert backend.name == "temporal"

# Plan has the right structure
assert len(activities) == 3  # researcher, analyst, writer
activity_names = [a["name"] for a in activities]
assert "researcher" in activity_names
assert "analyst" in activity_names
assert "writer" in activity_names

# Each activity is non-deterministic (LLM call)
for act in activities:
    assert act["temporal_type"] == "activity"
    assert act["deterministic"] is False
    assert act["checkpoint"] is True

# Generated code is valid Python
compile(code, "<temporal_worker>", "exec")
```
