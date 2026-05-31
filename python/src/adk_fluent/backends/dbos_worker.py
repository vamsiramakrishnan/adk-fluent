"""DBOS worker codegen — generates DBOS workflow and step code from IR.

This module takes a compiled ``DBOSRunnable`` (from the DBOS backend)
and generates ``@DBOS.workflow()`` and ``@DBOS.step()`` decorated
functions that can be run as a DBOS application.

Usage::

    from adk_fluent.backends.dbos_backend import DBOSBackend
    from adk_fluent.backends.dbos_worker import (
        DBOSWorkerConfig,
        generate_app_code,
    )

    backend = DBOSBackend()
    runnable = backend.compile(ir)

    # Generate code as string (for inspection / writing to file)
    code = generate_app_code(runnable)

Requires: ``pip install dbos``
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adk_fluent.backends._utils import safe_identifier as _safe_identifier

__all__ = [
    "DBOSWorkerConfig",
    "generate_app_code",
]


@dataclass
class DBOSWorkerConfig:
    """Configuration for DBOS application generation."""

    workflow_name: str = "adk_fluent_pipeline"
    database_url: str = "postgresql://postgres:password@localhost:5432/dbos"
    step_timeout_seconds: float = 300.0
    model_provider: Any = None


def generate_app_code(runnable: Any, config: DBOSWorkerConfig | None = None) -> str:
    """Generate Python source code for a DBOS application from a compiled plan.

    The generated code includes:
    - Step functions for each AgentNode (LLM calls)
    - A workflow function that orchestrates the steps
    - Application setup with DBOS initialization

    Args:
        runnable: A ``DBOSRunnable`` from ``DBOSBackend.compile()``.
        config: Worker configuration.

    Returns:
        Python source code as a string.
    """
    cfg = config or DBOSWorkerConfig()
    plan = runnable.node_plan

    # Collect all step nodes
    steps = _collect_steps(plan)
    lines = [
        '"""Auto-generated DBOS application for adk-fluent agent pipeline.',
        "",
        f"Workflow: {cfg.workflow_name}",
        f"Steps: {len(steps)}",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "from dbos import DBOS",
        "",
        "",
        "# ---------------------------------------------------------------------------",
        "# Steps (non-deterministic: LLM calls, durably recorded in PostgreSQL)",
        "# ---------------------------------------------------------------------------",
        "",
    ]

    # Generate step functions
    for step in steps:
        lines.extend(_generate_step(step, cfg))
        lines.append("")

    # Generate workflow function
    lines.append("")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("# Workflow (deterministic orchestration, replayed from DB log)")
    lines.append("# ---------------------------------------------------------------------------")
    lines.append("")
    lines.extend(_generate_workflow(plan, steps, cfg))

    # Generate app setup
    lines.append("")
    lines.append("")
    lines.extend(_generate_app_setup(cfg))

    return "\n".join(lines)


def _collect_steps(plan: list[dict], result: list[dict] | None = None) -> list[dict]:
    """Recursively collect all step nodes from the plan."""
    if result is None:
        result = []
    for node in plan:
        if node.get("dbos_type") == "step":
            result.append(node)
        for child in node.get("children", []):
            if isinstance(child, dict):
                _collect_steps([child], result)
    return result


