"""Tests for the H namespace — harness runtime primitives.

H provides sandboxed workspace tools, permission policies, and sandbox
policies for building CodAct-style agent runtimes.
"""

import os
import tempfile

import pytest

from adk_fluent import Agent, H
from adk_fluent._harness import (
    HarnessConfig,
    PermissionPolicy,
    SandboxPolicy,
    SkillSpec,
    TextChunk,
    ToolCallEnd,
    ToolCallStart,
    TurnComplete,
    _compile_skills_to_static,
    _make_bash,
    _make_edit_file,
    _make_glob_search,
    _make_grep_search,
    _make_list_dir,
    _make_read_file,
    _make_write_file,
)


# ======================================================================
# Permission policies
# ======================================================================


class TestPermissionPolicy:
    def test_ask_before(self):
        policy = H.ask_before("bash", "edit_file")
        assert policy.check("bash") == "ask"
        assert policy.check("edit_file") == "ask"
        assert policy.check("read_file") == "ask"  # default is ask

    def test_auto_allow(self):
        policy = H.auto_allow("read_file", "glob_search")
        assert policy.check("read_file") == "allow"
        assert policy.check("glob_search") == "allow"
        assert policy.check("bash") == "ask"  # unlisted defaults to ask

    def test_deny(self):
        policy = H.deny("bash")
        assert policy.check("bash") == "deny"
        assert policy.check("read_file") == "ask"

    def test_merge_policies(self):
        """Merge combines policies; deny wins over ask wins over allow."""
        allow_reads = H.auto_allow("read_file", "glob_search")
        ask_writes = H.ask_before("edit_file", "write_file")
        deny_shell = H.deny("bash")

        merged = allow_reads.merge(ask_writes).merge(deny_shell)
        assert merged.check("read_file") == "allow"
        assert merged.check("edit_file") == "ask"
        assert merged.check("bash") == "deny"

    def test_deny_overrides_allow(self):
        """If a tool is in both allow and deny, deny wins."""
        policy = H.auto_allow("bash").merge(H.deny("bash"))
        assert policy.check("bash") == "deny"


# ======================================================================
# Sandbox policies
# ======================================================================


class TestSandboxPolicy:
    def test_workspace_only(self):
        policy = H.workspace_only("/tmp/test-project")
        assert policy.workspace is not None
        assert "test-project" in policy.workspace

    def test_validate_path_inside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = SandboxPolicy(workspace=tmp)
            test_file = os.path.join(tmp, "file.txt")
            assert policy.validate_path(test_file, write=False)
            assert policy.validate_path(test_file, write=True)

    def test_validate_path_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = SandboxPolicy(workspace=tmp)
            assert not policy.validate_path("/etc/passwd", write=False)
            assert not policy.validate_path("/etc/passwd", write=True)

    def test_custom_sandbox(self):
        policy = H.sandbox(
            workspace="/project",
            allow_shell=False,
            allow_network=False,
        )
        assert not policy.allow_shell
        assert not policy.allow_network


# ======================================================================
# Workspace tools — sandboxed file operations
# ======================================================================


