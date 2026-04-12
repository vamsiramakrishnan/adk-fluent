"""Tests for the 8 atomic foundations closing harness capability gaps.

Covers:
    F1: Pattern-based permission rules (glob/regex)
    F2: Git workspace tools (status, diff, log, commit, branch)
    F3: Memory search (BM25/substring over ProjectMemory)
    F4: SessionTape (event recording/replay/serialization)
    F5: SlashCommandRegistry (command dispatch)
    F6: Manifold hot-reload (unfreeze → re-discover)
    F7: Process tailing (tail, output_since)
    F8: Async LLM summarization (compress_messages_async)
"""

import asyncio
import tempfile
from unittest.mock import MagicMock

from adk_fluent import H
from adk_fluent._harness._commands import CommandRegistry
from adk_fluent._compression import CompressionStrategy, ContextCompressor
from adk_fluent._harness._events import TextChunk, ToolCallStart, TurnComplete
from adk_fluent._harness._manifold import (
    CapabilityEntry,
    CapabilityRegistry,
    CapabilityType,
    ManifoldToolset,
)
from adk_fluent._harness._memory import ProjectMemory
from adk_fluent._permissions import PermissionPolicy
from adk_fluent._session import SessionTape
from adk_fluent._tool_registry import ToolRegistry


def _run(coro):
    return asyncio.run(coro)


# ======================================================================
# F1: Pattern-based permission rules
# ======================================================================


class TestPatternPermissions:
    def test_glob_allow(self):
        policy = PermissionPolicy(allow_patterns=("read_*", "list_*"))
        assert policy.check("read_file").behavior == "allow"
        assert policy.check("read_notebook").behavior == "allow"
        assert policy.check("list_dir").behavior == "allow"
        assert policy.check("edit_file").behavior == "ask"

    def test_glob_deny(self):
        policy = PermissionPolicy(deny_patterns=("*dangerous*",))
        assert policy.check("run_dangerous_command").behavior == "deny"
        assert policy.check("safe_tool").behavior == "ask"

    def test_regex_mode(self):
        policy = PermissionPolicy(
            allow_patterns=("^(read|list)_.*$",),
            pattern_mode="regex",
        )
        assert policy.check("read_file").behavior == "allow"
        assert policy.check("list_dir").behavior == "allow"
        assert policy.check("edit_file").behavior == "ask"

    def test_exact_overrides_pattern(self):
        policy = PermissionPolicy(
            deny=frozenset(["read_secret"]),
            allow_patterns=("read_*",),
        )
        assert policy.check("read_secret").behavior == "deny"  # exact wins
        assert policy.check("read_file").behavior == "allow"  # pattern applies

    def test_merge_preserves_patterns(self):
        p1 = PermissionPolicy(allow_patterns=("read_*",))
        p2 = PermissionPolicy(deny_patterns=("*secret*",))
        merged = p1.merge(p2)
        assert merged.check("read_file").behavior == "allow"
        assert merged.check("read_secret").behavior == "deny"  # deny pattern wins
        assert merged.check("edit_file").behavior == "ask"

    def test_ask_patterns(self):
        policy = PermissionPolicy(ask_patterns=("bash*",))
        assert policy.check("bash").behavior == "ask"
        assert policy.check("bash_streaming").behavior == "ask"

    def test_h_allow_patterns(self):
        policy = H.allow_patterns("read_*", "list_*")
        assert policy.check("read_file").behavior == "allow"
        assert policy.check("bash").behavior == "ask"

    def test_h_deny_patterns(self):
        policy = H.deny_patterns("*dangerous*")
        assert policy.check("dangerous_tool").behavior == "deny"

    def test_h_patterns_compose_with_exact(self):
        policy = H.auto_allow("bash").merge(H.deny_patterns("*secret*"))
        assert policy.check("bash").behavior == "allow"
        assert policy.check("read_secret").behavior == "deny"


# ======================================================================
# F2: Git workspace tools
# ======================================================================