def _generate_step(node: dict, cfg: DBOSWorkerConfig) -> list[str]:
    """Generate a @DBOS.step() function for an AgentNode."""
    name = node["name"]
    safe_name = _safe_identifier(name)
    model = node.get("model", "")

    return [
        "@DBOS.step()",
        f"async def {safe_name}_step(",
        "    prompt: str,",
        "    state: dict[str, Any],",
        "    *,",
        "    model_provider: Any = None,",
        ") -> dict[str, Any]:",
        f'    """Durable step for agent "{name}" (model: {model or "default"}).',
        "",
        "    This step is durably recorded in PostgreSQL. On workflow recovery,",
        "    completed steps return their cached results (zero LLM cost).",
        '    """',
        "    if model_provider is None:",
        f'        raise RuntimeError("No model_provider for step \\"{name}\\"")',
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


def _generate_workflow(
    plan: list[dict],
    steps: list[dict],
    cfg: DBOSWorkerConfig,
) -> list[str]:
    """Generate the @DBOS.workflow() function."""
    lines = [
        "@DBOS.workflow()",
        f"async def {_safe_identifier(cfg.workflow_name)}(",
        "    prompt: str,",
        "    initial_state: dict[str, Any] | None = None,",
        "    *,",
        "    model_provider: Any = None,",
        ") -> dict[str, Any]:",
        f'    """Durable workflow: {cfg.workflow_name}.',
        "",
        "    Deterministic orchestration replayed from DB log on recovery.",
        "    Steps (LLM calls) return cached results on replay.",
        '    """',
        "    state = dict(initial_state or {})",
        "    results: list[str] = []",
        "",
    ]

    # Generate workflow body
    body = _generate_workflow_body(plan, cfg, indent=1)
    lines.extend(body)

    lines.extend(
        [
            "",
            '    return {"results": results, "state": state}',
        ]
    )

    return lines


def _generate_workflow_body(plan: list[dict], cfg: DBOSWorkerConfig, indent: int = 1) -> list[str]:
    """Generate the workflow body from the plan."""
    lines: list[str] = []
    prefix = "    " * indent

    for node in plan:
        node_type = node.get("node_type", "")
        dbos_type = node.get("dbos_type", "")
        name = node.get("name", "unknown")
        safe = _safe_identifier(name)

        if dbos_type == "step":
            lines.append(f"{prefix}# Step: {name} (durably recorded)")
            lines.append(f"{prefix}{safe}_result = await {safe}_step(")
            lines.append(f"{prefix}    prompt, state, model_provider=model_provider")
            lines.append(f"{prefix})")
            lines.append(f'{prefix}state.update({safe}_result.get("state", {{}}))')
            lines.append(f'{prefix}results.append({safe}_result.get("text", ""))')
            lines.append("")

        elif node_type == "SequenceNode":
            lines.append(f"{prefix}# Sequence: {name}")
            children = node.get("children", [])
            if children and isinstance(children[0], dict):
                body = _generate_workflow_body(children, cfg, indent)
                lines.extend(body)

        elif node_type == "ParallelNode":
            lines.append(f"{prefix}# Parallel: {name} (asyncio.gather)")
            lines.append(f"{prefix}import asyncio")
            children = node.get("children", [])
            if children and isinstance(children[0], dict):
                step_children = [c for c in children if c.get("dbos_type") == "step"]
                coro_names = []
                for c in step_children:
                    cs = _safe_identifier(c.get("name", "unknown"))
                    coro_names.append(f"{cs}_coro")
                    lines.append(f"{prefix}{cs}_coro = {cs}_step(")
                    lines.append(f"{prefix}    prompt, dict(state), model_provider=model_provider")
                    lines.append(f"{prefix})")
                if coro_names:
                    gathered = ", ".join(coro_names)
                    lines.append(f"{prefix}parallel_results = await asyncio.gather({gathered})")
                    lines.append(f"{prefix}for r in parallel_results:")
                    lines.append(f'{prefix}    state.update(r.get("state", {{}}))')
                    lines.append(f'{prefix}    results.append(r.get("text", ""))')
            lines.append("")

        elif node_type == "LoopNode":
            max_iter = node.get("max_iterations", 10)
            lines.append(f"{prefix}# Loop: {name} (max {max_iter} iterations)")
            lines.append(f"{prefix}for _iter_{safe} in range({max_iter}):")
            children = node.get("children", [])
            if children and isinstance(children[0], dict):
                body = _generate_workflow_body(children, cfg, indent + 1)
                lines.extend(body)
            else:
                lines.append(f"{prefix}    pass")
            lines.append("")

        elif dbos_type == "recv":
            lines.append(f"{prefix}# Gate: {name} (waiting for external signal via DBOS.recv)")
            lines.append(f'{prefix}signal = await DBOS.recv("{safe}_signal", timeout_seconds=3600)')
            lines.append("")

        elif dbos_type == "child_workflow":
            lines.append(f"{prefix}# Dispatch: {name} (child workflow)")
            lines.append(f"{prefix}{safe}_handle = await DBOS.start_workflow(")
            lines.append(f"{prefix}    {_safe_identifier(cfg.workflow_name)},")
            lines.append(f"{prefix}    prompt, dict(state), model_provider=model_provider")
            lines.append(f"{prefix})")
            lines.append("")

        elif node_type == "TransformNode":
            lines.append(f"{prefix}# Transform: {name} (inline, deterministic)")
            lines.append("")

        elif node_type == "TapNode":
            lines.append(f"{prefix}# Tap: {name} (observation, no-op in replay)")
            lines.append("")

        elif node_type == "FallbackNode":
            lines.append(f"{prefix}# Fallback: {name} (try each alternative in order)")
            children = [c for c in node.get("children", []) if isinstance(c, dict)]
            if children:
                _emit_fallback_cascade(lines, children, cfg, indent)
            else:
                lines.append(f"{prefix}pass")
            lines.append("")

        elif node_type == "RouteNode":
            _emit_route_branch(lines, node, cfg, indent)

    return lines


def _emit_fallback_cascade(
    lines: list[str],
    children: list[dict],
    cfg: DBOSWorkerConfig,
    indent: int,
) -> None:
    """Emit a nested try/except fallback cascade across alternatives."""

    def _attempt(idx: int, level: int) -> None:
        attempt_prefix = "    " * level
        lines.append(f"{attempt_prefix}try:")
        lines.extend(_generate_workflow_body([children[idx]], cfg, level + 1))
        lines.append(f"{attempt_prefix}except Exception:")
        if idx + 1 < len(children):
            _attempt(idx + 1, level + 1)
        else:
            lines.append(f"{attempt_prefix}    raise")

    _attempt(0, indent)


def _emit_route_branch(
    lines: list[str],
    node: dict,
    cfg: DBOSWorkerConfig,
    indent: int,
) -> None:
    """Emit an if/elif/else cascade keyed on the route state value."""
    prefix = "    " * indent
    name = node.get("name", "unknown")
    safe = _safe_identifier(name)
    route_key = node.get("route_key")
    branches = node.get("branches", []) or []
    default_plan = node.get("default")
    key_repr = repr(route_key) if route_key is not None else "None"
    lines.append(f"{prefix}# Route: {name} (deterministic branch on state[{key_repr}])")
    lines.append(f"{prefix}_route_value_{safe} = state.get({key_repr})")

    if not branches and default_plan is None:
        lines.append(f"{prefix}pass")
        lines.append("")
        return

    lines.append(f"{prefix}# The runtime sets state['_route_{safe}_branch'] to the")
    lines.append(f"{prefix}# matching rule index (or -1 for the default) from the")
    lines.append(f"{prefix}# original Route rules, keyed on _route_value_{safe}.")
    for i, branch_plan in enumerate(branches):
        keyword = "if" if i == 0 else "elif"
        lines.append(f'{prefix}{keyword} state.get("_route_{safe}_branch") == {i}:')
        if branch_plan and isinstance(branch_plan[0], dict):
            lines.extend(_generate_workflow_body(branch_plan, cfg, indent + 1))
        else:
            lines.append(f"{prefix}    pass")

    if default_plan is not None:
        default_indent = indent + 1 if branches else indent
        if branches:
            lines.append(f"{prefix}else:")
        if default_plan and isinstance(default_plan[0], dict):
            lines.extend(_generate_workflow_body(default_plan, cfg, default_indent))
        else:
            lines.append(f"{'    ' * default_indent}pass")
    lines.append("")


def _generate_app_setup(cfg: DBOSWorkerConfig) -> list[str]:
    """Generate DBOS application setup code."""
    return [
        "# ---------------------------------------------------------------------------",
        "# Application setup",
        "# ---------------------------------------------------------------------------",
        "",
        "",
        'if __name__ == "__main__":',
        "    DBOS()",
        "    # Run: dbos start",
        f'    # Or:  DBOS.launch("{_safe_identifier(cfg.workflow_name)}", ...)',
    ]
