"""Tests for the 3 remaining gap-closing features.

Covers:
    1. Interrupt & Resume (CancellationToken, TurnSnapshot, callbacks)
    2. Memory Hierarchy (multi-file, merged load, unified search)
    3. Conversation Forking (fork, switch, merge, diff, callbacks)
"""

import tempfile
import threading
import time
from unittest.mock import MagicMock

from adk_fluent import H
from adk_fluent._harness._interrupt import (
    CancellationToken,
    TurnSnapshot,
    make_cancellation_callback,
)
from adk_fluent._harness._memory import MemoryHierarchy
from adk_fluent._session import ForkManager

# ======================================================================
# 1. Interrupt & Resume
# ======================================================================


class TestCancellationToken:
    def test_initial_state(self):
        token = CancellationToken()
        assert not token.is_cancelled
        assert token.snapshot is None

    def test_cancel_sets_flag(self):
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled

    def test_reset_clears_flag(self):
        token = CancellationToken()
        token.cancel()
        token.reset()
        assert not token.is_cancelled
        assert token.snapshot is None

    def test_cancel_captures_snapshot(self):
        token = CancellationToken()
        token.begin_turn("Fix the bug")
        token.record_tool_call("read_file", {"path": "main.py"})
        token.record_tool_call("bash", {"cmd": "pytest"})
        token.cancel()

        snapshot = token.snapshot
        assert snapshot is not None
        assert snapshot.prompt == "Fix the bug"
        assert len(snapshot.tool_calls_completed) == 2
        assert snapshot.tool_calls_completed[0]["tool_name"] == "read_file"

    def test_thread_safety(self):
        token = CancellationToken()
        token.begin_turn("test")

        def cancel_from_thread():
            time.sleep(0.01)
            token.cancel()

        t = threading.Thread(target=cancel_from_thread)
        t.start()
        t.join()
        assert token.is_cancelled

    def test_h_factory(self):
        token = H.cancellation_token()
        assert isinstance(token, CancellationToken)
        assert not token.is_cancelled


class TestTurnSnapshot:
    def test_resume_prompt_basic(self):
        snapshot = TurnSnapshot(prompt="Fix the bug")
        prompt = snapshot.resume_prompt()
        assert "Fix the bug" in prompt
        assert "Resuming" in prompt

    def test_resume_prompt_with_completed_tools(self):
        snapshot = TurnSnapshot(
            prompt="Refactor auth",
            tool_calls_completed=[
                {"tool_name": "read_file", "args": {}},
                {"tool_name": "grep_search", "args": {}},
            ],
            tool_call_interrupted="edit_file",
        )
        prompt = snapshot.resume_prompt()
        assert "Refactor auth" in prompt
        assert "read_file" in prompt
        assert "grep_search" in prompt
        assert "edit_file" in prompt
        assert "Interrupted during" in prompt


class TestCancellationCallback:
    def test_allows_when_not_cancelled(self):
        token = CancellationToken()
        cb = make_cancellation_callback(token)
        mock_tool = MagicMock()
        mock_tool.name = "bash"

        result = cb(tool=mock_tool, args={"cmd": "ls"}, tool_context=MagicMock())
        assert result is None  # allow execution

    def test_blocks_when_cancelled(self):
        token = CancellationToken()
        token.cancel()
        cb = make_cancellation_callback(token)
        mock_tool = MagicMock()
        mock_tool.name = "bash"

        result = cb(tool=mock_tool, args={"cmd": "ls"}, tool_context=MagicMock())
        assert isinstance(result, dict)
        assert "cancelled" in result["error"].lower()

    def test_records_tool_calls(self):
        token = CancellationToken()
        token.begin_turn("test")
        cb = make_cancellation_callback(token)
        mock_tool = MagicMock()
        mock_tool.name = "read_file"

        cb(tool=mock_tool, args={"path": "x.py"}, tool_context=MagicMock())
        assert len(token._tool_calls) == 1

    def test_records_interrupted_tool(self):
        token = CancellationToken()
        token.begin_turn("test")
        cb = make_cancellation_callback(token)

        # First call succeeds
        mock_tool1 = MagicMock()
        mock_tool1.name = "read_file"
        cb(tool=mock_tool1, args={}, tool_context=MagicMock())

        # Cancel before second call
        token.cancel()
        mock_tool2 = MagicMock()
        mock_tool2.name = "edit_file"
        result = cb(tool=mock_tool2, args={}, tool_context=MagicMock())

        assert result is not None  # blocked
        assert token.snapshot.tool_call_interrupted == "edit_file"


