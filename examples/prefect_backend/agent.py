"""
Prefect Backend -- Flow Orchestration for Agent Pipelines

The Prefect backend compiles IR nodes to Prefect flows and tasks.
Task results are cached by Prefect, so on retry, completed tasks
return their cached results instead of re-executing (reducing LLM costs).

Key mappings:
  AgentNode     → Task     (non-deterministic: LLM call, cached on retry)
  SequenceNode  → Flow     (sequential task orchestration)
  ParallelNode  → Flow     (concurrent .submit() + wait)
  LoopNode      → Flow     (iteration in flow body)
  TransformNode → Inline   (pure function, no caching)
  GateNode      → Pause    (pause_flow_run for HITL)
  MapOverNode   → task.map (parallel map over list)

Usage requires: pip install adk-fluent[prefect]

Converted from cookbook example: 75_prefect_backend.py

Usage:
    cd examples
    adk web prefect_backend
"""

from adk_fluent import Agent, Pipeline, FanOut, Loop
from adk_fluent.backends.prefect_backend import PrefectBackend, PrefectRunnable
from adk_fluent.backends.prefect_worker import (
    PrefectWorkerConfig,
    generate_flow_code,
    _collect_tasks,
)
from adk_fluent.compile import EngineCapabilities

# 1. Create a Prefect backend (offline mode -- no server needed for compilation)
backend = PrefectBackend(work_pool="gpu-pool")

# 2. Compile a research pipeline
research_pipeline = (
    Agent("researcher").instruct("Research the topic.").writes("findings")
    >> Agent("analyst").instruct("Analyze the findings: {findings}.").writes("analysis")
    >> Agent("writer").instruct("Write report from {analysis}.")
)

ir = research_pipeline.to_ir()
compiled = backend.compile(ir)

# 3. The compiled result is a PrefectRunnable with an execution plan
assert isinstance(compiled, PrefectRunnable)
plan = compiled.node_plan

# 4. Each node has Prefect type annotations
#    Tasks (LLM calls) are cached on retry -- no wasted LLM cost.
#    Flow code (orchestration) runs inline.
tasks = _collect_tasks(plan)

print(f"Tasks (cached on retry): {len(tasks)}")
for t in tasks:
    print(f"  @task {t['name']}: model={t.get('model', 'default')}")

# 5. Check backend capabilities
caps = backend.capabilities
assert isinstance(caps, EngineCapabilities)
assert caps.durable is True      # With Prefect server
assert caps.parallel is True     # .submit() + wait
assert caps.signals is True      # pause/resume for HITL
assert caps.distributed is True  # With work pools
assert caps.streaming is False   # No native streaming
assert caps.replay is False      # Prefect retries, not deterministic replay

print(f"\nCapabilities: {caps}")

# 6. Generate Prefect flow code (write to file for deployment)
config = PrefectWorkerConfig(
    flow_name="research_pipeline",
    work_pool="gpu-pool",
    task_retries=3,
)
flow_code = generate_flow_code(compiled, config)
print(f"\n--- Generated Prefect Flow Code ({len(flow_code.splitlines())} lines) ---")
print(flow_code[:500] + "...")

# 7. Compile via the compile() entry point
from adk_fluent.compile import compile
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

result = compile(ir, backend=backend)
assert result.backend_name == "prefect"
assert result.capabilities.durable is True
print(f"\nCompile result: backend={result.backend_name}, warnings={result.warnings}")

# 8. Parallel pipeline
parallel_pipeline = (
    Agent("web_search").instruct("Search the web.")
    | Agent("paper_search").instruct("Search academic papers.")
)
parallel_ir = parallel_pipeline.to_ir()
parallel_compiled = backend.compile(parallel_ir)
parallel_plan = parallel_compiled.node_plan
print(f"\nParallel plan: {len(parallel_plan)} nodes")
for node in parallel_plan:
    print(f"  {node['node_type']}: {node['name']} ({node['prefect_type']})")

# 9. Loop pipeline
loop_pipeline = (
    Agent("writer").instruct("Write a draft.")
    >> Agent("critic").instruct("Critique the draft.")
) * 3
loop_ir = loop_pipeline.to_ir()
loop_compiled = backend.compile(loop_ir)
loop_plan = loop_compiled.node_plan
print(f"\nLoop plan: {len(loop_plan)} nodes")
for node in loop_plan:
    print(f"  {node['node_type']}: {node['name']} (max_iter={node.get('max_iterations', 'N/A')})")

print("\nAll assertions passed!")

root_agent = loop_plan.build()
