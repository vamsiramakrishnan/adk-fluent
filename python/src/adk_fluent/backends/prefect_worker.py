"""Prefect worker codegen — generates Prefect flow and task code from IR.

This module takes a compiled ``PrefectRunnable`` (from the Prefect backend)
and generates ``@flow`` and ``@task`` decorated functions that can be
registered as Prefect deployments.

Usage::

    from adk_fluent.backends.prefect_backend import PrefectBackend
    from adk_fluent.backends.prefect_worker import (
        PrefectWorkerConfig,
        generate_flow_code,
    )

    backend = PrefectBackend()
    runnable = backend.compile(ir)

    # Generate code as string (for inspection / writing to file)
    code = generate_flow_code(runnable)

Requires: ``pip install prefect``
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adk_fluent.backends._utils import safe_identifier as _safe_identifier

__all__ = [
    "PrefectWorkerConfig",
    "generate_flow_code",
]


@dataclass
class PrefectWorkerConfig:
    """Configuration for Prefect flow generation."""

    flow_name: str = "adk_fluent_pipeline"
    work_pool: str | None = None
    task_retries: int = 2
    task_timeout_seconds: float = 300.0
    result_persistence: bool = True
    model_provider: Any = None


def generate_flow_code(runnable: Any, config: PrefectWorkerConfig | None = None) -> str:
    """Generate Python source code for a Prefect flow from a compiled plan.

    The generated code includes:
    - Task functions for each AgentNode (LLM calls)
    - A flow function that orchestrates the tasks
    - A deployment setup function

    Args:
        runnable: A ``PrefectRunnable`` from ``PrefectBackend.compile()``.
        config: Worker configuration.

    Returns:
        Python source code as a string.
    """
    cfg = config or PrefectWorkerConfig()
    plan = runnable.node_plan

    # Collect all task nodes
    tasks = _collect_tasks(plan)
    lines = [
        '"""Auto-generated Prefect flow for adk-fluent agent pipeline.',
        "",
        f"Flow: {cfg.flow_name}",
        f"Tasks: {len(tasks)}",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "from prefect import flow, task",
        "",
        "",
        "# ---------------------------------------------------------------------------",
        "# Tasks (non-deterministic: LLM calls, tool executions)",
        "# ---------------------------------------------------------------------------",
        "",
    ]

    # Generate task functions
    for t in tasks:
        lines.extend(_generate_task(t, cfg))
        lines.append("")

    # Generate flow function
    lines.append("")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("# Flow (orchestration)")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("")
    lines.extend(_generate_flow(plan, tasks, cfg))

    # Generate deployment setup
    lines.append("")
    lines.append("")
    lines.extend(_generate_deployment_setup(cfg))

    return "\n".join(lines)


def _collect_tasks(plan: list[dict], result: list[dict] | None = None) -> list[dict]:
    """Recursively collect all task nodes from the plan."""
    if result is None:
        result = []
    for node in plan:
        if node.get("prefect_type") == "task":
            result.append(node)
        for child in node.get("children", []):
            if isinstance(child, dict):
                _collect_tasks([child], result)
    return result


def _generate_task(node: dict, cfg: PrefectWorkerConfig) -> list[str]:
    """Generate a @task function for an AgentNode."""
    name = node["name"]
    safe_name = _safe_identifier(name)
    model = node.get("model", "")
    retries = cfg.task_retries

    return [
        f"@task(name={name!r}, retries={retries}, persist_result={cfg.result_persistence!r})",
        f"async def {safe_name}_task(",
        "    prompt: str,",
        "    state: dict[str, Any],",
        "    *,",
        "    model_provider: Any = None,",
        ") -> dict[str, Any]:",
        f'    """Task for agent "{name}" (model: {model or "default"})."""',
        "    if model_provider is None:",
        f'        raise RuntimeError("No model_provider for task \\"{name}\\"")',
        "",
        "    from adk_fluent.compute._protocol import GenerateConfig, Message",
        "",
        "    messages = []",
        f'    instruction = state.get("_instruction_{safe_name}", "")',
        "    if instruction:",
        '        messages.append(Message(role="system", content=instruction))',
        '    messages.append(Message(role="user", content=prompt))',
        "",
        "    result = await model_provider.generate(messages, None, GenerateConfig())",
        "",
        f'    output_key = state.get("_output_key_{safe_name}")',
        "    if output_key and result.text:",
        "        state[output_key] = result.text",
        "",
        '    return {"text": result.text, "state": state}',
    ]


def _generate_flow(
    plan: list[dict],
    tasks: list[dict],
    cfg: PrefectWorkerConfig,
) -> list[str]:
    """Generate the @flow function."""
    lines = [
        f"@flow(name={cfg.flow_name!r})",
        "async def agent_pipeline_flow(",
        "    prompt: str,",
        "    initial_state: dict[str, Any] | None = None,",
        "    *,",
        "    model_provider: Any = None,",
        ") -> dict[str, Any]:",
        '    """Execute the agent pipeline as a Prefect flow."""',
        "    state = dict(initial_state or {})",
        "    results: list[str] = []",
        "",
    ]

    # Generate flow body
    body = _generate_flow_body(plan, cfg, indent=1)
    lines.extend(body)

    lines.extend(
        [
            "",
            '    return {"results": results, "state": state}',
        ]
    )

    return lines


