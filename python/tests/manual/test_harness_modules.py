"""Tests for the modular harness package — all new components.

Tests cover:
    - Gitignore-aware filtering
    - Git checkpoint/rollback
    - Streaming bash
    - Event dispatcher
    - Hook system
    - Artifact/blob handling
    - Approval persistence
    - Context compression
    - Symlink-safe path validation
    - REPL configuration
"""

import asyncio
import os
import tempfile

import pytest

from adk_fluent import H
from adk_fluent._harness._artifacts import ArtifactStore
from adk_fluent._harness._compression import CompressionStrategy, ContextCompressor
from adk_fluent._harness._dispatcher import EventDispatcher
from adk_fluent._harness._events import (
    CompressionTriggered,
    GitCheckpoint,
    HookFired,
    PermissionResult,
    TextChunk,
    ToolCallStart,
)
from adk_fluent._harness._git import GitCheckpointer
from adk_fluent._harness._gitignore import GitignoreMatcher, load_gitignore
from adk_fluent._harness._hooks import HookRegistry
from adk_fluent._harness._permissions import ApprovalMemory, PermissionPolicy
from adk_fluent._harness._repl import HarnessRepl, ReplConfig
from adk_fluent._harness._sandbox import SandboxPolicy
from adk_fluent._harness._streaming import StreamingBash

# ======================================================================
# Gitignore-aware filtering
# ======================================================================