class TestGitTools:
    def test_git_tools_returns_list(self):
        tools = H.git_tools()
        assert isinstance(tools, list)
        assert len(tools) == 5  # status, diff, log, commit, branch
        names = [t.__name__ for t in tools]
        assert "git_status" in names
        assert "git_diff" in names
        assert "git_log" in names
        assert "git_commit" in names
        assert "git_branch" in names

    def test_git_tools_read_only(self):
        tools = H.git_tools(allow_shell=False)
        assert len(tools) == 3  # status, diff, log only
        names = [t.__name__ for t in tools]
        assert "git_commit" not in names
        assert "git_branch" not in names

    def test_git_status_callable(self):
        tools = H.git_tools("/tmp")
        status_fn = [t for t in tools if t.__name__ == "git_status"][0]
        result = status_fn()
        # May return clean or error — just verify it runs
        assert isinstance(result, str)

    def test_git_log_callable(self):
        tools = H.git_tools("/tmp")
        log_fn = [t for t in tools if t.__name__ == "git_log"][0]
        result = log_fn(n=5)
        assert isinstance(result, str)

    def test_composition_with_workspace(self):
        """Git tools compose with workspace tools via list concat."""
        ws_tools = H.workspace("/tmp", allow_shell=False, read_only=True)
        gt_tools = H.git_tools("/tmp", allow_shell=False)
        combined = ws_tools + gt_tools
        assert len(combined) > len(ws_tools)


# ======================================================================
# F3: Memory search
# ======================================================================


