"""Temporal worker codegen — generates Temporal workflow and activity code from IR.

This module takes a compiled ``TemporalRunnable`` (from the Temporal backend)
and generates the actual ``@workflow.defn`` and ``@activity.defn`` decorated
classes/functions that a Temporal worker can register and execute.

Usage::

    from adk_fluent.backends.temporal import TemporalBackend
    from adk_fluent.backends.temporal_worker import (
        TemporalWorkerConfig,
        generate_worker_code,
        create_worker,
    )

    backend = TemporalBackend(client=client)
    runnable = backend.compile(ir)

    # Option 1: Generate code as string (for inspection / writing to file)
    code = generate_worker_code(runnable)

    # Option 2: Create ready-to-run worker dynamically
    worker = await create_worker(client, runnable, model_provider=my_provider)
    await worker.run()

Requires: ``pip install temporalio``
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "TemporalWorkerConfig",
    "generate_worker_code",
    "create_activities",
    "create_workflow_class",
    "create_worker",
]


@dataclass
class TemporalWorkerConfig:
    """Configuration for Temporal worker generation."""

    task_queue: str = "adk-fluent"
    workflow_name: str = "adk_fluent_agent_workflow"
    activity_timeout_seconds: float = 300.0
    max_concurrent_activities: int = 10
    model_provider: Any = None
    tool_runtime: Any = None
    state_store: Any = None


def generate_worker_code(runnable: Any, config: TemporalWorkerConfig | None = None) -> str:
    """Generate Python source code for a Temporal worker from a compiled plan.

    The generated code includes:
    - Activity functions for each AgentNode (LLM calls)
    - A workflow class that orchestrates the activities
    - A worker setup function

    Args:
        runnable: A ``TemporalRunnable`` from ``TemporalBackend.compile()``.
        config: Worker configuration.

    Returns:
        Python source code as a string.
    """
    cfg = config or TemporalWorkerConfig()
    plan = runnable.node_plan

    # Collect all activity nodes
    activities = _collect_activities(plan)
    lines = [
        '"""Auto-generated Temporal worker for adk-fluent agent pipeline.',
        "",
        f"Task queue: {cfg.task_queue}",
        f"Workflow: {cfg.workflow_name}",
        f"Activities: {len(activities)}",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import asyncio",
        "from datetime import timedelta",
        "from typing import Any",
        "",
        "from temporalio import activity, workflow",
        "from temporalio.client import Client",
        "from temporalio.worker import Worker",
        "",
        "",
        "# ---------------------------------------------------------------------------",
        "# Activities (non-deterministic: LLM calls, tool executions)",
        "# ---------------------------------------------------------------------------",
        "",
    ]

    # Generate activity functions
    for act in activities:
        lines.extend(_generate_activity(act, cfg))
        lines.append("")

    # Generate workflow class
    lines.append("")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("# Workflow (deterministic orchestration)")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("")
    lines.extend(_generate_workflow_class(plan, activities, cfg))

    # Generate worker setup
    lines.append("")
    lines.append("")
    lines.extend(_generate_worker_setup(activities, cfg))

    return "\n".join(lines)


def _collect_activities(plan: list[dict], result: list[dict] | None = None) -> list[dict]:
    """Recursively collect all activity nodes from the plan."""
    if result is None:
        result = []
    for node in plan:
        if node.get("temporal_type") == "activity":
            result.append(node)
        for child in node.get("children", []):
            # Children are already flattened dicts in our format
            if isinstance(child, dict):
                _collect_activities([child], result)
    return result


