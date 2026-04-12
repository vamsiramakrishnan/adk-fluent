"""Tests for the new H namespace affordances — all 12 harness capabilities.

Tests cover:
    - Web tools (fetch, search)
    - Project memory (load, save, append, callbacks)
    - Usage tracking (record, callback, summary)
    - Diff mode (preview, apply, expire)
    - Multimodal reading (images, text fallback)
    - Process management (start, check, stop)
    - MCP bulk loading (config parsing)
    - Hook extensions (on_edit, on_error, on_commit, on_compress)
    - Error strategy (retry, skip, ask, merge)
    - Notebook tools (read, edit cells)
    - Task management (launch, check, list)
    - Event rendering (plain, json, rich)
    - New event types
    - HarnessConfig with new fields
    - .harness() wiring of new affordances
"""

import json
import os
import tempfile

import pytest

from adk_fluent import Agent, H
from adk_fluent._harness import (
    ErrorOccurred,
    ErrorStrategy,
    FileEdited,
    HarnessConfig,
    JsonRenderer,
    PendingEditStore,
    PlainRenderer,
    ProcessEvent,
    ProcessRegistry,
    ProjectMemory,
    SandboxPolicy,
    TaskEvent,
    TaskRegistry,
    TaskStatus,
    TextChunk,
    ToolCallEnd,
    ToolCallStart,
    UsageTracker,
    UsageUpdate,
    make_apply_edit,
    make_diff_edit_file,
    make_multimodal_read_file,
    make_web_fetch,
)

# ======================================================================
# Web tools
# ======================================================================


class TestWebTools:
    def test_web_fetch_respects_network_policy(self):
        """web_fetch rejects when network disabled."""
        sandbox = SandboxPolicy(allow_network=False)
        fetch = make_web_fetch(sandbox)
        result = fetch("http://example.com")
        assert "disabled" in result

    def test_web_fetch_rejects_bad_url(self):
        """web_fetch rejects non-http URLs."""
        sandbox = SandboxPolicy(allow_network=True)
        fetch = make_web_fetch(sandbox)
        result = fetch("ftp://example.com")
        assert "Error" in result

    def test_h_web_returns_list(self):
        """H.web() returns a list of tools."""
        tools = H.web(allow_network=False)
        assert isinstance(tools, list)
        assert len(tools) >= 1

    def test_h_web_no_search(self):
        """H.web(search=False) returns fewer tools."""
        tools = H.web(search=False, allow_network=False)
        assert isinstance(tools, list)


# ======================================================================
# Project memory
# ======================================================================