# ======================================================================
# 2. Memory Hierarchy
# ======================================================================


class TestMemoryHierarchy:
    def _create_temp_memory(self, content: str) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            return f.name

    def test_load_merges_files(self):
        global_file = self._create_temp_memory("- Global setting: use dark mode\n")
        project_file = self._create_temp_memory("- Project uses Python 3.11\n")

        hierarchy = MemoryHierarchy(global_file, project_file)
        content = hierarchy.load()

        assert "Global setting" in content
        assert "Python 3.11" in content

    def test_load_skips_missing_files(self):
        existing = self._create_temp_memory("- Exists\n")
        hierarchy = MemoryHierarchy("/nonexistent/file.md", existing)
        content = hierarchy.load()
        assert "Exists" in content

    def test_search_across_files(self):
        file1 = self._create_temp_memory("- [2024-01-01] Database uses PostgreSQL\n")
        file2 = self._create_temp_memory("- [2024-01-02] Frontend uses React\n")

        hierarchy = MemoryHierarchy(file1, file2)
        results = hierarchy.search("PostgreSQL")
        assert any("PostgreSQL" in r for r in results)

    def test_levels_property(self):
        f1 = self._create_temp_memory("")
        f2 = self._create_temp_memory("")
        hierarchy = MemoryHierarchy(f1, f2)
        assert hierarchy.levels == 2

    def test_load_callback(self):
        f = self._create_temp_memory("- Important note\n")
        hierarchy = MemoryHierarchy(f, state_key="mem")
        cb = hierarchy.load_callback()

        ctx = MagicMock()
        ctx.state = {}
        cb(ctx)
        assert "Important note" in ctx.state["mem"]

    def test_search_callback(self):
        f = self._create_temp_memory("- [2024] Uses TypeScript\n")
        hierarchy = MemoryHierarchy(f)
        tool = hierarchy.search_callback()
        assert callable(tool)
        result = tool("TypeScript")
        assert "TypeScript" in result

    def test_append_to_level(self):
        f = self._create_temp_memory("")
        hierarchy = MemoryHierarchy(f)
        hierarchy.append("New entry", level=-1)
        content = hierarchy.load()
        assert "New entry" in content

    def test_h_memory_hierarchy_factory(self):
        f = self._create_temp_memory("- test\n")
        hierarchy = H.memory_hierarchy(f)
        assert isinstance(hierarchy, MemoryHierarchy)
        assert hierarchy.levels == 1

    def test_paths_property(self):
        f1 = self._create_temp_memory("")
        f2 = self._create_temp_memory("")
        hierarchy = MemoryHierarchy(f1, f2)
        assert len(hierarchy.paths) == 2


# ======================================================================
# 3. Conversation Forking
# ======================================================================