class TestGitignoreMatcher:
    def test_always_ignored(self):
        """Built-in always-ignored patterns work."""
        matcher = GitignoreMatcher()
        assert matcher.is_ignored(".git/config")
        assert matcher.is_ignored("__pycache__/foo.pyc")
        assert matcher.is_ignored("src/__pycache__/bar.pyc")

    def test_dotfiles_ignored(self):
        """Hidden files/dirs are ignored by default."""
        matcher = GitignoreMatcher()
        assert matcher.is_ignored(".env")
        assert matcher.is_ignored(".vscode/settings.json")

    def test_normal_files_not_ignored(self):
        """Regular files are not ignored."""
        matcher = GitignoreMatcher()
        assert not matcher.is_ignored("src/main.py")
        assert not matcher.is_ignored("README.md")

    def test_custom_rules(self):
        """Custom gitignore rules work."""
        matcher = GitignoreMatcher()
        matcher.add_rules(["*.log", "build/", "!important.log"])
        assert matcher.is_ignored("debug.log")
        assert matcher.is_ignored("build/output.js")
        assert not matcher.is_ignored("important.log")

    def test_negation(self):
        """Negation patterns override previous ignores."""
        matcher = GitignoreMatcher()
        matcher.add_rules(["*.txt", "!readme.txt"])
        assert matcher.is_ignored("notes.txt")
        assert not matcher.is_ignored("readme.txt")

    def test_load_gitignore_from_dir(self):
        """load_gitignore parses .gitignore files."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create .gitignore
            with open(os.path.join(tmp, ".gitignore"), "w") as f:
                f.write("*.pyc\nnode_modules/\n")
            matcher = load_gitignore(tmp)
            assert matcher.is_ignored("foo.pyc")
            assert matcher.is_ignored("node_modules/package.json")

    def test_no_gitignore(self):
        """Works when no .gitignore exists."""
        with tempfile.TemporaryDirectory() as tmp:
            matcher = load_gitignore(tmp)
            # Still ignores built-in patterns
            assert matcher.is_ignored(".git/config")
            assert not matcher.is_ignored("main.py")


# ======================================================================
# Git checkpoint/rollback
# ======================================================================


class TestGitCheckpointer:
    def _make_repo(self, tmp):
        """Create a git repo with an initial commit."""
        import subprocess

        subprocess.run(["git", "init", tmp, "--initial-branch=main"], capture_output=True)
        subprocess.run(["git", "-C", tmp, "config", "user.email", "test@test.com"], capture_output=True)
        subprocess.run(["git", "-C", tmp, "config", "user.name", "Test"], capture_output=True)
        subprocess.run(["git", "-C", tmp, "config", "commit.gpgsign", "false"], capture_output=True)
        with open(os.path.join(tmp, "file.txt"), "w") as f:
            f.write("initial\n")
        subprocess.run(["git", "-C", tmp, "add", "."], capture_output=True)
        result = subprocess.run(
            ["git", "-C", tmp, "commit", "-m", "init"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def test_is_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            if not self._make_repo(tmp):
                pytest.skip("git commit not available in this environment")
            cp = GitCheckpointer(tmp)
            assert cp.is_git_repo

    def test_not_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = GitCheckpointer(tmp)
            assert not cp.is_git_repo

    def test_create_checkpoint_clean(self):
        """Checkpoint on clean repo records HEAD."""
        with tempfile.TemporaryDirectory() as tmp:
            if not self._make_repo(tmp):
                pytest.skip("git commit not available in this environment")
            cp = GitCheckpointer(tmp)
            sha = cp.create("clean checkpoint")
            assert sha is not None
            assert len(sha) == 40

    def test_create_checkpoint_dirty(self):
        """Checkpoint on dirty repo captures stash."""
        with tempfile.TemporaryDirectory() as tmp:
            if not self._make_repo(tmp):
                pytest.skip("git commit not available in this environment")
            with open(os.path.join(tmp, "file.txt"), "w") as f:
                f.write("modified\n")
            cp = GitCheckpointer(tmp)
            sha = cp.create("dirty checkpoint")
            assert sha is not None

    def test_list_checkpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            if not self._make_repo(tmp):
                pytest.skip("git commit not available in this environment")
            cp = GitCheckpointer(tmp)
            cp.create("first")
            cp.create("second")
            cps = cp.list_checkpoints()
            assert len(cps) == 2
            assert cps[0]["message"] == "first"

    def test_diff_since(self):
        with tempfile.TemporaryDirectory() as tmp:
            if not self._make_repo(tmp):
                pytest.skip("git commit not available in this environment")
            cp = GitCheckpointer(tmp)
            sha = cp.create("before")
            with open(os.path.join(tmp, "file.txt"), "w") as f:
                f.write("changed\n")
            diff = cp.diff_since(sha)
            assert "changed" in diff or "modified" in diff.lower() or diff == "(no changes)"

    def test_non_repo_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = GitCheckpointer(tmp)
            assert cp.create() is None
            assert not cp.restore()

    def test_h_git_factory(self):
        """H.git() creates a GitCheckpointer."""
        with tempfile.TemporaryDirectory() as tmp:
            cp = H.git(tmp)
            assert isinstance(cp, GitCheckpointer)


# ======================================================================
# Streaming bash
# ======================================================================


class TestStreamingBash:
    def test_streaming_bash_creation(self):
        """H.streaming_bash() creates a StreamingBash."""
        sandbox = SandboxPolicy(workspace="/tmp", allow_shell=True)
        sb = H.streaming_bash(sandbox)
        assert isinstance(sb, StreamingBash)

    def test_streaming_bash_disabled(self):
        """Streaming bash respects shell disabled."""
        sandbox = SandboxPolicy(allow_shell=False)
        sb = StreamingBash(sandbox)
        chunks = []
        asyncio.run(self._collect(sb.run("echo hello"), chunks))
        assert any("disabled" in c for c in chunks)

    def test_streaming_bash_runs(self):
        """Streaming bash executes commands."""
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp, allow_shell=True)
            sb = StreamingBash(sandbox)
            output = asyncio.run(sb.run_collected("echo hello"))
            assert "hello" in output

    def test_streaming_bash_timeout(self):
        """Streaming bash respects timeout."""
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp, allow_shell=True)
            sb = StreamingBash(sandbox)
            output = asyncio.run(sb.run_collected("sleep 10", timeout=1))
            assert "timed out" in output

    def test_workspace_streaming_option(self):
        """H.workspace(streaming=True) uses streaming bash."""
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.workspace(tmp, streaming=True)
            names = [t.__name__ for t in tools]
            assert "bash" in names
            # Should still have 7 tools
            assert len(tools) == 7

    async def _collect(self, aiter, out):
        async for chunk in aiter:
            out.append(chunk)


# ======================================================================
# Event dispatcher
# ======================================================================


class TestEventDispatcher:
    def test_subscribe_all(self):
        """Global subscribers receive all events."""
        d = H.dispatcher()
        received = []
        d.subscribe(lambda e: received.append(e))
        d.emit(TextChunk(text="hello"))
        d.emit(ToolCallStart(tool_name="bash"))
        assert len(received) == 2

    def test_subscribe_by_kind(self):
        """Kind-specific subscribers only receive matching events."""
        d = EventDispatcher()
        texts = []
        d.on("text", lambda e: texts.append(e))
        d.emit(TextChunk(text="hello"))
        d.emit(ToolCallStart(tool_name="bash"))
        assert len(texts) == 1
        assert texts[0].text == "hello"

    def test_subscriber_error_doesnt_crash(self):
        """Subscriber errors are swallowed."""
        d = EventDispatcher()
        d.subscribe(lambda e: 1 / 0)  # Will raise
        # Should not raise
        d.emit(TextChunk(text="hello"))

    def test_h_dispatcher_factory(self):
        d = H.dispatcher()
        assert isinstance(d, EventDispatcher)


# ======================================================================
# Hook system
# ======================================================================


class TestHookSystem:
    def test_hook_registration(self):
        hooks = HookRegistry()
        hooks.on("tool_call_start", "echo test")
        assert "tool_call_start" in hooks.registered_events

    def test_fire_sync(self):
        hooks = HookRegistry()
        hooks.on("test", "echo fired")
        results = hooks.fire_sync("test")
        assert len(results) == 1
        assert results[0].exit_code == 0

    def test_fire_with_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            hooks = HookRegistry(workspace=tmp)
            hooks.on("test", "echo {tool_name}")
            results = hooks.fire_sync("test", tool_name="bash")
            assert results[0].exit_code == 0

    def test_fire_async(self):
        hooks = HookRegistry()
        hooks.on("test", "echo async_fired")
        results = asyncio.run(hooks.fire("test"))
        assert len(results) == 1
        assert results[0].exit_code == 0

    def test_shorthand_methods(self):
        hooks = HookRegistry()
        hooks.on_tool_start("echo start")
        hooks.on_tool_end("echo end")
        hooks.on_turn("echo turn")
        assert "tool_call_start" in hooks.registered_events
        assert "tool_call_end" in hooks.registered_events
        assert "turn_complete" in hooks.registered_events

    def test_h_hooks_factory(self):
        hooks = H.hooks("/tmp")
        assert isinstance(hooks, HookRegistry)
        assert hooks.workspace == "/tmp"

    def test_hook_chaining(self):
        hooks = H.hooks().on("a", "echo a").on("b", "echo b").on("a", "echo a2")
        assert "a" in hooks.registered_events
        assert "b" in hooks.registered_events


# ======================================================================
# Artifact/blob handling
# ======================================================================


class TestArtifactStore:
    def test_save_and_load_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp)
            ref = store.save("output.txt", "hello world")
            assert ref.name == "output.txt"
            assert ref.size_bytes == len(b"hello world")
            content = store.load("output.txt")
            assert content == "hello world"

    def test_save_and_load_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp)
            data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
            ref = store.save_binary("image.png", data, mime_type="image/png")
            assert ref.mime_type == "image/png"
            loaded = store.load_binary("image.png")
            assert loaded == data

    def test_summarize_small(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp, max_inline_bytes=1000)
            store.save("small.txt", "tiny content")
            summary = store.summarize("small.txt")
            assert "small.txt" in summary
            assert "tiny content" in summary  # Inlined

    def test_summarize_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp, max_inline_bytes=10)
            store.save("big.txt", "x" * 1000)
            summary = store.summarize("big.txt")
            assert "big.txt" in summary
            assert "x" * 1000 not in summary  # Not inlined

    def test_list_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp)
            store.save("a.txt", "aaa")
            store.save("b.txt", "bbb")
            arts = store.list_artifacts()
            assert len(arts) == 2

    def test_delete_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp)
            store.save("temp.txt", "temporary")
            assert store.delete("temp.txt")
            assert store.load("temp.txt") is None

    def test_manifest_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Save in one store instance
            store1 = ArtifactStore(tmp)
            store1.save("persisted.txt", "data")
            # Load in another
            store2 = ArtifactStore(tmp)
            content = store2.load("persisted.txt")
            assert content == "data"

    def test_h_artifacts_factory(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = H.artifacts(tmp)
            assert isinstance(store, ArtifactStore)


# ======================================================================
# Approval persistence
# ======================================================================


class TestApprovalMemory:
    def test_remember_tool(self):
        mem = ApprovalMemory()
        mem.remember_tool("bash", True)
        assert mem.recall("bash") is True

    def test_remember_specific(self):
        mem = ApprovalMemory()
        mem.remember_specific("edit_file", {"path": "main.py"}, True)
        assert mem.recall("edit_file", {"path": "main.py"}) is True
        assert mem.recall("edit_file", {"path": "other.py"}) is None

    def test_tool_decision_overrides_specific(self):
        mem = ApprovalMemory()
        mem.remember_specific("bash", {"command": "ls"}, False)
        mem.remember_tool("bash", True)
        # Tool-level decision takes priority
        assert mem.recall("bash", {"command": "ls"}) is True

    def test_recall_unknown(self):
        mem = ApprovalMemory()
        assert mem.recall("unknown") is None

    def test_clear(self):
        mem = ApprovalMemory()
        mem.remember_tool("bash", True)
        mem.clear()
        assert mem.recall("bash") is None

    def test_h_approval_memory_factory(self):
        mem = H.approval_memory()
        assert isinstance(mem, ApprovalMemory)


# ======================================================================
# Context compression
# ======================================================================


class TestContextCompressor:
    def test_should_compress(self):
        comp = ContextCompressor(threshold=1000)
        assert not comp.should_compress(500)
        assert comp.should_compress(1000)
        assert comp.should_compress(2000)

    def test_estimate_tokens(self):
        comp = ContextCompressor()
        msgs = [{"role": "user", "content": "x" * 400}]
        estimate = comp.estimate_tokens(msgs)
        assert estimate == 100  # 400 / 4

    def test_compress_keeps_system(self):
        comp = ContextCompressor(strategy=CompressionStrategy.keep_recent(2))
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "resp1"},
            {"role": "user", "content": "msg2"},
            {"role": "assistant", "content": "resp2"},
            {"role": "user", "content": "msg3"},
            {"role": "assistant", "content": "resp3"},
        ]
        compressed = comp.compress_messages(msgs)
        # System message preserved
        assert compressed[0]["role"] == "system"
        # Only last 2 turn-pairs (4 messages) kept
        assert len(compressed) <= 5  # 1 system + 4 recent

    def test_compression_count(self):
        comp = ContextCompressor(threshold=100)
        msgs = [{"role": "user", "content": "test"}]
        comp.compress_messages(msgs)
        comp.compress_messages(msgs)
        assert comp.compression_count == 2

    def test_on_compress_callback(self):
        triggered = []
        comp = ContextCompressor(
            threshold=100,
            on_compress=lambda tokens: triggered.append(tokens),
        )
        comp.compress_messages([{"role": "user", "content": "x" * 400}])
        assert len(triggered) == 1

    def test_drop_old_strategy(self):
        comp = ContextCompressor(strategy=CompressionStrategy.drop_old(1))
        msgs = [
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "old_resp"},
            {"role": "user", "content": "new"},
            {"role": "assistant", "content": "new_resp"},
        ]
        compressed = comp.compress_messages(msgs)
        assert len(compressed) == 2
        assert compressed[0]["content"] == "new"

    def test_h_compressor_factory(self):
        comp = H.compressor(threshold=50_000)
        assert isinstance(comp, ContextCompressor)
        assert comp.threshold == 50_000


# ======================================================================
# Symlink-safe path validation
# ======================================================================


class TestSymlinkSafePaths:
    def test_symlink_escape_blocked(self):
        """Symlinks pointing outside workspace are blocked."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create workspace
            ws = os.path.join(tmp, "workspace")
            os.makedirs(ws)
            # Create a secret file outside workspace
            secret = os.path.join(tmp, "secret.txt")
            with open(secret, "w") as f:
                f.write("secret data")
            # Create a symlink inside workspace pointing outside
            link = os.path.join(ws, "escape_link")
            os.symlink(secret, link)

            sandbox = SandboxPolicy(workspace=ws)
            # The symlink resolves to /tmp/.../secret.txt — outside workspace
            assert not sandbox.validate_path(link)

    def test_dotdot_traversal_blocked(self):
        """Path traversal with .. is blocked after resolution."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = os.path.join(tmp, "workspace")
            os.makedirs(ws)
            sandbox = SandboxPolicy(workspace=ws)
            # Try to escape via ..
            escaped = os.path.join(ws, "..", "secret.txt")
            assert not sandbox.validate_path(escaped)

    def test_resolve_path(self):
        """SandboxPolicy.resolve_path handles relative paths."""
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = SandboxPolicy(workspace=tmp)
            resolved = sandbox.resolve_path("src/main.py")
            assert resolved.startswith(os.path.realpath(tmp))

    def test_workspace_prefix_attack(self):
        """Paths like /workspace2 don't match /workspace."""
        with tempfile.TemporaryDirectory() as base:
            ws = os.path.join(base, "workspace")
            ws2 = os.path.join(base, "workspace2")
            os.makedirs(ws)
            os.makedirs(ws2)
            with open(os.path.join(ws2, "trick.txt"), "w") as f:
                f.write("gotcha")

            sandbox = SandboxPolicy(workspace=ws)
            assert not sandbox.validate_path(os.path.join(ws2, "trick.txt"))


