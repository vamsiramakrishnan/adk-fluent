"""Tests for :class:`AdkSubagentRunner` — the real, runnable subagent runner.

The LLM is mocked via the fluent builder's ``.mock([...])`` so no network is
needed: ``.mock()`` injects a ``before_model_callback`` that returns a canned
``LlmResponse`` and bypasses the model entirely.
"""

from __future__ import annotations

import pytest

from adk_fluent._subagents import (
    AdkSubagentRunner,
    SubagentRegistry,
    SubagentResult,
    SubagentRunner,
    SubagentSpec,
    make_task_tool,
)


def _mocked_runner(text: str) -> AdkSubagentRunner:
    """An AdkSubagentRunner whose agents always return ``text`` (no network)."""

    def factory(spec: SubagentSpec):
        from adk_fluent import Agent

        return (
            Agent(spec.role, spec.model or "gemini-2.5-flash")
            .instruct(spec.instruction)
            .describe(spec.description)
            .mock([text])
        )

    return AdkSubagentRunner(agent_factory=factory)


# ======================================================================
# Protocol conformance
# ======================================================================


def test_satisfies_runner_protocol():
    runner = AdkSubagentRunner()
    assert isinstance(runner, SubagentRunner)


def test_wires_into_make_task_tool():
    registry = SubagentRegistry(
        [SubagentSpec(role="researcher", instruction="Find papers.", description="research")]
    )
    runner = _mocked_runner("found three papers")
    task = make_task_tool(registry, runner)

    assert callable(task)
    assert task.__name__ == "task"
    assert "researcher" in (task.__doc__ or "")


# ======================================================================
# Happy path
# ======================================================================


def test_run_returns_non_error_result():
    spec = SubagentSpec(role="researcher", instruction="Find papers.")
    runner = _mocked_runner("RESEARCH OUTPUT")

    result = runner.run(spec, "dig up three papers on X")

    assert isinstance(result, SubagentResult)
    assert result.role == "researcher"
    assert result.is_error is False
    assert result.error == ""
    assert result.output == "RESEARCH OUTPUT"


def test_task_tool_end_to_end():
    registry = SubagentRegistry(
        [SubagentSpec(role="reviewer", instruction="Critique the draft.")]
    )
    runner = _mocked_runner("looks good")
    task = make_task_tool(registry, runner)

    out = task("reviewer", "review this")

    # to_tool_output() prefixes the role for provenance.
    assert out == "[reviewer] looks good"


def test_uses_spec_model_when_set():
    captured: dict[str, str] = {}

    def factory(spec: SubagentSpec):
        from adk_fluent import Agent

        captured["model"] = spec.model or "gemini-2.5-flash"
        return Agent(spec.role, spec.model or "gemini-2.5-flash").instruct(spec.instruction).mock(["ok"])

    runner = AdkSubagentRunner(agent_factory=factory)
    spec = SubagentSpec(role="r", instruction="i", model="gemini-2.5-pro")
    result = runner.run(spec, "go")

    assert result.is_error is False
    assert captured["model"] == "gemini-2.5-pro"


# ======================================================================
# Error path
# ======================================================================


def test_exception_yields_is_error():
    def boom_factory(spec: SubagentSpec):
        raise RuntimeError("kaboom")

    runner = AdkSubagentRunner(agent_factory=boom_factory)
    spec = SubagentSpec(role="researcher", instruction="Find papers.")

    result = runner.run(spec, "anything")

    assert result.is_error is True
    assert result.output == ""
    assert "kaboom" in result.error
    assert result.role == "researcher"


def test_error_surfaces_through_task_tool():
    def boom_factory(spec: SubagentSpec):
        raise ValueError("bad wiring")

    registry = SubagentRegistry([SubagentSpec(role="researcher", instruction="i")])
    runner = AdkSubagentRunner(agent_factory=boom_factory)
    task = make_task_tool(registry, runner)

    out = task("researcher", "go")

    assert out.startswith("[researcher:error]")
    assert "bad wiring" in out


# ======================================================================
# Tool resolution
# ======================================================================


def test_tool_names_resolved_via_resolver():
    resolved: list[str] = []

    def my_tool(x: str) -> str:
        """A demo tool."""
        return x

    def resolver(name: str):
        resolved.append(name)
        return my_tool if name == "demo_tool" else None

    def factory(spec: SubagentSpec):
        # Exercise the real _build_agent path but force a mocked LLM.
        from adk_fluent import Agent

        agent = Agent(spec.role, "gemini-2.5-flash").instruct(spec.instruction)
        for n in spec.tool_names:
            t = resolver(n)
            if t is not None:
                agent = agent.tool(t)
        return agent.mock(["done"])

    runner = AdkSubagentRunner(agent_factory=factory)
    spec = SubagentSpec(
        role="r", instruction="i", tool_names=("demo_tool", "missing_tool")
    )
    result = runner.run(spec, "go")

    assert result.is_error is False
    assert resolved == ["demo_tool", "missing_tool"]


def test_build_agent_skips_unresolvable_tools_gracefully():
    """A resolver that returns None / raises must not abort the build."""

    def resolver(name: str):
        if name == "raises":
            raise KeyError(name)
        return None  # unresolvable

    runner = AdkSubagentRunner(tool_resolver=resolver)
    spec = SubagentSpec(role="r", instruction="i", tool_names=("raises", "missing"))

    # Should build without raising despite both tools being unresolvable.
    builder = runner._build_agent(spec)
    assert builder is not None


# ======================================================================
# Async variant + running-loop guard
# ======================================================================


@pytest.mark.asyncio
async def test_run_async_works_in_loop():
    spec = SubagentSpec(role="researcher", instruction="Find papers.")
    runner = _mocked_runner("ASYNC OUTPUT")

    result = await runner.run_async(spec, "go")

    assert result.is_error is False
    assert result.output == "ASYNC OUTPUT"


@pytest.mark.asyncio
async def test_sync_run_inside_loop_raises():
    from adk_fluent._subagents import SubagentRunnerError

    spec = SubagentSpec(role="researcher", instruction="Find papers.")
    runner = _mocked_runner("x")

    with pytest.raises(SubagentRunnerError):
        runner.run(spec, "go")
