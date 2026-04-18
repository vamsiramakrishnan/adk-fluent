"""Tests for Phase C: workflow lifecycle events.

Uses lightweight stand-ins for ADK agents — the plugin's agent-type
detection is ``type(agent).__name__`` based, so we don't need real ADK
``LoopAgent`` / ``ParallelAgent`` classes here. Integration with real
ADK workflows is exercised separately by the cookbook smoke tests.
"""

from __future__ import annotations

import asyncio

import pytest

from adk_fluent import (
    EventBus,
    SessionTape,
    WorkflowLifecyclePlugin,
)
from adk_fluent._subagents import (
    FakeSubagentRunner,
    SubagentRegistry,
    SubagentSpec,
    make_task_tool,
)


class _FakeAgent:
    """Stand-in ADK agent with a name, class, and optional parent."""

    def __init__(self, name: str, kind: str = "LlmAgent", parent=None) -> None:
        self.name = name
        self.parent_agent = parent
        # Rename the class so type(agent).__name__ returns ``kind``.
        # This lets us simulate LoopAgent / ParallelAgent without ADK.
        self.__class__ = type(kind, (_FakeAgent,), {})


class _Ctx:
    def __init__(self, agent_name: str = "") -> None:
        self.agent_name = agent_name


async def _fire(plugin, agent, ctx=None):
    ctx = ctx or _Ctx(agent.name)
    await plugin.before_agent_callback(agent=agent, callback_context=ctx)
    await plugin.after_agent_callback(agent=agent, callback_context=ctx)


class TestStepEvents:
    def test_emits_started_and_completed(self):
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)
        plugin = WorkflowLifecyclePlugin(bus)

        agent = _FakeAgent("writer", kind="LlmAgent")
        asyncio.run(_fire(plugin, agent))

        kinds = [e.get("kind") for e in tape.events]
        assert "step_started" in kinds
        assert "step_completed" in kinds
        started = next(e for e in tape.events if e["kind"] == "step_started")
        assert started["agent_name"] == "writer"
        assert started["agent_type"] == "LlmAgent"

    def test_duration_is_populated(self):
        bus = EventBus()
        captured: list = []
        bus.on("step_completed", captured.append)
        plugin = WorkflowLifecyclePlugin(bus)

        async def run() -> None:
            agent = _FakeAgent("slow", kind="LlmAgent")
            await plugin.before_agent_callback(agent=agent, callback_context=_Ctx("slow"))
            await asyncio.sleep(0.005)
            await plugin.after_agent_callback(agent=agent, callback_context=_Ctx("slow"))

        asyncio.run(run())
        assert len(captured) == 1
        assert captured[0].duration_ms >= 5.0

    def test_step_events_can_be_suppressed(self):
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)
        plugin = WorkflowLifecyclePlugin(bus, emit_step_events=False)

        agent = _FakeAgent("writer")
        asyncio.run(_fire(plugin, agent))
        kinds = [e.get("kind") for e in tape.events]
        assert "step_started" not in kinds
        assert "step_completed" not in kinds


class TestIterationEvents:
    def test_loop_children_emit_iteration(self):
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)
        plugin = WorkflowLifecyclePlugin(bus)

        loop = _FakeAgent("refine", kind="LoopAgent")
        child_a = _FakeAgent("writer", kind="LlmAgent", parent=loop)
        child_b = _FakeAgent("critic", kind="LlmAgent", parent=loop)

        async def run() -> None:
            await plugin.before_agent_callback(agent=loop, callback_context=_Ctx(loop.name))
            # Iteration 1
            await _fire(plugin, child_a)
            await _fire(plugin, child_b)
            # Iteration 2 — child_a re-enters with same parent
            await _fire(plugin, child_a)
            await _fire(plugin, child_b)
            await plugin.after_agent_callback(agent=loop, callback_context=_Ctx(loop.name))

        asyncio.run(run())

        iters_started = [e for e in tape.events if e["kind"] == "iteration_started"]
        assert [e["iteration"] for e in iters_started] == [0, 1]
        assert all(e["loop_name"] == "refine" for e in iters_started)

        # The loop closes with one IterationCompleted on after_agent_callback.
        iters_done = [e for e in tape.events if e["kind"] == "iteration_completed"]
        assert len(iters_done) == 1
        assert iters_done[0]["iteration"] == 1


class TestBranchEvents:
    def test_parallel_children_emit_branch(self):
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)
        plugin = WorkflowLifecyclePlugin(bus)

        fanout = _FakeAgent("researcher", kind="ParallelAgent")
        web = _FakeAgent("web", kind="LlmAgent", parent=fanout)
        papers = _FakeAgent("papers", kind="LlmAgent", parent=fanout)

        async def run() -> None:
            await _fire(plugin, web)
            await _fire(plugin, papers)

        asyncio.run(run())

        started = [e for e in tape.events if e["kind"] == "branch_started"]
        assert [e["branch_name"] for e in started] == ["web", "papers"]
        assert [e["branch_index"] for e in started] == [0, 1]

        completed = [e for e in tape.events if e["kind"] == "branch_completed"]
        assert [e["branch_name"] for e in completed] == ["web", "papers"]


class TestSubagentEvents:
    def test_task_tool_emits_subagent_events(self):
        registry = SubagentRegistry([SubagentSpec(role="researcher", instruction="find stuff")])
        runner = FakeSubagentRunner(responder=lambda spec, prompt, ctx: f"[{spec.role}] {prompt}")
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)

        task = make_task_tool(registry, runner, bus=bus)
        task("researcher", "find three papers on foundation models")

        started = [e for e in tape.events if e["kind"] == "subagent_started"]
        completed = [e for e in tape.events if e["kind"] == "subagent_completed"]
        assert len(started) == 1
        assert started[0]["role"] == "researcher"
        assert "foundation models" in started[0]["prompt"]
        assert len(completed) == 1
        assert completed[0]["is_error"] is False

    def test_task_tool_emits_error_on_runner_failure(self):
        registry = SubagentRegistry([SubagentSpec(role="researcher", instruction="find stuff")])

        runner = FakeSubagentRunner(error_for_role={"researcher": "upstream down"})
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)

        task = make_task_tool(registry, runner, bus=bus)
        task("researcher", "go")

        completed = [e for e in tape.events if e["kind"] == "subagent_completed"]
        assert len(completed) == 1
        assert completed[0]["is_error"] is True


class TestBusIntegration:
    def test_events_flow_through_tape_with_seq(self):
        bus = EventBus()
        tape = SessionTape()
        bus.subscribe(tape.record)
        plugin = WorkflowLifecyclePlugin(bus)

        agent = _FakeAgent("a", kind="LlmAgent")
        asyncio.run(_fire(plugin, agent))

        # Every event on the tape has a monotonic seq.
        seqs = [e["seq"] for e in tape.events]
        assert seqs == sorted(seqs)
        assert seqs == list(range(len(seqs)))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