class TestProjectMemory:
    def test_load_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = ProjectMemory(os.path.join(tmp, "memory.md"))
            assert mem.load() == ""
            assert not mem.exists

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "memory.md")
            mem = ProjectMemory(path)
            mem.save("# Project memory\n- Remember: use pytest")
            assert mem.exists
            content = mem.load()
            assert "use pytest" in content

    def test_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "memory.md")
            mem = ProjectMemory(path)
            mem.save("# Memory")
            mem.append("learned X")
            mem.append("learned Y")
            content = mem.load()
            assert "learned X" in content
            assert "learned Y" in content

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "memory.md")
            mem = ProjectMemory(path)
            mem.save("data")
            mem.clear()
            assert not mem.exists

    def test_h_memory_factory(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = H.memory(os.path.join(tmp, "mem.md"))
            assert isinstance(mem, ProjectMemory)

    def test_load_callback(self):
        """Load callback injects content into state."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "memory.md")
            mem = ProjectMemory(path, state_key="mem")
            mem.save("project notes")
            cb = mem.load_callback()

            # Simulate callback context with state
            class FakeCtx:
                state = {}

            ctx = FakeCtx()
            cb(ctx)
            assert ctx.state["mem"] == "project notes"


# ======================================================================
# Usage tracking
# ======================================================================


class TestUsageTracker:
    def test_record(self):
        tracker = UsageTracker()
        tracker.record(100, 50, model="gemini-2.5-flash")
        assert tracker.total_input_tokens == 100
        assert tracker.total_output_tokens == 50
        assert tracker.total_tokens == 150
        assert tracker.turn_count == 1

    def test_multiple_records(self):
        tracker = UsageTracker()
        tracker.record(100, 50)
        tracker.record(200, 100)
        assert tracker.total_input_tokens == 300
        assert tracker.total_output_tokens == 150
        assert tracker.turn_count == 2

    def test_cost_calculation(self):
        tracker = UsageTracker(
            cost_per_million_input=3.0,
            cost_per_million_output=15.0,
        )
        tracker.record(1_000_000, 100_000)
        assert tracker.total_cost_usd == pytest.approx(3.0 + 1.5)

    def test_summary(self):
        tracker = UsageTracker()
        tracker.record(500, 200)
        summary = tracker.summary()
        assert "500" in summary
        assert "200" in summary

    def test_reset(self):
        tracker = UsageTracker()
        tracker.record(100, 50)
        tracker.reset()
        assert tracker.turn_count == 0
        assert tracker.total_tokens == 0

    def test_h_usage_factory(self):
        tracker = H.usage()
        assert isinstance(tracker, UsageTracker)

    def test_h_usage_with_cost(self):
        tracker = H.usage(cost_per_million_input=3.0, cost_per_million_output=15.0)
        assert tracker.cost_per_million_input == 3.0


# ======================================================================
# Diff mode
# ======================================================================


class TestDiffMode:
    def test_diff_preview(self):
        """edit_file in diff_mode returns a diff and token."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = os.path.join(tmp, "test.py")
            with open(test_file, "w") as f:
                f.write("hello world\n")

            sandbox = SandboxPolicy(workspace=tmp)
            store = PendingEditStore()
            edit = make_diff_edit_file(sandbox, store)
            result = edit("test.py", "hello", "goodbye")
            assert "goodbye" in result
            assert "apply_edit" in result

    def test_apply_edit(self):
        """apply_edit applies a pending edit."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = os.path.join(tmp, "test.py")
            with open(test_file, "w") as f:
                f.write("hello world\n")

            sandbox = SandboxPolicy(workspace=tmp)
            store = PendingEditStore()
            edit = make_diff_edit_file(sandbox, store)
            apply = make_apply_edit(sandbox, store)

            # Preview
            result = edit("test.py", "hello", "goodbye")
            # Extract token
            token = result.split('"')[-2]
            # Apply
            result = apply(token)
            assert "Successfully" in result

            with open(test_file) as f:
                assert "goodbye world" in f.read()

    def test_expired_token(self):
        """Expired tokens are rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp)
            store = PendingEditStore(ttl=0)  # Immediate expiry
            apply = make_apply_edit(sandbox, store)
            result = apply("nonexistent")
            assert "Error" in result

    def test_h_workspace_diff_mode(self):
        """H.workspace(diff_mode=True) includes edit_file and apply_edit."""
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.workspace(tmp, diff_mode=True)
            names = [t.__name__ for t in tools]
            assert "edit_file" in names
            assert "apply_edit" in names


# ======================================================================
# Multimodal reading
# ======================================================================