class TestMemorySearch:
    def test_search_empty_memory(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            mem = ProjectMemory(f.name)
        results = mem.search("anything")
        assert results == []

    def test_search_finds_entries(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                "- [2024-01-01 10:00] Database uses PostgreSQL with read replicas\n"
                "- [2024-01-02 11:00] Frontend uses React with TypeScript\n"
                "- [2024-01-03 12:00] API endpoints use FastAPI\n"
            )
            f.flush()
            mem = ProjectMemory(f.name)

        results = mem.search("database PostgreSQL")
        assert len(results) >= 1
        assert any("PostgreSQL" in r for r in results)

    def test_search_callback_returns_tool(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("- [2024-01-01 10:00] Uses Python 3.11\n")
            f.flush()
            mem = ProjectMemory(f.name)

        tool = mem.search_callback()
        assert callable(tool)
        assert tool.__name__ == "search_memory"

        result = tool("Python")
        assert "Python" in result

    def test_search_no_matches_falls_back(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("- [2024-01-01] Entry one\n- [2024-01-02] Entry two\n")
            f.flush()
            mem = ProjectMemory(f.name)

        # Substring fallback when BM25 finds nothing
        results = mem.search("zzzznonexistent")
        # Falls back to returning top entries
        assert isinstance(results, list)


# ======================================================================
# F4: SessionTape (recording/replay)
# ======================================================================


class TestSessionTape:
    def test_record_events(self):
        tape = SessionTape()
        tape.record(TextChunk(text="Hello"))
        tape.record(ToolCallStart(tool_name="bash", args={"cmd": "ls"}))
        tape.record(TurnComplete(response="Done"))

        assert tape.size == 3
        assert tape.events[0]["kind"] == "text"
        assert tape.events[1]["kind"] == "tool_call_start"
        assert tape.events[2]["kind"] == "turn_complete"

    def test_filter_by_kind(self):
        tape = SessionTape()
        tape.record(TextChunk(text="A"))
        tape.record(ToolCallStart(tool_name="bash"))
        tape.record(TextChunk(text="B"))

        texts = tape.filter("text")
        assert len(texts) == 2

    def test_save_and_load(self):
        tape = SessionTape()
        tape.record(TextChunk(text="Hello"))
        tape.record(TurnComplete(response="Done"))

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            tape.save(f.name)

            loaded = SessionTape.load(f.name)
            assert loaded.size == 2
            assert loaded.events[0]["text"] == "Hello"

    def test_summary(self):
        tape = SessionTape()
        tape.record(TextChunk(text="A"))
        tape.record(TextChunk(text="B"))
        tape.record(ToolCallStart(tool_name="x"))

        summary = tape.summary()
        assert summary["total_events"] == 3
        assert summary["event_counts"]["text"] == 2
        assert summary["event_counts"]["tool_call_start"] == 1

    def test_max_events(self):
        tape = SessionTape(max_events=2)
        tape.record(TextChunk(text="A"))
        tape.record(TextChunk(text="B"))
        tape.record(TextChunk(text="C"))
        assert tape.size == 2
        assert tape.events[0]["text"] == "B"  # oldest dropped

    def test_clear(self):
        tape = SessionTape()
        tape.record(TextChunk(text="A"))
        tape.clear()
        assert tape.size == 0

    def test_h_tape_factory(self):
        tape = H.tape()
        assert isinstance(tape, SessionTape)
        tape.record(TextChunk(text="test"))
        assert tape.size == 1

    def test_replay_alias(self):
        tape = SessionTape()
        tape.record(TextChunk(text="A"))
        assert tape.replay() == tape.events


# ======================================================================
# F5: SlashCommandRegistry
# ======================================================================


class TestCommandRegistry:
    def test_register_and_dispatch(self):
        reg = CommandRegistry()
        reg.register("hello", lambda args: f"Hello, {args}!")
        result = reg.dispatch("/hello world")
        assert result == "Hello, world!"

    def test_unknown_command(self):
        reg = CommandRegistry()
        result = reg.dispatch("/unknown")
        assert "Unknown command" in result

    def test_is_command(self):
        reg = CommandRegistry()
        assert reg.is_command("/test")
        assert not reg.is_command("just text")

    def test_help_text(self):
        reg = CommandRegistry()
        reg.register("clear", lambda a: "ok", description="Clear context")
        reg.register("model", lambda a: "ok", description="Switch model")

        help_text = reg.help_text()
        assert "/clear" in help_text
        assert "/model" in help_text
        assert "Clear context" in help_text

    def test_chaining(self):
        reg = CommandRegistry().register("a", lambda x: "a").register("b", lambda x: "b")
        assert reg.size == 2

    def test_no_args(self):
        reg = CommandRegistry()
        reg.register("status", lambda args: "all good")
        result = reg.dispatch("/status")
        assert result == "all good"

    def test_custom_prefix(self):
        reg = CommandRegistry(prefix="!")
        reg.register("help", lambda a: "help text")
        assert reg.is_command("!help")
        assert reg.dispatch("!help") == "help text"
        assert not reg.is_command("/help")

    def test_h_commands_factory(self):
        cmds = H.commands()
        assert isinstance(cmds, CommandRegistry)

    def test_list_commands(self):
        reg = CommandRegistry()
        reg.register("a", lambda x: "a", description="desc A")
        specs = reg.list_commands()
        assert len(specs) == 1
        assert specs[0].name == "a"


# ======================================================================
# F6: Manifold hot-reload
# ======================================================================


def _make_tool(name, doc=""):
    def fn(x: str) -> str:
        return f"{name}: {x}"

    fn.__name__ = name
    fn.__doc__ = doc or f"Tool {name}"
    return fn


class TestManifoldHotReload:
    def test_unfreeze_allows_new_loading(self):
        tool_reg = ToolRegistry()
        tool_reg.register(_make_tool("tool_a", "Tool A"))
        tool_reg.register(_make_tool("tool_b", "Tool B"))

        cap_reg = CapabilityRegistry()
        cap_reg.add_from_tool_registry(tool_reg)

        manifold = ManifoldToolset(cap_reg, tool_reg)
        manifold.load("tool_a")
        manifold.finalize()
        assert manifold.is_frozen

        # Can't load when frozen
        assert "finalized" in manifold.load("tool_b")

        # Unfreeze
        manifold.unfreeze()
        assert not manifold.is_frozen

        # Now can load more
        result = manifold.load("tool_b")
        assert "Loaded" in result

        manifold.finalize()
        ctx = MagicMock()
        ctx.state = {"manifold_phase": "execution"}
        tools = _run(manifold.get_tools(ctx))
        assert len(tools) == 2

    def test_unfreeze_returns_meta_tools(self):
        manifold = ManifoldToolset(CapabilityRegistry())
        manifold.finalize()
        manifold.unfreeze()

        ctx = MagicMock()
        ctx.state = {"manifold_phase": "discovery"}
        tools = _run(manifold.get_tools(ctx))
        assert len(tools) == 3  # meta-tools again

    def test_add_capability_at_runtime(self):
        cap_reg = CapabilityRegistry()
        manifold = ManifoldToolset(cap_reg)

        # Add capability mid-session
        manifold.add_capability(
            CapabilityEntry(
                name="new_tool",
                description="Dynamically added",
                cap_type=CapabilityType.TOOL,
            )
        )

        result = manifold.search("dynamically")
        assert "new_tool" in result


# ======================================================================
# F7: Process tailing
# ======================================================================


class TestProcessTailing:
    def test_tail_no_process(self):
        from adk_fluent._harness._processes import ProcessRegistry
        from adk_fluent._harness._sandbox import SandboxPolicy

        reg = ProcessRegistry(SandboxPolicy(allow_shell=True))
        result = reg.tail("nonexistent")
        assert "Error" in result

    def test_output_since_no_process(self):
        from adk_fluent._harness._processes import ProcessRegistry
        from adk_fluent._harness._sandbox import SandboxPolicy

        reg = ProcessRegistry(SandboxPolicy(allow_shell=True))
        output, offset = reg.output_since("nonexistent", 0)
        assert "Error" in output

    def test_tail_method_exists(self):
        from adk_fluent._harness._processes import ProcessRegistry
        from adk_fluent._harness._sandbox import SandboxPolicy

        reg = ProcessRegistry(SandboxPolicy(allow_shell=True))
        assert hasattr(reg, "tail")
        assert hasattr(reg, "output_since")


# ======================================================================
# F8: Async LLM summarization
# ======================================================================


class TestAsyncSummarization:
    def test_sync_compress_still_works(self):
        compressor = ContextCompressor(threshold=100)
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
            {"role": "user", "content": "Q3"},
            {"role": "assistant", "content": "A3"},
        ]
        result = compressor.compress_messages(msgs)
        assert any(m.get("role") == "system" for m in result)

    def test_async_compress_with_summarizer(self):
        compressor = ContextCompressor(
            threshold=100,
            strategy=CompressionStrategy(method="summarize", keep_turns=1),
        )
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "First question about Python"},
            {"role": "assistant", "content": "Python is great"},
            {"role": "user", "content": "Second question about Java"},
            {"role": "assistant", "content": "Java is typed"},
            {"role": "user", "content": "Third question about Rust"},
            {"role": "assistant", "content": "Rust is safe"},
            {"role": "user", "content": "Latest question"},
            {"role": "assistant", "content": "Latest answer"},
        ]

        async def mock_summarizer(text: str) -> str:
            return "Summary: discussed Python, Java, and Rust."

        result = _run(compressor.compress_messages_async(msgs, summarizer=mock_summarizer))

        # Should have system + summary + recent
        assert any(m.get("role") == "system" for m in result)
        assert any("Summary:" in m.get("content", "") for m in result)
        # Recent messages preserved
        assert any("Latest question" in m.get("content", "") for m in result)

    def test_async_compress_no_summarizer_falls_back(self):
        compressor = ContextCompressor(
            threshold=100,
            strategy=CompressionStrategy(method="summarize", keep_turns=1),
        )
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        result = _run(compressor.compress_messages_async(msgs))
        assert len(result) > 0  # falls back to keep_recent

    def test_async_compress_sync_summarizer(self):
        """Test that sync summarizer works in async context."""
        compressor = ContextCompressor(
            threshold=100,
            strategy=CompressionStrategy(method="summarize", keep_turns=1),
        )
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "q3"},
            {"role": "assistant", "content": "a3"},
        ]

        def sync_summarizer(text: str) -> str:
            return "Sync summary"

        result = _run(compressor.compress_messages_async(msgs, summarizer=sync_summarizer))
        assert any("Sync summary" in m.get("content", "") for m in result)


# ======================================================================
# Integration: H namespace coverage
# ======================================================================


class TestHNamespaceCompleteness:
    """Verify all new foundations are accessible via H."""

    def test_allow_patterns(self):
        assert hasattr(H, "allow_patterns")
        assert callable(H.allow_patterns)

    def test_deny_patterns(self):
        assert hasattr(H, "deny_patterns")
        assert callable(H.deny_patterns)

    def test_git_tools(self):
        assert hasattr(H, "git_tools")
        assert callable(H.git_tools)

    def test_tape(self):
        assert hasattr(H, "tape")
        assert callable(H.tape)

    def test_commands(self):
        assert hasattr(H, "commands")
        assert callable(H.commands)

    def test_manifold_has_unfreeze(self):
        manifold = H.manifold()
        assert hasattr(manifold, "unfreeze")
        assert hasattr(manifold, "add_capability")
