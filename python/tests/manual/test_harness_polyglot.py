"""Tests for the polyglot CodeExecutor + agent self-management tools +
``H.coding_agent`` preset added in the build-your-own-Claude-Code work.

These tests shell out to ``bash`` and ``python3`` so they're skipped on
hosts that don't have those interpreters.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from adk_fluent import H
from adk_fluent._harness import (
    CodeExecutor,
    CodingAgentBundle,
    PlanMode,
    TodoStore,
    coding_agent,
    make_ask_user_tool,
)
from adk_fluent._harness._sandbox import SandboxPolicy

# ─── CodeExecutor ─────────────────────────────────────────────────────────


@pytest.fixture
def workspace():
    with tempfile.TemporaryDirectory(prefix="harness-poly-") as tmp:
        yield tmp


def test_code_executor_runs_bash(workspace):
    ex = H.code_executor(workspace)
    r = ex.run("bash", "echo hello-bash")
    assert r.exit_code == 0
    assert "hello-bash" in r.stdout


@pytest.mark.skipif(shutil.which("python3") is None, reason="python3 not on PATH")
def test_code_executor_runs_python(workspace):
    ex = H.code_executor(workspace)
    r = ex.run("python", "print(1 + 2)")
    assert r.exit_code == 0
    assert "3" in r.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_code_executor_runs_node(workspace):
    ex = H.code_executor(workspace)
    r = ex.run("node", "console.log(40 + 2)")
    assert r.exit_code == 0
    assert "42" in r.stdout


def test_code_executor_respects_timeout(workspace):
    ex = H.code_executor(workspace)
    r = ex.run("bash", "sleep 5", timeout_ms=100)
    assert r.exit_code != 0
    assert "killed after" in r.stderr


def test_code_executor_refuses_when_shell_disabled(workspace):
    sandbox = SandboxPolicy(workspace=workspace, allow_shell=False)
    ex = CodeExecutor(sandbox=sandbox)
    with pytest.raises(RuntimeError, match="forbids shell"):
        ex.run("bash", "echo nope")


def test_code_executor_tools_factory(workspace):
    tools = H.run_code_tools(workspace)
    names = [t.__name__ for t in tools]
    assert names == ["run_code", "which_languages"]


def test_code_executor_detect_returns_bool_map(workspace):
    ex = H.code_executor(workspace)
    detected = ex.detect()
    assert "bash" in detected
    assert isinstance(detected["bash"], bool)


# ─── TodoStore ────────────────────────────────────────────────────────────


def test_todo_store_replaces_items():
    store = H.todos()
    store.replace(
        [
            {"content": "first", "active_form": "doing first", "status": "pending"},
            {"content": "second", "active_form": "doing second", "status": "in_progress"},
        ]
    )
    items = store.list()
    assert len(items) == 2
    assert items[0].content == "first"
    assert items[1].status == "in_progress"


def test_todo_store_rejects_multiple_in_progress():
    store = TodoStore()
    with pytest.raises(ValueError, match="in_progress"):
        store.replace(
            [
                {"content": "a", "active_form": "doing a", "status": "in_progress"},
                {"content": "b", "active_form": "doing b", "status": "in_progress"},
            ]
        )


# ─── PlanMode ─────────────────────────────────────────────────────────────


def test_plan_mode_state_transitions():
    pm = H.plan_mode()
    assert pm.current == "off"
    pm.enter()
    assert pm.current == "planning"
    pm.exit("step 1; step 2")
    assert pm.current == "executing"
    assert "step 1" in pm.current_plan
    pm.reset()
    assert pm.current == "off"


def test_plan_mode_identifies_mutating_tools():
    assert PlanMode.is_mutating("write_file")
    assert PlanMode.is_mutating("bash")
    assert PlanMode.is_mutating("run_code")
    assert not PlanMode.is_mutating("read_file")
    assert not PlanMode.is_mutating("glob_search")


# ─── ask_user ─────────────────────────────────────────────────────────────


def test_ask_user_default_handler_raises():
    tool = make_ask_user_tool()
    with pytest.raises(RuntimeError, match="no handler installed"):
        tool(question="who?")


def test_ask_user_invokes_custom_handler():
    captured: list[str] = []

    def handler(q: str, opts):
        captured.append(q)
        return "yes"

    tool = H.ask_user(handler)
    result = tool(question="ready?")
    assert result == {"answer": "yes"}
    assert captured == ["ready?"]


# ─── coding_agent preset ─────────────────────────────────────────────────


def test_coding_agent_returns_full_bundle(workspace):
    Path(workspace, "hello.txt").write_text("world")
    bundle = H.coding_agent(workspace, enable_git=False)
    assert isinstance(bundle, CodingAgentBundle)
    assert bundle.workspace == str(Path(workspace).resolve())
    names = {t.__name__ for t in bundle.tools}
    for must in {"read_file", "run_code", "todo_write", "enter_plan_mode", "ask_user_question"}:
        assert must in names, f"missing {must} (got {sorted(names)})"


def test_coding_agent_read_only_drops_mutators(workspace):
    bundle = coding_agent(workspace, allow_mutations=False, enable_git=False)
    names = {t.__name__ for t in bundle.tools}
    assert "read_file" in names
    assert "write_file" not in names
    assert "edit_file" not in names
    assert "bash" not in names


def test_coding_agent_executor_is_sandboxed(workspace):
    bundle = coding_agent(workspace, enable_git=False)
    r = bundle.executor.run("bash", "pwd")
    assert r.exit_code == 0
    assert str(Path(workspace).resolve()) in r.stdout
