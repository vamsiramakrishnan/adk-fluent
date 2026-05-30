"""AdkSubagentRunner — a real runner that executes a spec via the ADK engine.

:class:`FakeSubagentRunner` is great for tests and canned-response sandboxes,
but production callers need a runner that actually turns a
:class:`SubagentSpec` into a running model. This module provides that:

- :class:`AdkSubagentRunner` builds a fluent :class:`adk_fluent.Agent` from the
  spec, executes it on the per-call prompt through the same one-shot engine
  ``Agent.ask_async`` uses (an ``InMemoryRunner`` driving a fresh session),
  and folds the text response into a :class:`SubagentResult`.

The runner implements the synchronous :class:`SubagentRunner` Protocol so it
drops straight into :func:`adk_fluent._subagents.make_task_tool`. Because the
task tool calls ``runner.run(...)`` synchronously, the runner owns the
async-to-sync bridge: it spins up its own event loop when called from sync
code and raises :class:`SubagentRunnerError` when called from inside a running
loop (mirroring the rest of adk-fluent's sync/async contract).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from adk_fluent._subagents._result import SubagentResult
from adk_fluent._subagents._runner import SubagentRunnerError
from adk_fluent._subagents._spec import SubagentSpec

__all__ = ["AdkSubagentRunner"]

DEFAULT_MODEL = "gemini-2.5-flash"


class AdkSubagentRunner:
    """Execute a :class:`SubagentSpec` as a real ADK agent.

    The runner is a thin orchestration layer over the fluent ``Agent``
    builder and the package's existing one-shot execution machinery — it
    deliberately does *not* reimplement model invocation.

    Args:
        default_model: Model used when a spec does not pin its own
            ``spec.model``. Defaults to ``"gemini-2.5-flash"``.
        tool_resolver: Optional callable mapping a tool name to a tool
            callable/object. When a spec lists ``tool_names`` and a
            resolver is supplied, each name is resolved and attached to
            the agent via ``.tool()``. Names the resolver cannot resolve
            (returns ``None`` or raises) are skipped gracefully rather
            than failing the whole run.
        agent_factory: Escape hatch for advanced wiring. A callable
            ``(spec) -> Agent`` that fully builds the fluent ``Agent``
            builder. When supplied, ``default_model`` and ``tool_resolver``
            are ignored.

    Notes:
        - ``spec.permission_mode`` and ``spec.max_tokens`` are recorded on
          the agent's metadata for downstream tooling but are not yet
          enforced at the model layer. TODO: thread ``max_tokens`` into a
          ``generate_content_config`` and ``permission_mode`` into a
          permission plugin once a per-subagent runner context is wired.
    """

    def __init__(
        self,
        *,
        default_model: str = DEFAULT_MODEL,
        tool_resolver: Callable[[str], Any] | None = None,
        agent_factory: Callable[[SubagentSpec], Any] | None = None,
    ) -> None:
        self._default_model = default_model
        self._tool_resolver = tool_resolver
        self._agent_factory = agent_factory

    # ------------------------------------------------------------------
    # Agent construction
    # ------------------------------------------------------------------

    def _build_agent(self, spec: SubagentSpec):
        """Build a fluent ``Agent`` builder from ``spec``."""
        if self._agent_factory is not None:
            return self._agent_factory(spec)

        # Imported lazily to avoid a heavy import at module load and to
        # keep this package importable without the full builder graph.
        from adk_fluent import Agent

        agent = (
            Agent(spec.role, spec.model or self._default_model)
            .instruct(spec.instruction)
            .describe(spec.description)
        )

        if spec.tool_names and self._tool_resolver is not None:
            for name in spec.tool_names:
                try:
                    tool = self._tool_resolver(name)
                except Exception:  # noqa: BLE001 — a bad resolver must not abort the run
                    tool = None
                if tool is not None:
                    agent = agent.tool(tool)

        return agent

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_async(
        self,
        spec: SubagentSpec,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> SubagentResult:
        """Async variant of :meth:`run`. Safe to ``await`` from a loop."""
        try:
            text = await self._execute(spec, prompt)
        except Exception as exc:  # noqa: BLE001 — surface failures via the result
            return SubagentResult(
                role=spec.role,
                output="",
                error=str(exc),
            )
        return SubagentResult(role=spec.role, output=text)

    async def _execute(self, spec: SubagentSpec, prompt: str) -> str:
        """Build the agent and run it once on ``prompt``; return the text."""
        from google.adk.runners import InMemoryRunner

        from adk_fluent._helpers import _adk_run_once

        builder = self._build_agent(spec)
        agent = builder.build()
        # App names must start with a letter; ``spec.role`` already does
        # (the spec rejects empty roles). Prefix keeps it unambiguous.
        app_name = f"subagent_{agent.name}"
        runner = InMemoryRunner(agent=agent, app_name=app_name)
        return await _adk_run_once(runner, app_name, prompt)

    def run(
        self,
        spec: SubagentSpec,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> SubagentResult:
        """Execute ``spec`` with ``prompt`` synchronously.

        Implements the :class:`SubagentRunner` Protocol. Drives
        :meth:`run_async` on a private event loop. Raises
        :class:`SubagentRunnerError` if called from inside a running event
        loop — async callers should ``await`` :meth:`run_async` instead.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            raise SubagentRunnerError(
                "AdkSubagentRunner.run() cannot be called from inside a "
                "running event loop. Await runner.run_async(spec, prompt) "
                "instead."
            )

        return asyncio.run(self.run_async(spec, prompt, context))
