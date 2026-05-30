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

from adk_fluent.backends._utils import safe_identifier as _safe_identifier

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
            _emit_parallel(node, lines, cfg, indent)

        elif node_type == "LoopNode":
            _emit_loop(node, lines, cfg, indent)

        elif node_type == "TransformNode":
            lines.append(f"{prefix}# Transform: {name} (inline, deterministic)")
            lines.append(f"{prefix}# Transform functions are stored in workflow state")
            lines.append("")

        elif node_type == "TapNode":
            lines.append(f"{prefix}# Tap: {name} (observation, no-op in replay)")
            lines.append("")

        elif node_type == "FallbackNode":
            _emit_fallback(node, lines, cfg, indent)

        elif node_type == "RouteNode":
            _emit_route(node, lines, cfg, indent)

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


def _emit_parallel(
    node: dict,
    lines: list[str],
    cfg: TemporalWorkerConfig,
    indent: int,
) -> None:
    """Emit a parallel fan-out: start every branch activity, then gather.

    Branch activities are started concurrently via ``workflow.start_activity``
    (which returns an awaitable handle) and awaited together with
    ``asyncio.gather`` so they run in parallel inside the workflow.
    """
    prefix = "    " * indent
    name = node.get("name", "unknown")
    lines.append(f"{prefix}# Parallel: {name} (concurrent activities via asyncio.gather)")
    children = node.get("children", [])
    activity_children = [
        c for c in children if isinstance(c, dict) and c.get("temporal_type") == "activity"
    ]
    if not activity_children:
        # No directly-parallelizable activities — fall back to sequential walk.
        if children and isinstance(children[0], dict):
            _walk_plan_nodes(children, lines, cfg, indent)
        lines.append("")
        return

    timeout = int(cfg.activity_timeout_seconds)
    handle_names: list[str] = []
    for child in activity_children:
        child_safe = _safe_identifier(child.get("name", "branch"))
        handle_names.append(child_safe)
        lines.append(f"{prefix}{child_safe}_handle = workflow.start_activity(")
        lines.append(f'{prefix}    "{child.get("name", "")}",')
        lines.append(f"{prefix}    args=[prompt, dict(state)],")
        lines.append(f"{prefix}    start_to_close_timeout=timedelta(seconds={timeout}),")
        lines.append(f"{prefix})")
    gathered = ", ".join(f"{h}_handle" for h in handle_names)
    result_vars = ", ".join(f"{h}_result" for h in handle_names)
    # A single handle needs a trailing comma to unpack as a tuple.
    if len(handle_names) == 1:
        result_vars += ","
    lines.append(f"{prefix}{result_vars} = await asyncio.gather({gathered})")
    for h in handle_names:
        lines.append(f'{prefix}state.update({h}_result.get("state", {{}}))')
        lines.append(f'{prefix}results.append({h}_result.get("text", ""))')
    lines.append("")


def _emit_loop(
    node: dict,
    lines: list[str],
    cfg: TemporalWorkerConfig,
    indent: int,
) -> None:
    """Emit a bounded loop.

    The loop is bounded by ``max_iterations`` (defaults to 10 when the IR
    does not specify a limit, matching ``Loop.max_iterations`` semantics).
    An ``until`` predicate, when present in the plan, is checked at the top
    of each iteration and breaks the loop early.
    """
    prefix = "    " * indent
    name = node.get("name", "unknown")
    safe = _safe_identifier(name)
    max_iter = node.get("max_iterations") or 10
    lines.append(f"{prefix}# Loop: {name} (bounded, max {max_iter} iterations)")
    lines.append(f"{prefix}for _iter_{safe} in range({int(max_iter)}):")
    body_indent = indent + 1
    body_prefix = "    " * body_indent
    has_until = node.get("until_key") is not None
    if has_until:
        until_key = node["until_key"]
        lines.append(f"{body_prefix}# until predicate: stop when state signals completion")
        lines.append(f'{body_prefix}if state.get("{until_key}"):')
        lines.append(f"{body_prefix}    break")
    children = node.get("children", [])
    if children and isinstance(children[0], dict):
        _walk_plan_nodes(children, lines, cfg, body_indent)
    else:
        lines.append(f"{body_prefix}pass")
    lines.append("")


def _emit_fallback(
    node: dict,
    lines: list[str],
    cfg: TemporalWorkerConfig,
    indent: int,
) -> None:
    """Emit a fallback cascade as nested ``try`` / ``except`` blocks.

    The first child runs in the outermost ``try``. Each subsequent child is
    attempted inside the ``except`` handler of the previous one, so a failure
    cascades to the next alternative. The final alternative re-raises if it
    too fails.
    """
    name = node.get("name", "unknown")
    prefix = "    " * indent
    lines.append(f"{prefix}# Fallback: {name} (try each alternative in order)")
    children = [c for c in node.get("children", []) if isinstance(c, dict)]
    if not children:
        lines.append(f"{prefix}pass")
        lines.append("")
        return

    def _emit_attempt(idx: int, level: int) -> None:
        attempt_prefix = "    " * level
        lines.append(f"{attempt_prefix}try:")
        _walk_plan_nodes([children[idx]], lines, cfg, level + 1)
        if idx + 1 < len(children):
            lines.append(f"{attempt_prefix}except Exception:")
            _emit_attempt(idx + 1, level + 1)
        else:
            # Last alternative: surface the failure if it also fails.
            lines.append(f"{attempt_prefix}except Exception:")
            lines.append(f"{attempt_prefix}    raise")

    _emit_attempt(0, indent)
    lines.append("")


