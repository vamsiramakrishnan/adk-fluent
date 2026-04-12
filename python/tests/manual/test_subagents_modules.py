"""Dedicated tests for ``adk_fluent._subagents`` — dynamic spawner + task tool."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from adk_fluent import (
    FakeSubagentRunner,
    H,
    SubagentRegistry,
    SubagentResult,
    SubagentRunner,
    SubagentSpec,
    make_task_tool,
)

# ======================================================================
# SubagentSpec
# ======================================================================


class TestSubagentSpec:
    def test_happy_path(self):
        spec = SubagentSpec(
            role="researcher",
            instruction="Find three papers.",
            description="Deep research specialist",
            tool_names=("web_search",),
            permission_mode="plan",
            max_tokens=5_000,
        )
        assert spec.role == "researcher"
        assert spec.permission_mode == "plan"
        assert spec.max_tokens == 5_000
        assert spec.tool_names == ("web_search",)

    def test_spec_is_frozen(self):
        spec = SubagentSpec(role="r", instruction="i")
        with pytest.raises(FrozenInstanceError):
            spec.role = "other"  # type: ignore[misc]

    def test_rejects_empty_role(self):
        with pytest.raises(ValueError):
            SubagentSpec(role="", instruction="i")

    def test_rejects_empty_instruction(self):
        with pytest.raises(ValueError):
            SubagentSpec(role="r", instruction="")


# ======================================================================
# SubagentRegistry
# ======================================================================


class TestSubagentRegistry:
    def test_register_and_get(self):
        r = SubagentRegistry()
        spec = SubagentSpec(role="r", instruction="i")
        r.register(spec)
        assert r.get("r") is spec
        assert "r" in r
        assert len(r) == 1

    def test_duplicate_registration_raises(self):
        r = SubagentRegistry()
        r.register(SubagentSpec(role="r", instruction="i"))
        with pytest.raises(ValueError):
            r.register(SubagentSpec(role="r", instruction="i2"))

    def test_replace_overwrites(self):
        r = SubagentRegistry()
        r.register(SubagentSpec(role="r", instruction="i"))
        r.replace(SubagentSpec(role="r", instruction="i2"))
        assert r.get("r").instruction == "i2"

    def test_unregister(self):
        r = SubagentRegistry([SubagentSpec(role="r", instruction="i")])
        r.unregister("r")
        assert "r" not in r
        # Silent when absent.
        r.unregister("missing")

    def test_require_raises_on_missing(self):
        with pytest.raises(KeyError):
            SubagentRegistry().require("nope")

    def test_roles_preserves_order(self):
        r = SubagentRegistry(
            [
                SubagentSpec(role="a", instruction="i"),
                SubagentSpec(role="b", instruction="i"),
                SubagentSpec(role="c", instruction="i"),
            ]
        )
        assert r.roles() == ["a", "b", "c"]

    def test_roster_lists_roles(self):
        r = SubagentRegistry(
            [
                SubagentSpec(
                    role="researcher",
                    instruction="Find papers.",
                    description="deep search",
                ),
                SubagentSpec(
                    role="reviewer",
                    instruction="Review results.",
                ),
            ]
        )
        roster = r.roster()
        assert "researcher" in roster
        assert "reviewer" in roster
        assert "deep search" in roster

    def test_roster_empty(self):
        assert "no subagents" in SubagentRegistry().roster()

    def test_iteration(self):
        specs = [
            SubagentSpec(role="a", instruction="i"),
            SubagentSpec(role="b", instruction="i"),
        ]
        r = SubagentRegistry(specs)
        assert list(r) == specs


# ======================================================================
# SubagentResult
# ======================================================================


class TestSubagentResult:
    def test_success_output(self):
        r = SubagentResult(role="r", output="hello")
        assert not r.is_error
        assert r.to_tool_output() == "[r] hello"

    def test_error_output(self):
        r = SubagentResult(role="r", output="", error="boom")
        assert r.is_error
        assert r.to_tool_output() == "[r:error] boom"


# ======================================================================
# FakeSubagentRunner
# ======================================================================


class TestFakeSubagentRunner:
    def test_satisfies_protocol(self):
        assert isinstance(FakeSubagentRunner(), SubagentRunner)

    def test_default_echoes_prompt(self):
        runner = FakeSubagentRunner()
        result = runner.run(SubagentSpec(role="r", instruction="i"), "hi")
        assert result.output == "echo: hi"
        assert result.role == "r"

    def test_responder_callable(self):
        runner = FakeSubagentRunner(
            responder=lambda spec, prompt, ctx: f"{spec.role}::{prompt}"
        )
        result = runner.run(SubagentSpec(role="r", instruction="i"), "go")
        assert result.output == "r::go"

    def test_error_for_role(self):
        runner = FakeSubagentRunner(error_for_role={"r": "blown up"})
        result = runner.run(SubagentSpec(role="r", instruction="i"), "hi")
        assert result.is_error
        assert result.error == "blown up"

    def test_responder_exception_becomes_error(self):
        def boom(spec, prompt, ctx):
            raise RuntimeError("nope")

        runner = FakeSubagentRunner(responder=boom)
        result = runner.run(SubagentSpec(role="r", instruction="i"), "hi")
        assert result.is_error
        assert "nope" in result.error

    def test_call_log(self):
        runner = FakeSubagentRunner()
        spec = SubagentSpec(role="r", instruction="i")
        runner.run(spec, "one")
        runner.run(spec, "two", {"ctx": True})
        log = runner.calls
        assert len(log) == 2
        assert log[0][1] == "one"
        assert log[1][2] == {"ctx": True}

    def test_usage_is_attached(self):
        runner = FakeSubagentRunner(usage={"input_tokens": 5, "output_tokens": 3})
        result = runner.run(SubagentSpec(role="r", instruction="i"), "hi")
        assert result.usage == {"input_tokens": 5, "output_tokens": 3}


# ======================================================================
# make_task_tool
# ======================================================================


class TestMakeTaskTool:
    def _setup(self):
        registry = SubagentRegistry(
            [
                SubagentSpec(
                    role="researcher",
                    instruction="Find papers.",
                    description="deep search specialist",
                ),
                SubagentSpec(
                    role="reviewer",
                    instruction="Review results.",
                    description="critic",
                ),
            ]
        )
        runner = FakeSubagentRunner(
            responder=lambda spec, prompt, ctx: f"{spec.role} handled: {prompt}"
        )
        task = make_task_tool(registry, runner)
        return registry, runner, task

    def test_tool_name_is_task(self):
        _, _, task = self._setup()
        assert task.__name__ == "task"

    def test_docstring_lists_roles(self):
        _, _, task = self._setup()
        doc = task.__doc__
        assert "researcher" in doc
        assert "reviewer" in doc
        assert "deep search" in doc

    def test_dispatches_to_runner(self):
        _, runner, task = self._setup()
        output = task("researcher", "find LLM scaling papers")
        assert "[researcher]" in output
        assert "find LLM scaling papers" in output
        assert len(runner.calls) == 1

    def test_unknown_role_returns_error(self):
        _, _, task = self._setup()
        out = task("nope", "hi")
        assert "unknown subagent role" in out.lower()
        assert "researcher" in out

    def test_runner_error_propagates(self):
        registry = SubagentRegistry(
            [SubagentSpec(role="r", instruction="i")]
        )
        runner = FakeSubagentRunner(error_for_role={"r": "model down"})
        task = make_task_tool(registry, runner)
        out = task("r", "hi")
        assert "r:error" in out
        assert "model down" in out

    def test_context_provider_is_called(self):
        registry = SubagentRegistry([SubagentSpec(role="r", instruction="i")])
        runner = FakeSubagentRunner()
        captured: list[dict] = []

        def responder(spec, prompt, ctx):
            captured.append(ctx)
            return "ok"

        runner = FakeSubagentRunner(responder=responder)
        task = make_task_tool(
            registry, runner, context_provider=lambda: {"turn": 3}
        )
        task("r", "hi")
        assert captured == [{"turn": 3}]

    def test_custom_tool_name(self):
        registry, runner, _ = self._setup()
        task = make_task_tool(registry, runner, tool_name="dispatch")
        assert task.__name__ == "dispatch"


# ======================================================================
# H namespace sugar
# ======================================================================


class TestHNamespaceSugar:
    def test_subagent_spec_factory(self):
        spec = H.subagent_spec("r", "instruction", description="d")
        assert isinstance(spec, SubagentSpec)
        assert spec.description == "d"

    def test_subagent_registry_factory(self):
        r = H.subagent_registry(
            [H.subagent_spec("a", "i"), H.subagent_spec("b", "i")]
        )
        assert isinstance(r, SubagentRegistry)
        assert "a" in r and "b" in r

    def test_task_tool_factory(self):
        registry = H.subagent_registry([H.subagent_spec("r", "i")])
        runner = FakeSubagentRunner()
        task = H.task_tool(registry, runner)
        assert callable(task)
        assert "r" in task.__doc__
