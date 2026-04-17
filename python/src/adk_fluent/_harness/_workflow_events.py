"""Workflow lifecycle event emission — Phase C.

``WorkflowLifecyclePlugin`` is an ADK :class:`BasePlugin` that bridges
ADK's per-agent callbacks into typed harness events on an
:class:`EventBus`. One install covers every agent in the invocation
tree — Pipeline, Loop, FanOut, LlmAgent, RemoteAgent — without touching
the auto-generated ``workflow.py``.

Emission rules:

- ``before_agent_callback`` fires once per agent per entry; we emit
  :class:`StepStarted`. The agent's class name (``SequentialAgent``,
  ``LoopAgent``, ``ParallelAgent``, ``LlmAgent``, ...) is stamped as
  ``agent_type`` so consumers can distinguish workflow orchestrators
  from leaf agents.
- ``after_agent_callback`` emits :class:`StepCompleted` with
  ``duration_ms`` computed from a monotonic timer keyed by agent name.
- For a ``LoopAgent``, the plugin also emits
  :class:`IterationStarted` / :class:`IterationCompleted` each time the
  loop body runs (detected by a child agent re-entering with the same
  parent name).
- For a ``ParallelAgent``, child agents are tagged as
  :class:`BranchStarted` / :class:`BranchCompleted` so downstream
  consumers can correlate parallel execution.

The plugin is independent of the durable tape: wire it to a bus, and
subscribe the tape (or any other consumer) to the bus. Deterministic
seq ordering comes from the tape, not from this plugin.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from google.adk.plugins.base_plugin import BasePlugin

from adk_fluent._harness._events import (
    BranchCompleted,
    BranchStarted,
    IterationCompleted,
    IterationStarted,
    StepCompleted,
    StepStarted,
)

if TYPE_CHECKING:
    from adk_fluent._harness._event_bus import EventBus

__all__ = ["WorkflowLifecyclePlugin"]


class WorkflowLifecyclePlugin(BasePlugin):
    """Emit typed lifecycle events for every agent in the invocation tree.

    Args:
        bus: The :class:`EventBus` to emit events on. Every consumer —
            tape, renderer, signal reactor — subscribes to the bus.
        emit_step_events: If True (default), emit
            :class:`StepStarted` / :class:`StepCompleted` for every
            agent. Set False to suppress leaf-level chatter and keep
            only iteration/branch events.
        emit_iteration_events: If True (default), detect ``LoopAgent``
            re-entries and emit :class:`IterationStarted` /
            :class:`IterationCompleted`.
        emit_branch_events: If True (default), tag ``ParallelAgent``
            children as :class:`BranchStarted` / :class:`BranchCompleted`.
        name: ADK plugin display name.
    """

    def __init__(
        self,
        bus: EventBus,
        *,
        emit_step_events: bool = True,
        emit_iteration_events: bool = True,
        emit_branch_events: bool = True,
        name: str = "adkf_workflow_lifecycle",
    ) -> None:
        super().__init__(name=name)
        self._bus = bus
        self._emit_step = emit_step_events
        self._emit_iter = emit_iteration_events
        self._emit_branch = emit_branch_events
        # Monotonic timers keyed by agent name — lets after_agent_callback
        # compute duration without carrying state on the callback context.
        self._start_times: dict[str, float] = {}
        # Per-loop iteration counters. Incremented each time a LoopAgent's
        # first child re-enters before_agent_callback with the same parent.
        self._loop_counters: dict[str, int] = {}
        self._loop_current_child: dict[str, str] = {}
        # Branch index counters per ParallelAgent instance.
        self._branch_indices: dict[str, dict[str, int]] = {}
        self._branch_start_times: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _agent_type(agent: Any) -> str:
        return type(agent).__name__ if agent is not None else ""

    @staticmethod
    def _agent_name(agent: Any, ctx: Any) -> str:
        name = getattr(agent, "name", None)
        if name:
            return str(name)
        return str(getattr(ctx, "agent_name", "") or "anon")

    @staticmethod
    def _parent_name(agent: Any, ctx: Any) -> str:
        parent = getattr(agent, "parent_agent", None)
        if parent is not None:
            return str(getattr(parent, "name", ""))
        # Fallback — ADK callback contexts sometimes expose this path.
        return str(getattr(ctx, "parent_agent_name", "") or "")

    # ------------------------------------------------------------------
    # ADK hooks
    # ------------------------------------------------------------------

    async def before_agent_callback(
        self,
        *,
        agent: Any = None,
        callback_context: Any,
    ) -> Any:
        name = self._agent_name(agent, callback_context)
        atype = self._agent_type(agent)
        parent = self._parent_name(agent, callback_context)
        now = time.monotonic()
        self._start_times[name] = now

        # Iteration detection for LoopAgent parents — when a child's
        # before callback re-fires with the same parent, that's a new
        # iteration.
        if self._emit_iter and parent and self._is_loop_parent(agent):
            prev_child = self._loop_current_child.get(parent)
            if prev_child is None or prev_child == name:
                # Seeing the first child again → new iteration.
                iteration = self._loop_counters.get(parent, 0)
                self._loop_counters[parent] = iteration + 1
                self._loop_current_child[parent] = name
                self._bus.emit(IterationStarted(loop_name=parent, iteration=iteration))

        # Branch tagging for ParallelAgent parents.
        if self._emit_branch and parent and self._is_parallel_parent(agent):
            indices = self._branch_indices.setdefault(parent, {})
            if name not in indices:
                indices[name] = len(indices)
            idx = indices[name]
            self._branch_start_times[f"{parent}::{name}"] = now
            self._bus.emit(
                BranchStarted(
                    fanout_name=parent,
                    branch_name=name,
                    branch_index=idx,
                )
            )

        if self._emit_step:
            self._bus.emit(
                StepStarted(
                    agent_name=name,
                    agent_type=atype,
                    parent_name=parent,
                )
            )
        return None

    async def after_agent_callback(
        self,
        *,
        agent: Any = None,
        callback_context: Any,
    ) -> Any:
        name = self._agent_name(agent, callback_context)
        atype = self._agent_type(agent)
        parent = self._parent_name(agent, callback_context)
        start = self._start_times.pop(name, time.monotonic())
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        if self._emit_step:
            self._bus.emit(
                StepCompleted(
                    agent_name=name,
                    agent_type=atype,
                    parent_name=parent,
                    duration_ms=duration_ms,
                )
            )

        # Close the corresponding iteration when a LoopAgent itself
        # completes — we emitted IterationStarted for the body, so we
        # close it at the boundary.
        if self._emit_iter and self._is_loop_agent(agent):
            count = self._loop_counters.pop(name, 0)
            self._loop_current_child.pop(name, None)
            # Emit a final completed event for the last iteration if any
            # ran — consumers can pair this with the last IterationStarted.
            if count > 0:
                self._bus.emit(IterationCompleted(loop_name=name, iteration=count - 1))

        if self._emit_branch and parent and self._is_parallel_parent(agent):
            indices = self._branch_indices.get(parent, {})
            idx = indices.get(name, 0)
            bkey = f"{parent}::{name}"
            bstart = self._branch_start_times.pop(bkey, start)
            bduration_ms = round((time.monotonic() - bstart) * 1000, 1)
            self._bus.emit(
                BranchCompleted(
                    fanout_name=parent,
                    branch_name=name,
                    branch_index=idx,
                    duration_ms=bduration_ms,
                )
            )

        return None

    # ------------------------------------------------------------------
    # Agent-type detection — pure ``isinstance`` with a string fallback
    # so tests can use lightweight stand-ins without importing ADK.
    # ------------------------------------------------------------------

    @staticmethod
    def _class_chain(agent: Any) -> set[str]:
        if agent is None:
            return set()
        return {cls.__name__ for cls in type(agent).__mro__}

    def _is_loop_agent(self, agent: Any) -> bool:
        return "LoopAgent" in self._class_chain(agent)

    def _is_parallel_agent(self, agent: Any) -> bool:
        return "ParallelAgent" in self._class_chain(agent)

    def _is_loop_parent(self, agent: Any) -> bool:
        parent = getattr(agent, "parent_agent", None)
        return "LoopAgent" in self._class_chain(parent)

    def _is_parallel_parent(self, agent: Any) -> bool:
        parent = getattr(agent, "parent_agent", None)
        return "ParallelAgent" in self._class_chain(parent)