class TestForkManager:
    def test_fork_and_switch(self):
        forks = ForkManager()
        state_a = {"topic": "Python", "depth": 3}
        forks.fork("approach_a", state_a)

        state_b = {"topic": "Rust", "depth": 1}
        forks.fork("approach_b", state_b)

        restored = forks.switch("approach_a")
        assert restored["topic"] == "Python"
        assert forks.active == "approach_a"

    def test_fork_deep_copies_state(self):
        forks = ForkManager()
        state = {"items": [1, 2, 3]}
        forks.fork("test", state)

        # Mutate original
        state["items"].append(4)

        # Branch should be unaffected
        restored = forks.switch("test")
        assert restored["items"] == [1, 2, 3]

    def test_switch_nonexistent_raises(self):
        import pytest

        forks = ForkManager()
        with pytest.raises(KeyError):
            forks.switch("nonexistent")

    def test_merge_union(self):
        forks = ForkManager()
        forks.fork("a", {"x": 1, "shared": "from_a"})
        forks.fork("b", {"y": 2, "shared": "from_b"})

        merged = forks.merge("a", "b", strategy="union")
        assert merged["x"] == 1
        assert merged["y"] == 2
        assert merged["shared"] == "from_b"  # last wins

    def test_merge_intersection(self):
        forks = ForkManager()
        forks.fork("a", {"x": 1, "shared": 10})
        forks.fork("b", {"y": 2, "shared": 20})

        merged = forks.merge("a", "b", strategy="intersection")
        assert "shared" in merged
        assert "x" not in merged
        assert "y" not in merged

    def test_merge_prefer(self):
        forks = ForkManager()
        forks.fork("a", {"key": "value_a"})
        forks.fork("b", {"key": "value_b"})

        merged = forks.merge("a", "b", strategy="prefer", prefer="a")
        assert merged["key"] == "value_a"

    def test_diff(self):
        forks = ForkManager()
        forks.fork("a", {"x": 1, "shared": 10, "same": True})
        forks.fork("b", {"y": 2, "shared": 20, "same": True})

        diff = forks.diff("a", "b")
        assert "x" in diff["only_a"]
        assert "y" in diff["only_b"]
        assert "shared" in diff["different"]
        assert "same" in diff["same"]

    def test_delete_branch(self):
        forks = ForkManager()
        forks.fork("test", {"a": 1})
        forks.delete("test")
        assert forks.size == 0

    def test_list_branches(self):
        forks = ForkManager()
        forks.fork("a", {"x": 1})
        forks.fork("b", {"y": 2})

        branches = forks.list_branches()
        assert len(branches) == 2
        names = {b["name"] for b in branches}
        assert names == {"a", "b"}

    def test_max_branches_eviction(self):
        forks = ForkManager(max_branches=2)
        forks.fork("first", {"a": 1})
        time.sleep(0.01)
        forks.fork("second", {"b": 2})
        time.sleep(0.01)
        forks.fork("third", {"c": 3})  # evicts "first"

        assert forks.size == 2
        assert "first" not in {b["name"] for b in forks.list_branches()}

    def test_parent_tracking(self):
        forks = ForkManager()
        forks.fork("main", {"x": 1})
        forks.fork("feature", {"x": 2})  # parent = "main"

        branch = forks.get("feature")
        assert branch.parent == "main"

    def test_save_callback(self):
        forks = ForkManager()
        cb = forks.save_callback("auto_branch")

        ctx = MagicMock()
        ctx.state = MagicMock()
        ctx.state.items.return_value = [("key", "value")]
        cb(ctx)

        assert forks.size == 1
        assert "auto_branch" in {b["name"] for b in forks.list_branches()}

    def test_restore_callback(self):
        forks = ForkManager()
        forks.fork("saved", {"restored_key": "restored_value"})

        cb = forks.restore_callback("saved")
        ctx = MagicMock()
        ctx.state = MagicMock()
        cb(ctx)

        ctx.state.update.assert_called_once()
        restored_arg = ctx.state.update.call_args[0][0]
        assert restored_arg["restored_key"] == "restored_value"

    def test_h_forks_factory(self):
        forks = H.forks()
        assert isinstance(forks, ForkManager)

    def test_metadata(self):
        forks = ForkManager()
        forks.fork("test", {"a": 1}, reason="experiment", attempt=3)
        branch = forks.get("test")
        assert branch.metadata["reason"] == "experiment"
        assert branch.metadata["attempt"] == 3


# ======================================================================
# Integration
# ======================================================================


class TestIntegration:
    def test_interrupt_with_tape(self):
        """CancellationToken composes with SessionTape."""
        from adk_fluent._harness._events import TextChunk, ToolCallStart

        token = H.cancellation_token()
        tape = H.tape()

        # Simulate a turn
        token.begin_turn("Fix bugs")
        event1 = TextChunk(text="Looking at the code...")
        event2 = ToolCallStart(tool_name="read_file", args={"path": "bug.py"})

        tape.record(event1)
        tape.record(event2)
        token.record_event(event1)
        token.record_event(event2)

        # Interrupt
        token.cancel()
        snapshot = token.snapshot
        assert snapshot.prompt == "Fix bugs"
        assert tape.size == 2

    def test_fork_with_memory(self):
        """ForkManager composes with ProjectMemory state."""
        forks = H.forks()

        # Simulate two approaches with different state
        forks.fork(
            "conservative",
            {
                "approach": "incremental",
                "files_changed": ["a.py"],
            },
        )
        forks.fork(
            "aggressive",
            {
                "approach": "rewrite",
                "files_changed": ["a.py", "b.py", "c.py"],
            },
        )

        # Compare approaches
        diff = forks.diff("conservative", "aggressive")
        assert "approach" in diff["different"]

        # Merge: take conservative approach but include aggressive file list
        merged = forks.merge("conservative", "aggressive", strategy="union")
        assert merged["approach"] == "rewrite"  # last wins
        assert len(merged["files_changed"]) == 3

    def test_all_h_methods_exist(self):
        """All new H methods are accessible."""
        assert callable(H.cancellation_token)
        assert callable(H.forks)
        assert callable(H.memory_hierarchy)