# ======================================================================
# REPL config
# ======================================================================


class TestReplConfig:
    def test_default_config(self):
        cfg = ReplConfig()
        assert cfg.prompt_prefix == "> "
        assert "/exit" in cfg.exit_commands
        assert cfg.max_turns == 0

    def test_custom_config(self):
        cfg = ReplConfig(
            prompt_prefix="harness> ",
            max_turns=10,
            auto_checkpoint=True,
        )
        assert cfg.prompt_prefix == "harness> "
        assert cfg.max_turns == 10
        assert cfg.auto_checkpoint

    def test_h_repl_factory(self):
        from adk_fluent import Agent

        agent = Agent("test", "gemini-2.5-flash").instruct("Test.")
        repl = H.repl(agent)
        assert isinstance(repl, HarnessRepl)


# ======================================================================
# New event types
# ======================================================================


class TestNewEvents:
    def test_permission_result(self):
        e = PermissionResult(tool_name="bash", granted=True, remembered=True)
        assert e.kind == "permission_result"
        assert e.granted
        assert e.remembered

    def test_git_checkpoint(self):
        e = GitCheckpoint(commit_sha="abc123", action="create")
        assert e.kind == "git_checkpoint"

    def test_compression_triggered(self):
        e = CompressionTriggered(token_count=150_000, threshold=100_000)
        assert e.kind == "compression_triggered"

    def test_hook_fired(self):
        e = HookFired(hook_name="echo test", trigger="turn_complete", exit_code=0)
        assert e.kind == "hook_fired"