def _generate_activity(node: dict, cfg: TemporalWorkerConfig) -> list[str]:
    """Generate an @activity.defn function for an AgentNode."""
    name = node["name"]
    safe_name = _safe_identifier(name)
    model = node.get("model", "")
    lines = [
        f'@activity.defn(name="{name}")',
        f"async def {safe_name}_activity(",
        "    prompt: str,",
        "    state: dict[str, Any],",
        "    *,",
        "    model_provider: Any = None,",
        ") -> dict[str, Any]:",
        f'    """Activity for agent "{name}" (model: {model or "default"})."""',
        "    if model_provider is None:",
        f'        raise RuntimeError("No model_provider for activity \\"{name}\\"")',
        "",
        "    from adk_fluent.compute._protocol import GenerateConfig, Message",
        "",
        "    messages = []",
    ]

    # Add instruction handling
    lines.extend(
        [
            "    # Agent instruction is baked into the plan at compile time",
            '    instruction = state.get(f"_instruction_{safe_name}", "")',
            "    if instruction:",
            '        messages.append(Message(role="system", content=instruction))',
            '    messages.append(Message(role="user", content=prompt))',
            "",
            "    result = await model_provider.generate(messages, None, GenerateConfig())",
            "",
            '    output_key = state.get(f"_output_key_{safe_name}")',
            "    if output_key and result.text:",
            "        state[output_key] = result.text",
            "",
            '    return {"text": result.text, "state": state}',
        ]
    )

    # Replace safe_name placeholders with actual name
    return [line.replace("{safe_name}", safe_name) for line in lines]


def _generate_workflow_body(plan: list[dict], cfg: TemporalWorkerConfig, indent: int = 2) -> list[str]:
    """Generate the workflow @workflow.run body from the plan."""
    lines = []
    _walk_plan_nodes(plan, lines, cfg, indent)
    return lines


def _walk_plan_nodes(
    nodes: list[dict],
    lines: list[str],
    cfg: TemporalWorkerConfig,
    indent: int,
) -> None:
    """Recursively generate workflow code from plan nodes."""
    prefix = "    " * indent
    for node in nodes:
        node_type = node.get("node_type", "")
        temporal_type = node.get("temporal_type", "")
        name = node.get("name", "unknown")
        safe = _safe_identifier(name)

        if temporal_type == "activity":
            # Activity call
            timeout = int(cfg.activity_timeout_seconds)
            lines.append(f"{prefix}# Activity: {name}")
            lines.append(f"{prefix}{safe}_result = await workflow.execute_activity(")
            lines.append(f'{prefix}    "{name}",')
            lines.append(f"{prefix}    args=[prompt, state],")
            lines.append(f"{prefix}    start_to_close_timeout=timedelta(seconds={timeout}),")
            lines.append(f"{prefix})")
            lines.append(f'{prefix}state.update({safe}_result.get("state", {{}}))')
            lines.append(f'{prefix}results.append({safe}_result.get("text", ""))')
            lines.append("")

        elif node_type == "SequenceNode":
            lines.append(f"{prefix}# Sequence: {name}")
            children = node.get("children", [])
            if isinstance(children, list) and children and isinstance(children[0], dict):
                _walk_plan_nodes(children, lines, cfg, indent)

        elif node_type == "ParallelNode":
            lines.append(f"{prefix}# Parallel: {name}")
            children = node.get("children", [])
            if children and isinstance(children[0], dict):
                task_names = []
                for i, child in enumerate(children):
                    child_safe = _safe_identifier(child.get("name", f"branch_{i}"))
                    task_names.append(child_safe)
                    if child.get("temporal_type") == "activity":
                        timeout = int(cfg.activity_timeout_seconds)
                        lines.append(f"{prefix}{child_safe}_handle = workflow.start_activity(")
                        lines.append(f'{prefix}    "{child.get("name", "")}",')
                        lines.append(f"{prefix}    args=[prompt, dict(state)],")
                        lines.append(f"{prefix}    start_to_close_timeout=timedelta(seconds={timeout}),")
                        lines.append(f"{prefix})")
                # Await all
                for tn in task_names:
                    lines.append(f"{prefix}{tn}_result = await {tn}_handle")
                    lines.append(f'{prefix}state.update({tn}_result.get("state", {{}}))')
                    lines.append(f'{prefix}results.append({tn}_result.get("text", ""))')
            lines.append("")

        elif node_type == "LoopNode":
            max_iter = node.get("max_iterations", 10)
            lines.append(f"{prefix}# Loop: {name} (max {max_iter} iterations)")
            lines.append(f"{prefix}for _iter_{safe} in range({max_iter}):")
            children = node.get("children", [])
            if children and isinstance(children[0], dict):
                _walk_plan_nodes(children, lines, cfg, indent + 1)
            else:
                lines.append(f"{prefix}    pass")
            lines.append("")

        elif node_type == "TransformNode":
            lines.append(f"{prefix}# Transform: {name} (inline, deterministic)")
            lines.append(f"{prefix}# Transform functions are stored in workflow state")
            lines.append("")

        elif node_type == "TapNode":
            lines.append(f"{prefix}# Tap: {name} (observation, no-op in replay)")
            lines.append("")

        elif node_type == "FallbackNode":
            lines.append(f"{prefix}# Fallback: {name}")
            children = node.get("children", [])
            if children and isinstance(children[0], dict):
                for i, child in enumerate(children):
                    if i == 0:
                        lines.append(f"{prefix}try:")
                    else:
                        lines.append(f"{prefix}except Exception:")
                        lines.append(f"{prefix}    try:")
                    _walk_plan_nodes([child], lines, cfg, indent + 1 + (1 if i > 0 else 0))
                # Close nested try blocks
                for i in range(1, len(children)):
                    exc_indent = "    " * (indent + len(children) - i)
                    lines.append(f"{exc_indent}except Exception:")
                    lines.append(f"{exc_indent}    raise")
            lines.append("")

        elif node_type == "RouteNode":
            lines.append(f"{prefix}# Route: {name} (deterministic routing)")
            lines.append("")

        elif temporal_type == "signal_wait":
            lines.append(f"{prefix}# Gate: {name} (waiting for signal)")
            lines.append(f"{prefix}await workflow.wait_condition(")
            lines.append(f'{prefix}    lambda: state.get("{safe}_approved", False)')
            lines.append(f"{prefix})")
            lines.append("")

        elif temporal_type == "child_workflow":
            lines.append(f"{prefix}# Dispatch: {name} (child workflow)")
            lines.append(f"{prefix}{safe}_handle = await workflow.start_child_workflow(")
            lines.append(f'{prefix}    "{cfg.workflow_name}",')
            lines.append(f"{prefix}    args=[prompt, dict(state)],")
            lines.append(f"{prefix})")
            lines.append("")