class TestWorkspaceTools:
    def test_workspace_returns_tools(self):
        """H.workspace() returns a list of tool functions."""
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.workspace(tmp)
            # Default: read, glob, grep, ls, edit, write, bash = 7
            assert len(tools) == 7
            names = [t.__name__ for t in tools]
            assert "read_file" in names
            assert "edit_file" in names
            assert "write_file" in names
            assert "glob_search" in names
            assert "grep_search" in names
            assert "bash" in names
            assert "list_dir" in names

    def test_workspace_read_only(self):
        """Read-only workspace excludes write tools."""
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.workspace(tmp, read_only=True)
            names = [t.__name__ for t in tools]
            assert "read_file" in names
            assert "edit_file" not in names
            assert "write_file" not in names

    def test_workspace_no_shell(self):
        """Disabling shell excludes bash tool."""
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.workspace(tmp, allow_shell=False)
            names = [t.__name__ for t in tools]
            assert "bash" not in names

    def test_read_file_tool(self):
        """read_file tool reads with line numbers."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = os.path.join(tmp, "test.py")
            with open(test_file, "w") as f:
                f.write("line1\nline2\nline3\n")

            sandbox = SandboxPolicy(workspace=tmp)
            read = _make_read_file(sandbox)
            result = read("test.py")
            assert "1\tline1" in result
            assert "2\tline2" in result

    def test_read_file_with_offset_limit(self):
        """read_file respects offset and limit."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = os.path.join(tmp, "test.py")
            with open(test_file, "w") as f:
                f.write("\n".join(f"line{i}" for i in range(100)))

            sandbox = SandboxPolicy(workspace=tmp)
            read = _make_read_file(sandbox)
            result = read("test.py", offset=10, limit=5)
            assert "11\tline10" in result
            assert "15\tline14" in result
            assert "16\t" not in result

    def test_read_file_outside_workspace_blocked(self):
        """read_file blocks reads outside workspace."""
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp)
            read = _make_read_file(sandbox)
            result = read("/etc/passwd")
            assert "Error" in result or "outside" in result

    def test_edit_file_tool(self):
        """edit_file does search-and-replace."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = os.path.join(tmp, "test.py")
            with open(test_file, "w") as f:
                f.write("hello world\n")

            sandbox = SandboxPolicy(workspace=tmp)
            edit = _make_edit_file(sandbox)
            result = edit("test.py", "hello", "goodbye")
            assert "Successfully" in result

            with open(test_file) as f:
                assert "goodbye world" in f.read()

    def test_edit_file_unique_check(self):
        """edit_file rejects non-unique matches."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = os.path.join(tmp, "test.py")
            with open(test_file, "w") as f:
                f.write("aaa\naaa\n")

            sandbox = SandboxPolicy(workspace=tmp)
            edit = _make_edit_file(sandbox)
            result = edit("test.py", "aaa", "bbb")
            assert "appears 2 times" in result

    def test_write_file_tool(self):
        """write_file creates new files."""
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp)
            write = _make_write_file(sandbox)
            result = write("new_file.py", "print('hello')")
            assert "Successfully" in result

            with open(os.path.join(tmp, "new_file.py")) as f:
                assert "print('hello')" in f.read()

    def test_write_file_creates_directories(self):
        """write_file creates parent directories."""
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp)
            write = _make_write_file(sandbox)
            result = write("deep/nested/file.py", "content")
            assert "Successfully" in result
            assert os.path.exists(os.path.join(tmp, "deep/nested/file.py"))

    def test_glob_search_tool(self):
        """glob_search finds files by pattern."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create some files
            os.makedirs(os.path.join(tmp, "src"))
            for name in ["a.py", "b.py", "c.txt"]:
                open(os.path.join(tmp, "src", name), "w").close()

            sandbox = SandboxPolicy(workspace=tmp)
            glob = _make_glob_search(sandbox)
            result = glob("**/*.py")
            assert "a.py" in result
            assert "b.py" in result
            assert "c.txt" not in result

    def test_grep_search_tool(self):
        """grep_search finds content in files."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = os.path.join(tmp, "test.py")
            with open(test_file, "w") as f:
                f.write("def hello():\n    return 'world'\n")

            sandbox = SandboxPolicy(workspace=tmp)
            grep = _make_grep_search(sandbox)
            result = grep("def hello")
            assert "test.py:1:" in result

    def test_bash_tool(self):
        """bash executes commands in workspace."""
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp, allow_shell=True)
            bash = _make_bash(sandbox)
            result = bash("echo 'hello from bash'")
            assert "hello from bash" in result

    def test_bash_disabled(self):
        """bash tool respects allow_shell=False."""
        sandbox = SandboxPolicy(allow_shell=False)
        bash = _make_bash(sandbox)
        result = bash("echo 'should not work'")
        assert "disabled" in result

    def test_bash_timeout(self):
        """bash respects timeout."""
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp, allow_shell=True)
            bash = _make_bash(sandbox)
            result = bash("sleep 10", timeout=1)
            assert "timed out" in result

    def test_list_dir_tool(self):
        """list_dir shows directory contents."""
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "file.py"), "w").close()
            os.makedirs(os.path.join(tmp, "subdir"))

            sandbox = SandboxPolicy(workspace=tmp)
            ls = _make_list_dir(sandbox)
            result = ls()
            assert "f file.py" in result
            assert "d subdir" in result


# ======================================================================
# .harness() on Agent
# ======================================================================


class TestHarnessOnAgent:
    def test_harness_wires_permission_callback(self):
        """Calling .harness() with permissions registers before_tool callback."""
        agent = (
            Agent("coder", "gemini-2.5-flash")
            .instruct("Code things.")
            .harness(permissions=H.ask_before("bash"))
        )
        # Check that callbacks were registered
        assert len(agent._callbacks.get("before_tool_callback", [])) > 0

    def test_harness_stores_config(self):
        """Harness config is stored in _config."""
        agent = (
            Agent("coder", "gemini-2.5-flash")
            .instruct("Code things.")
            .harness(
                permissions=H.ask_before("bash"),
                sandbox=H.workspace_only("/tmp"),
                auto_compress=50_000,
            )
        )
        cfg = agent._config.get("_harness_config")
        assert isinstance(cfg, HarnessConfig)
        assert cfg.auto_compress_threshold == 50_000

    def test_harness_builds_successfully(self):
        """Agent with .harness() builds into a valid ADK agent."""
        agent = (
            Agent("coder", "gemini-2.5-flash")
            .instruct("Code things.")
            .harness(permissions=H.ask_before("bash"))
        )
        built = agent.build()
        assert built.name == "coder"

    def test_full_harness_pattern(self):
        """The complete harness pattern: skill + workspace + permissions."""
        with tempfile.TemporaryDirectory() as tmp:
            agent = (
                Agent("coder", "gemini-2.5-flash")
                .use_skill("examples/skills/code_reviewer/")
                .instruct("Review the code in the workspace.")
                .tools(H.workspace(tmp, read_only=True))
                .harness(
                    permissions=H.auto_allow("read_file", "glob_search"),
                )
            )
            built = agent.build()
            assert "<skills>" in (built.static_instruction or "")
            assert len(built.tools) > 0


# ======================================================================
# Event dataclasses
# ======================================================================


class TestHarnessEvents:
    def test_text_chunk(self):
        event = TextChunk(text="Hello")
        assert event.kind == "text"
        assert event.text == "Hello"

    def test_tool_call_start(self):
        event = ToolCallStart(tool_name="bash", args={"command": "ls"})
        assert event.kind == "tool_call_start"

    def test_tool_call_end(self):
        event = ToolCallEnd(tool_name="bash", result="file.py")
        assert event.kind == "tool_call_end"

    def test_turn_complete(self):
        event = TurnComplete(response="Done!")
        assert event.kind == "turn_complete"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