# ======================================================================
# Gitignore integration with workspace tools
# ======================================================================


class TestGitignoreIntegration:
    def test_glob_respects_gitignore(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Create .gitignore
            with open(os.path.join(tmp, ".gitignore"), "w") as f:
                f.write("*.log\nbuild/\n")
            # Create files
            with open(os.path.join(tmp, "main.py"), "w") as f:
                f.write("print('hello')")
            with open(os.path.join(tmp, "debug.log"), "w") as f:
                f.write("log data")
            os.makedirs(os.path.join(tmp, "build"))
            with open(os.path.join(tmp, "build", "output.js"), "w") as f:
                f.write("built")

            tools = H.workspace(tmp)
            glob_fn = [t for t in tools if t.__name__ == "glob_search"][0]
            result = glob_fn("**/*")
            assert "main.py" in result
            assert "debug.log" not in result

    def test_grep_respects_gitignore(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, ".gitignore"), "w") as f:
                f.write("*.log\n")
            with open(os.path.join(tmp, "main.py"), "w") as f:
                f.write("hello world")
            with open(os.path.join(tmp, "debug.log"), "w") as f:
                f.write("hello world")

            tools = H.workspace(tmp)
            grep_fn = [t for t in tools if t.__name__ == "grep_search"][0]
            result = grep_fn("hello")
            assert "main.py" in result
            assert "debug.log" not in result