def _generate_workflow_class(
    plan: list[dict],
    activities: list[dict],
    cfg: TemporalWorkerConfig,
) -> list[str]:
    """Generate the @workflow.defn class."""
    lines = [
        f'@workflow.defn(name="{cfg.workflow_name}")',
        "class AgentPipelineWorkflow:",
        '    """Auto-generated workflow for adk-fluent agent pipeline."""',
        "",
        "    def __init__(self) -> None:",
        "        self._state: dict[str, Any] = {}",
        "",
        '    @workflow.signal(name="approve")',
        "    async def approve(self, gate_name: str) -> None:",
        '        """Signal handler for gate approval."""',
        '        self._state[f"{gate_name}_approved"] = True',
        "",
        "    @workflow.run",
        "    async def run(self, prompt: str, initial_state: dict[str, Any] | None = None) -> dict[str, Any]:",
        '        """Execute the agent pipeline."""',
        "        state = dict(initial_state or {})",
        "        results: list[str] = []",
        "",
    ]

    # Generate workflow body
    body = _generate_workflow_body(plan, cfg, indent=2)
    lines.extend(body)

    lines.extend(
        [
            '        return {"results": results, "state": state}',
        ]
    )

    return lines


def _generate_worker_setup(activities: list[dict], cfg: TemporalWorkerConfig) -> list[str]:
    """Generate the worker setup function."""
    act_refs = [f"{_safe_identifier(a['name'])}_activity" for a in activities]
    act_list = ", ".join(act_refs) if act_refs else "# no activities"

    lines = [
        "async def create_temporal_worker(",
        "    client: Client,",
        f'    task_queue: str = "{cfg.task_queue}",',
        ") -> Worker:",
        '    """Create a Temporal worker with all registered activities."""',
        "    return Worker(",
        "        client,",
        "        task_queue=task_queue,",
        "        workflows=[AgentPipelineWorkflow],",
        f"        activities=[{act_list}],",
        "    )",
    ]

    return lines


def _safe_identifier(name: str) -> str:
    """Convert a node name to a valid Python identifier."""
    import re

    result = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if result and result[0].isdigit():
        result = f"n_{result}"
    return result or "unnamed"


# ---------------------------------------------------------------------------
# Dynamic worker creation (runtime, not codegen)
# ---------------------------------------------------------------------------


