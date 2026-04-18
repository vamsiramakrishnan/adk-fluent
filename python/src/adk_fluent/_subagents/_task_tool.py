"""make_task_tool — produce the ``task(role, prompt, ...)`` tool for parent agents.

The parent LLM calls ``task("researcher", "dig up three papers on X")``
and the tool looks up the spec, delegates to the runner, and returns the
subagent's serialised output. The tool's docstring is rewritten at build
time to enumerate every registered specialist so the parent knows its
options.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from adk_fluent._subagents._registry import SubagentRegistry
from adk_fluent._subagents._runner import SubagentRunner

if TYPE_CHECKING:
    from adk_fluent._harness._event_bus import EventBus

__all__ = ["make_task_tool"]


def make_task_tool(
    registry: SubagentRegistry,
    runner: SubagentRunner,
    *,
    context_provider: Callable[[], dict[str, Any]] | None = None,
    tool_name: str = "task",
    bus: EventBus | None = None,
) -> Callable[..., str]:
    """Return a ``task`` tool callable backed by ``registry`` and ``runner``.

    Args:
        registry: The registry the tool reads specs from.
        runner: The runtime that actually executes a spec.
        context_provider: Optional callable returning the context dict
            to pass to the runner on every invocation. Use this to
            thread the parent agent's state into subagents.
        tool_name: The name the tool function will be exposed under.
        bus: Optional :class:`EventBus`. When provided, the tool emits
            :class:`SubagentStarted` before the runner call and
            :class:`SubagentCompleted` afterwards so consumers on the
            tape can trace dynamic delegation.

    Returns:
        A callable with signature ``task(role: str, prompt: str) -> str``.
        The docstring lists every registered role with its description
        so the parent LLM can pick one.
    """

    def task(role: str, prompt: str) -> str:
        spec = registry.get(role)
        if spec is None:
            known = ", ".join(registry.roles()) or "(none)"
            return f"Error: unknown subagent role {role!r}. Known roles: {known}"
        context = context_provider() if context_provider is not None else None

        if bus is not None:
            from adk_fluent._harness._events import SubagentStarted

            bus.emit(SubagentStarted(role=role, prompt=prompt[:500]))

        started = time.monotonic()
        try:
            result = runner.run(spec, prompt, context)
        except Exception as exc:  # noqa: BLE001
            if bus is not None:
                from adk_fluent._harness._events import SubagentCompleted

                bus.emit(
                    SubagentCompleted(
                        role=role,
                        is_error=True,
                        output_preview=f"Runner raised: {exc}"[:500],
                        duration_ms=round((time.monotonic() - started) * 1000, 1),
                    )
                )
            return f"[{role}:error] Runner raised: {exc}"

        output = result.to_tool_output()
        if bus is not None:
            from adk_fluent._harness._events import SubagentCompleted

            bus.emit(
                SubagentCompleted(
                    role=role,
                    is_error=bool(getattr(result, "is_error", False)),
                    output_preview=output[:500],
                    duration_ms=round((time.monotonic() - started) * 1000, 1),
                )
            )
        return output

    roster = registry.roster()
    task.__doc__ = (
        "Spawn a subagent specialist to handle a sub-task.\n\n"
        "Args:\n"
        "    role: The specialist to invoke. Must be one of the roles below.\n"
        "    prompt: The task description to hand to the specialist.\n\n"
        "Available roles:\n"
        f"{roster}\n"
    )
    task.__name__ = tool_name
    return task