def _generate_flow_body(plan: list[dict], cfg: PrefectWorkerConfig, indent: int = 1) -> list[str]:
    """Generate the flow body from the plan."""
    lines: list[str] = []
    prefix = "    " * indent

    for node in plan:
        node_type = node.get("node_type", "")
        prefect_type = node.get("prefect_type", "")
        name = node.get("name", "unknown")
        safe = _safe_identifier(name)

        if prefect_type == "task":
            lines.append(f"{prefix}# Task: {name}")
            lines.append(f"{prefix}{safe}_result = await {safe}_task(")
            lines.append(f"{prefix}    prompt, state, model_provider=model_provider")
            lines.append(f"{prefix})")
            lines.append(f'{prefix}state.update({safe}_result.get("state", {{}}))')
            lines.append(f'{prefix}results.append({safe}_result.get("text", ""))')
            lines.append("")

        elif node_type == "SequenceNode":
            lines.append(f"{prefix}# Sequence: {name}")
            children = node.get("children", [])
            if children and isinstance(children[0], dict):
                _extend_flow_body(lines, children, cfg, indent)

        elif node_type == "ParallelNode":
            lines.append(f"{prefix}# Parallel: {name} (submit + wait)")
            children = node.get("children", [])
            if children and isinstance(children[0], dict):
                task_children = [c for c in children if c.get("prefect_type") == "task"]
                for c in task_children:
                    cs = _safe_identifier(c.get("name", "unknown"))
                    lines.append(f"{prefix}{cs}_future = {cs}_task.submit(")
                    lines.append(f"{prefix}    prompt, dict(state), model_provider=model_provider")
                    lines.append(f"{prefix})")
                for c in task_children:
                    cs = _safe_identifier(c.get("name", "unknown"))
                    lines.append(f"{prefix}{cs}_result = {cs}_future.result()")
                    lines.append(f'{prefix}state.update({cs}_result.get("state", {{}}))')
                    lines.append(f'{prefix}results.append({cs}_result.get("text", ""))')
            lines.append("")

        elif node_type == "LoopNode":
            max_iter = node.get("max_iterations", 10)
            lines.append(f"{prefix}# Loop: {name} (max {max_iter} iterations)")
            lines.append(f"{prefix}for _iter_{safe} in range({max_iter}):")
            children = node.get("children", [])
            if children and isinstance(children[0], dict):
                _extend_flow_body(lines, children, cfg, indent + 1)
            else:
                lines.append(f"{prefix}    pass")
            lines.append("")

        elif node_type == "FallbackNode":
            lines.append(f"{prefix}# Fallback: {name}")
            children = node.get("children", [])
            if children and isinstance(children[0], dict):
                for i, child in enumerate(children):
                    kw = "try" if i == 0 else "except Exception"
                    lines.append(f"{prefix}{kw}:")
                    _extend_flow_body(lines, [child], cfg, indent + 1)
            lines.append("")

        elif prefect_type == "pause":
            lines.append(f"{prefix}# Gate: {name} (pause for human approval)")
            lines.append(f"{prefix}from prefect.input import RunInput")
            lines.append(f"{prefix}await pause_flow_run(wait_for_input=RunInput)")
            lines.append("")

        elif node_type == "TransformNode":
            lines.append(f"{prefix}# Transform: {name} (inline, deterministic)")
            lines.append("")

        elif node_type == "TapNode":
            lines.append(f"{prefix}# Tap: {name} (observation, no-op)")
            lines.append("")

    return lines


def _extend_flow_body(
    lines: list[str],
    children: list[dict],
    cfg: PrefectWorkerConfig,
    indent: int,
) -> None:
    """Helper to extend lines with child flow body."""
    body = _generate_flow_body(children, cfg, indent)
    lines.extend(body)


def _generate_deployment_setup(cfg: PrefectWorkerConfig) -> list[str]:
    """Generate deployment setup code."""
    lines = [
        "# ---------------------------------------------------------------------------",
        "# Deployment setup",
        "# ---------------------------------------------------------------------------",
        "",
        "",
        "def create_deployment(",
        f'    name: str = "{cfg.flow_name}",',
    ]
    if cfg.work_pool:
        lines.append(f'    work_pool: str = "{cfg.work_pool}",')
    else:
        lines.append('    work_pool: str = "default",')
    lines.extend(
        [
            "):",
            '    """Create a Prefect deployment for this flow."""',
            "    return agent_pipeline_flow.to_deployment(",
            "        name=name,",
            "        work_pool_name=work_pool,",
            "    )",
        ]
    )

    return lines