async def create_activities(
    runnable: Any,
    model_provider: Any,
    tool_runtime: Any = None,
) -> list[Any]:
    """Create activity functions from a compiled TemporalRunnable.

    Returns a list of Temporal activity-decorated async functions.
    These can be registered with a Temporal worker.

    Args:
        runnable: A ``TemporalRunnable`` from ``TemporalBackend.compile()``.
        model_provider: A ``ModelProvider`` instance for LLM calls.
        tool_runtime: Optional ``ToolRuntime`` for tool execution.
    """
    try:
        from temporalio import activity as _activity
    except ImportError:
        raise ImportError(
            "temporalio is required for create_activities(). Install with: pip install temporalio"
        ) from None

    plan = runnable.node_plan
    activities_list = _collect_activities(plan)
    result = []

    for act_node in activities_list:
        name = act_node["name"]
        model = act_node.get("model", "")

        # Create a closure-based activity
        async def _activity_fn(
            prompt: str,
            state: dict[str, Any],
            *,
            _name: str = name,
            _model: str = model,
        ) -> dict[str, Any]:
            from adk_fluent.compute._protocol import GenerateConfig, Message

            messages = []
            instruction = state.get(f"_instruction_{_safe_identifier(_name)}", "")
            if instruction:
                messages.append(Message(role="system", content=instruction))
            messages.append(Message(role="user", content=prompt))

            gen_result = await model_provider.generate(messages, None, GenerateConfig())

            output_key = state.get(f"_output_key_{_safe_identifier(_name)}")
            if output_key and gen_result.text:
                state[output_key] = gen_result.text

            return {"text": gen_result.text, "state": state}

        # Decorate with Temporal activity
        _activity_fn.__name__ = f"{_safe_identifier(name)}_activity"
        decorated = _activity.defn(name=name)(_activity_fn)
        result.append(decorated)

    return result


async def create_workflow_class(
    runnable: Any,
) -> type:
    """Create a Temporal workflow class from a compiled TemporalRunnable.

    Returns a class decorated with @workflow.defn that can be registered
    with a Temporal worker.
    """
    try:
        from temporalio import workflow as _workflow
    except ImportError:
        raise ImportError(
            "temporalio is required for create_workflow_class(). Install with: pip install temporalio"
        ) from None

    plan = runnable.node_plan
    activities = _collect_activities(plan)

    # For now, generate a simple sequential workflow
    # More complex patterns (parallel, loop, fallback) would need
    # deeper AST generation or a plan interpreter approach
    activity_names = [a["name"] for a in activities]

    @_workflow.defn(name="adk_fluent_agent_workflow")
    class DynamicAgentWorkflow:
        """Dynamically generated workflow from IR plan."""

        def __init__(self):
            self._state: dict[str, Any] = {}
            self._approved_gates: set[str] = set()

        @_workflow.signal(name="approve")
        async def approve(self, gate_name: str) -> None:
            self._approved_gates.add(gate_name)

        @_workflow.run
        async def run(self, prompt: str, initial_state: dict[str, Any] | None = None) -> dict[str, Any]:
            from datetime import timedelta

            state = dict(initial_state or {})
            results = []

            for act_name in activity_names:
                result = await _workflow.execute_activity(
                    act_name,
                    args=[prompt, state],
                    start_to_close_timeout=timedelta(seconds=300),
                )
                state.update(result.get("state", {}))
                results.append(result.get("text", ""))

            return {"results": results, "state": state}

    return DynamicAgentWorkflow


async def create_worker(
    client: Any,
    runnable: Any,
    *,
    model_provider: Any,
    tool_runtime: Any = None,
    task_queue: str = "adk-fluent",
) -> Any:
    """Create a ready-to-run Temporal worker from a compiled TemporalRunnable.

    This is the highest-level API: it creates activities, workflow class,
    and worker in one call.

    Args:
        client: A ``temporalio.client.Client``.
        runnable: A ``TemporalRunnable`` from ``TemporalBackend.compile()``.
        model_provider: A ``ModelProvider`` instance.
        tool_runtime: Optional ``ToolRuntime``.
        task_queue: Temporal task queue name.

    Returns:
        A ``temporalio.worker.Worker`` ready to be started with ``await worker.run()``.
    """
    from temporalio.worker import Worker

    activities = await create_activities(runnable, model_provider, tool_runtime)
    workflow_cls = await create_workflow_class(runnable)

    return Worker(
        client,
        task_queue=task_queue,
        workflows=[workflow_cls],
        activities=activities,
    )