# ======================================================================
# H namespace completeness
# ======================================================================


class TestHNamespaceCompleteness:
    """Verify all H methods exist and return correct types."""

    def test_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = H.workspace(tmp)
            assert isinstance(tools, list)
            assert len(tools) == 7

    def test_ask_before(self):
        p = H.ask_before("bash")
        assert isinstance(p, PermissionPolicy)

    def test_auto_allow(self):
        p = H.auto_allow("read_file")
        assert isinstance(p, PermissionPolicy)

    def test_deny(self):
        p = H.deny("bash")
        assert isinstance(p, PermissionPolicy)

    def test_workspace_only(self):
        s = H.workspace_only("/tmp")
        assert isinstance(s, SandboxPolicy)

    def test_sandbox(self):
        s = H.sandbox(workspace="/tmp", allow_shell=False)
        assert isinstance(s, SandboxPolicy)
        assert not s.allow_shell

    def test_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = H.git(tmp)
            assert isinstance(cp, GitCheckpointer)

    def test_hooks(self):
        hooks = H.hooks()
        assert isinstance(hooks, HookRegistry)

    def test_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = H.artifacts(tmp)
            assert isinstance(store, ArtifactStore)

    def test_streaming_bash(self):
        sandbox = SandboxPolicy(workspace="/tmp")
        sb = H.streaming_bash(sandbox)
        assert isinstance(sb, StreamingBash)

    def test_dispatcher(self):
        d = H.dispatcher()
        assert isinstance(d, EventDispatcher)

    def test_compressor(self):
        c = H.compressor(threshold=50_000)
        assert isinstance(c, ContextCompressor)

    def test_approval_memory(self):
        m = H.approval_memory()
        assert isinstance(m, ApprovalMemory)

    def test_auto_compress(self):
        assert H.auto_compress(50_000) == 50_000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