class TestMultimodal:
    def test_text_file_unchanged(self):
        """Text files are read normally with multimodal enabled."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = os.path.join(tmp, "test.py")
            with open(test_file, "w") as f:
                f.write("print('hello')\n")

            sandbox = SandboxPolicy(workspace=tmp)
            read = make_multimodal_read_file(sandbox)
            result = read("test.py")
            assert "1\tprint('hello')" in result

    def test_image_returns_base64(self):
        """Image files return base64-encoded content."""
        with tempfile.TemporaryDirectory() as tmp:
            img_file = os.path.join(tmp, "test.png")
            with open(img_file, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

            sandbox = SandboxPolicy(workspace=tmp)
            read = make_multimodal_read_file(sandbox)
            result = read("test.png")
            assert "base64" in result
            assert "image/png" in result

    def test_outside_workspace_blocked(self):
        """Multimodal read respects sandbox."""
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp)
            read = make_multimodal_read_file(sandbox)
            result = read("/etc/passwd")
            assert "Error" in result or "outside" in result

    def test_h_workspace_multimodal(self):
        """H.workspace(multimodal=True) replaces read_file."""
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.workspace(tmp, multimodal=True)
            names = [t.__name__ for t in tools]
            assert "read_file" in names
            assert len(tools) == 7  # Same count


# ======================================================================
# Process management
# ======================================================================


class TestProcessManagement:
    def test_start_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp, allow_shell=True)
            registry = ProcessRegistry(sandbox)
            result = registry.start("sleeper", "sleep 10")
            assert "Started" in result
            result = registry.check("sleeper")
            assert "running" in result

    def test_stop_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp, allow_shell=True)
            registry = ProcessRegistry(sandbox)
            registry.start("sleeper", "sleep 10")
            result = registry.stop("sleeper")
            assert "Stopped" in result

    def test_shell_disabled(self):
        sandbox = SandboxPolicy(allow_shell=False)
        registry = ProcessRegistry(sandbox)
        result = registry.start("test", "echo hi")
        assert "disabled" in result

    def test_check_nonexistent(self):
        sandbox = SandboxPolicy(allow_shell=True)
        registry = ProcessRegistry(sandbox)
        result = registry.check("nonexistent")
        assert "Error" in result

    def test_h_processes_factory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.processes(tmp)
            assert len(tools) == 3
            names = [t.__name__ for t in tools]
            assert "start_process" in names
            assert "check_process" in names
            assert "stop_process" in names

    def test_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp, allow_shell=True)
            registry = ProcessRegistry(sandbox)
            registry.start("bg", "sleep 100")
            registry.cleanup()
            assert len(registry._processes) == 0


# ======================================================================
# MCP config parsing
# ======================================================================


class TestMCPConfig:
    def test_load_config_array_format(self):
        """Array format config is parsed."""
        with tempfile.TemporaryDirectory() as tmp:
            config_path = os.path.join(tmp, "mcp.json")
            config = {
                "mcpServers": [
                    {"url": "http://localhost:3000/mcp"},
                    {"command": "npx", "args": ["-y", "test-server"]},
                ]
            }
            with open(config_path, "w") as f:
                json.dump(config, f)

            from adk_fluent._harness._mcp import load_mcp_config

            # Will return empty list if McpToolset isn't installed
            result = load_mcp_config(config_path)
            assert isinstance(result, list)

    def test_load_config_dict_format(self):
        """Claude Code dict format config is parsed."""
        with tempfile.TemporaryDirectory() as tmp:
            config_path = os.path.join(tmp, "mcp.json")
            config = {
                "mcpServers": {
                    "filesystem": {"command": "npx", "args": ["-y", "@mcp/fs"]},
                    "github": {"url": "http://localhost:3001/mcp"},
                }
            }
            with open(config_path, "w") as f:
                json.dump(config, f)

            from adk_fluent._harness._mcp import load_mcp_config

            result = load_mcp_config(config_path)
            assert isinstance(result, list)

    def test_load_config_missing_file(self):
        from adk_fluent._harness._mcp import load_mcp_config

        result = load_mcp_config("/nonexistent/path.json")
        assert result == []

    def test_h_mcp_factory(self):
        result = H.mcp([])
        assert result == []


# ======================================================================
# Hook extensions
# ======================================================================
# The convenience methods ``on_edit`` / ``on_error`` / ``on_commit`` /
# ``on_compress`` were removed when the hook foundation moved to
# ``adk_fluent._hooks``. Hook tests live in test_hooks_modules.py now; the
# equivalent recipes use ``HookEvent.POST_TOOL_USE`` + ``HookMatcher.for_tool``
# (see docs/user-guide/hooks.md).


# ======================================================================
# Error strategy
# ======================================================================


class TestErrorStrategy:
    def test_action_for(self):
        strategy = ErrorStrategy(
            retry=frozenset({"bash"}),
            skip=frozenset({"glob_search"}),
            ask=frozenset({"edit_file"}),
        )
        assert strategy.action_for("bash") == "retry"
        assert strategy.action_for("glob_search") == "skip"
        assert strategy.action_for("edit_file") == "ask"
        assert strategy.action_for("unknown") == "propagate"

    def test_merge(self):
        s1 = ErrorStrategy(retry=frozenset({"bash"}))
        s2 = ErrorStrategy(skip=frozenset({"bash"}))
        merged = s1.merge(s2)
        assert merged.action_for("bash") == "skip"

    def test_h_on_error_factory(self):
        strategy = H.on_error(retry={"bash"}, skip={"glob_search"})
        assert isinstance(strategy, ErrorStrategy)
        assert strategy.action_for("bash") == "retry"


# ======================================================================
# Notebook tools
# ======================================================================


class TestNotebookTools:
    def _make_notebook(self, tmp, name="test.ipynb"):
        nb = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["print('hello')\n"],
                    "outputs": [],
                    "execution_count": 1,
                    "metadata": {},
                },
                {"cell_type": "markdown", "source": ["# Title\n"], "metadata": {}},
            ],
            "metadata": {},
        }
        path = os.path.join(tmp, name)
        with open(path, "w") as f:
            json.dump(nb, f)
        return path

    def test_read_notebook(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_notebook(tmp)
            sandbox = SandboxPolicy(workspace=tmp)
            from adk_fluent._harness._notebook import make_read_notebook

            read = make_read_notebook(sandbox)
            result = read("test.ipynb")
            assert "Cell 0" in result
            assert "print('hello')" in result
            assert "Cell 1" in result
            assert "Title" in result

    def test_read_specific_cell(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_notebook(tmp)
            sandbox = SandboxPolicy(workspace=tmp)
            from adk_fluent._harness._notebook import make_read_notebook

            read = make_read_notebook(sandbox)
            result = read("test.ipynb", cell_index=1)
            assert "markdown" in result
            assert "Title" in result

    def test_edit_notebook_cell(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_notebook(tmp)
            sandbox = SandboxPolicy(workspace=tmp)
            from adk_fluent._harness._notebook import make_edit_notebook_cell

            edit = make_edit_notebook_cell(sandbox)
            result = edit("test.ipynb", 0, "print('goodbye')")
            assert "Successfully" in result

            # Verify the edit
            with open(os.path.join(tmp, "test.ipynb")) as f:
                nb = json.load(f)
            assert "goodbye" in "".join(nb["cells"][0]["source"])

    def test_h_notebook_factory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.notebook(tmp)
            assert len(tools) == 2
            names = [t.__name__ for t in tools]
            assert "read_notebook" in names
            assert "edit_notebook_cell" in names


# ======================================================================
# Task management
# ======================================================================


class TestTaskManagement:
    def test_register_and_complete(self):
        registry = TaskRegistry()
        info = registry.register("research", "Find papers")
        assert info.status == TaskStatus.PENDING
        registry.complete("research", "Found 5 papers")
        info = registry.get("research")
        assert info.status == TaskStatus.COMPLETE
        assert info.result == "Found 5 papers"

    def test_fail_task(self):
        registry = TaskRegistry()
        registry.register("build")
        registry.fail("build", "Compilation error")
        info = registry.get("build")
        assert info.status == TaskStatus.FAILED

    def test_cancel_task(self):
        registry = TaskRegistry()
        registry.register("long_task")
        assert registry.cancel("long_task")
        info = registry.get("long_task")
        assert info.status == TaskStatus.CANCELLED

    def test_max_tasks(self):
        registry = TaskRegistry(max_tasks=2)
        registry.register("task1")
        registry.register("task2")
        with pytest.raises(ValueError, match="Maximum"):
            registry.register("task3")

    def test_h_tasks_factory(self):
        tools = H.tasks()
        assert len(tools) == 3
        names = [t.__name__ for t in tools]
        assert "launch_task" in names
        assert "check_task" in names
        assert "list_tasks" in names

    def test_task_tools_workflow(self):
        from adk_fluent._harness._tasks import task_tools

        registry = TaskRegistry()
        tools = task_tools(registry)
        launch, check, list_all = tools

        result = launch("test_task", "A test")
        assert "registered" in result

        result = check("test_task")
        assert "pending" in result

        result = list_all()
        assert "test_task" in result


# ======================================================================
# Event rendering
# ======================================================================


class TestRendering:
    def test_plain_renderer_text(self):
        renderer = PlainRenderer()
        result = renderer.render(TextChunk(text="Hello"))
        assert result == "Hello"

    def test_plain_renderer_tool_start(self):
        renderer = PlainRenderer()
        result = renderer.render(ToolCallStart(tool_name="bash"))
        assert "bash" in result

    def test_plain_renderer_tool_end(self):
        renderer = PlainRenderer(show_timing=True)
        result = renderer.render(ToolCallEnd(tool_name="bash", duration_ms=150))
        assert "bash" in result
        assert "150" in result

    def test_plain_renderer_verbose(self):
        renderer = PlainRenderer(verbose=True)
        result = renderer.render(FileEdited(file_path="main.py"))
        assert "file_edited" in result

    def test_json_renderer(self):
        renderer = JsonRenderer()
        result = renderer.render(ToolCallStart(tool_name="bash", args={"command": "ls"}))
        data = json.loads(result)
        assert data["kind"] == "tool_call_start"
        assert data["tool_name"] == "bash"

    def test_rich_renderer_fallback(self):
        """RichRenderer falls back to plain when rich not installed."""
        from adk_fluent._harness._renderer import RichRenderer

        renderer = RichRenderer()
        result = renderer.render(TextChunk(text="Hello"))
        assert "Hello" in result

    def test_h_renderer_factory(self):
        renderer = H.renderer()
        assert isinstance(renderer, PlainRenderer)

    def test_h_renderer_json(self):
        renderer = H.renderer(format="json")
        assert isinstance(renderer, JsonRenderer)


# ======================================================================
# New event types
# ======================================================================


class TestNewEventTypes:
    def test_file_edited(self):
        e = FileEdited(file_path="main.py")
        assert e.kind == "file_edited"
        assert e.file_path == "main.py"

    def test_error_occurred(self):
        e = ErrorOccurred(tool_name="bash", error="timeout")
        assert e.kind == "error"

    def test_usage_update(self):
        e = UsageUpdate(input_tokens=100, output_tokens=50, total_tokens=150)
        assert e.kind == "usage_update"

    def test_process_event(self):
        e = ProcessEvent(process_name="server", action="started")
        assert e.kind == "process_event"

    def test_task_event(self):
        e = TaskEvent(task_name="build", status="complete")
        assert e.kind == "task_event"


# ======================================================================
# HarnessConfig with new fields
# ======================================================================


class TestHarnessConfigExtended:
    def test_config_with_usage(self):
        tracker = H.usage()
        cfg = H.config(usage=tracker)
        assert isinstance(cfg, HarnessConfig)
        assert cfg.usage is tracker

    def test_config_with_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = H.memory(os.path.join(tmp, "mem.md"))
            cfg = H.config(memory=mem)
            assert cfg.memory is mem

    def test_config_with_error_strategy(self):
        strategy = H.on_error(retry={"bash"})
        cfg = H.config(on_error=strategy)
        assert cfg.on_error is strategy


# ======================================================================
# .harness() wiring of new affordances
# ======================================================================


class TestHarnessWiring:
    def test_harness_wires_usage(self):
        tracker = H.usage()
        agent = Agent("coder", "gemini-2.5-flash").instruct("Code.").harness(usage=tracker)
        assert len(agent._callbacks.get("after_model_callback", [])) > 0

    def test_harness_wires_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = H.memory(os.path.join(tmp, "mem.md"))
            agent = Agent("coder", "gemini-2.5-flash").instruct("Code.").harness(memory=mem)
            assert len(agent._callbacks.get("before_agent_callback", [])) > 0
            assert len(agent._callbacks.get("after_agent_callback", [])) > 0

    def test_harness_wires_error_strategy(self):
        strategy = H.on_error(retry={"bash"})
        agent = Agent("coder", "gemini-2.5-flash").instruct("Code.").harness(on_error=strategy)
        assert len(agent._callbacks.get("after_tool_callback", [])) > 0

    def test_full_harness_all_affordances(self):
        """The complete harness pattern with all new affordances."""
        with tempfile.TemporaryDirectory() as tmp:
            agent = (
                Agent("coder", "gemini-2.5-flash")
                .instruct("Code in the workspace.")
                .tools(
                    H.workspace(tmp, diff_mode=True, multimodal=True)
                    + H.web(allow_network=False)
                    + H.processes(tmp)
                    + H.notebook(tmp)
                    + H.tasks()
                )
                .harness(
                    permissions=H.ask_before("bash").merge(H.auto_allow("read_file")),
                    sandbox=H.workspace_only(tmp),
                    usage=H.usage(),
                    memory=H.memory(os.path.join(tmp, ".memory.md")),
                    on_error=H.on_error(retry={"bash"}, skip={"glob_search"}),
                )
            )
            built = agent.build()
            assert built.name == "coder"
            # Verify tools were attached
            assert len(built.tools) > 7  # More than basic workspace


# ======================================================================
# H namespace completeness for new methods
# ======================================================================


class TestHNamespaceNewMethods:
    """Verify all new H methods exist and return correct types."""

    def test_web(self):
        tools = H.web(allow_network=False)
        assert isinstance(tools, list)

    def test_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = H.memory(os.path.join(tmp, "m.md"))
            assert isinstance(mem, ProjectMemory)

    def test_usage(self):
        t = H.usage()
        assert isinstance(t, UsageTracker)

    def test_processes(self):
        tools = H.processes()
        assert isinstance(tools, list)
        assert len(tools) == 3

    def test_mcp(self):
        tools = H.mcp([])
        assert isinstance(tools, list)

    def test_notebook(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.notebook(tmp)
            assert isinstance(tools, list)
            assert len(tools) == 2

    def test_tasks(self):
        tools = H.tasks()
        assert isinstance(tools, list)
        assert len(tools) == 3

    def test_on_error(self):
        s = H.on_error(retry={"bash"})
        assert isinstance(s, ErrorStrategy)

    def test_renderer_plain(self):
        r = H.renderer()
        assert isinstance(r, PlainRenderer)

    def test_renderer_json(self):
        r = H.renderer(format="json")
        assert isinstance(r, JsonRenderer)

    def test_workspace_diff_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.workspace(tmp, diff_mode=True)
            names = [t.__name__ for t in tools]
            assert "edit_file" in names
            assert "apply_edit" in names

    def test_workspace_multimodal(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.workspace(tmp, multimodal=True)
            names = [t.__name__ for t in tools]
            assert "read_file" in names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