def _emit_route(
    node: dict,
    lines: list[str],
    cfg: TemporalWorkerConfig,
    indent: int,
) -> None:
    """Emit a deterministic branch keyed on a state value.

    Generates an ``if`` / ``elif`` / ``else`` cascade. Each branch condition
    delegates to a predicate supplied at workflow construction time via
    ``self._route_predicates`` (keyed by route name + branch index), so the
    original routing rules stay authoritative while the generated workflow
    code remains deterministic and replay-safe.
    """
    name = node.get("name", "unknown")
    safe = _safe_identifier(name)
    prefix = "    " * indent
    route_key = node.get("route_key")
    branches = node.get("branches", []) or []
    default_plan = node.get("default")

    key_repr = repr(route_key) if route_key is not None else "None"
    lines.append(f"{prefix}# Route: {name} (deterministic branch on state[{key_repr}])")
    lines.append(f'{prefix}_route_value_{safe} = state.get({key_repr})')

    if not branches and default_plan is None:
        lines.append(f"{prefix}pass")
        lines.append("")
        return

    for i, branch_plan in enumerate(branches):
        keyword = "if" if i == 0 else "elif"
        lines.append(
            f'{prefix}{keyword} self._route_match("{safe}", {i}, _route_value_{safe}, state):'
        )
        if branch_plan and isinstance(branch_plan[0], dict):
            _walk_plan_nodes(branch_plan, lines, cfg, indent + 1)
        else:
            lines.append(f"{prefix}    pass")

    if default_plan is not None:
        if branches:
            lines.append(f"{prefix}else:")
            default_indent = indent + 1
        else:
            # No rules, only a default — emit it unconditionally.
            default_indent = indent
        if default_plan and isinstance(default_plan[0], dict):
            _walk_plan_nodes(default_plan, lines, cfg, default_indent)
        else:
            lines.append(f"{'    ' * default_indent}pass")
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
        "        # Route predicates: {(route_name, branch_index): callable(value, state)}.",
        "        # Populated by the worker from the original routing rules.",
        "        self._route_predicates: dict[tuple[str, int], Any] = {}",
        "",
        '    @workflow.signal(name="approve")',
        "    async def approve(self, gate_name: str) -> None:",
        '        """Signal handler for gate approval."""',
        '        self._state[f"{gate_name}_approved"] = True',
        "",
        "    def _route_match(",
        "        self, route_name: str, branch_index: int, value: Any, state: dict[str, Any]",
        "    ) -> bool:",
        '        """Evaluate a route branch predicate (deterministic, replay-safe)."""',
        "        pred = self._route_predicates.get((route_name, branch_index))",
        "        if pred is None:",
        "            return False",
        "        return bool(pred(value, state))",
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
        from temporalio import activity as _activity  # type: ignore[import-not-found]
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
        from temporalio import (  # type: ignore[import-not-found]  # noqa: F401 — verify temporalio is installed
            workflow as _workflow,
        )
    except ImportError:
        raise ImportError(
            "temporalio is required for create_workflow_class(). Install with: pip install temporalio"
        ) from None

    # Generate the full workflow source (parallel / loop / fallback / route
    # aware) and materialize the class by executing it. This keeps the
    # dynamic worker in lock-step with the codegen output instead of being
    # limited to a flat sequential walk.
    cfg = TemporalWorkerConfig()
    class_lines = _generate_workflow_class(runnable.node_plan, _collect_activities(runnable.node_plan), cfg)
    header = [
        "from __future__ import annotations",
        "import asyncio",
        "from datetime import timedelta",
        "from typing import Any",
        "from temporalio import activity, workflow",
        "",
        "",
    ]
    source = "\n".join(header + class_lines)
    namespace: dict[str, Any] = {}
    exec(compile(source, "<adk_fluent_temporal_workflow>", "exec"), namespace)  # noqa: S102 — generated, trusted source
    return namespace["AgentPipelineWorkflow"]


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
    from temporalio.worker import Worker  # type: ignore[import-not-found]

    activities = await create_activities(runnable, model_provider, tool_runtime)
    workflow_cls = await create_workflow_class(runnable)

    return Worker(
        client,
        task_queue=task_queue,
        workflows=[workflow_cls],
        activities=activities,
    )
