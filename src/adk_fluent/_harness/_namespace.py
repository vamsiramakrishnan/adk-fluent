"""H namespace — public API for harness building blocks.

All harness primitives are accessed through the ``H`` class::

    from adk_fluent import H

    # Workspace tools
    tools = H.workspace("/project")

    # Permission policies
    perms = H.auto_allow("read_file").merge(H.ask_before("bash"))

    # Sandbox policies
    sandbox = H.workspace_only("/project")

    # Git checkpoints
    checkpoint = H.git("/project")

    # Hooks
    hooks = H.hooks("/project").on("tool_call_start", "echo {tool_name}")

    # Artifacts
    store = H.artifacts("/project/.harness/artifacts")

    # Streaming bash
    bash = H.streaming_bash(sandbox)

    # Event dispatcher
    dispatcher = H.dispatcher()

    # Context compressor
    compressor = H.compressor(threshold=100_000)

    # REPL
    repl = H.repl(agent, hooks=hooks, compressor=compressor)
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from adk_fluent._harness._artifacts import ArtifactStore
from adk_fluent._harness._compression import CompressionStrategy, ContextCompressor
from adk_fluent._harness._dispatcher import EventDispatcher
from adk_fluent._harness._git import GitCheckpointer
from adk_fluent._harness._hooks import HookRegistry
from adk_fluent._harness._permissions import ApprovalMemory, PermissionPolicy
from adk_fluent._harness._repl import HarnessRepl, ReplConfig
from adk_fluent._harness._sandbox import SandboxPolicy
from adk_fluent._harness._streaming import StreamingBash, make_streaming_bash
from adk_fluent._harness._tools import workspace_tools

__all__ = ["H"]


class H:
    """Harness namespace — building blocks for AI coding harnesses.

    ``H`` is a purely static namespace. Every method returns a composable
    building block. Combine them to construct your harness::

        harness = (
            Agent("coder", "gemini-2.5-pro")
            .use_skill("skills/python/")
            .tools(H.workspace("/project"))
            .harness(
                permissions=H.auto_allow("read_file").merge(H.ask_before("bash")),
                sandbox=H.workspace_only("/project"),
            )
        )
    """

    # =================================================================
    # Workspace tools
    # =================================================================

    @staticmethod
    def workspace(
        path: str | Path,
        *,
        allow_shell: bool = True,
        allow_network: bool = True,
        read_only: bool = False,
        max_output_bytes: int = 100_000,
        streaming: bool = False,
        on_output: Callable[[str], None] | None = None,
    ) -> list[Callable]:
        """Create a sandboxed workspace tool kit.

        Returns tool functions scoped to the given directory.
        By default: read, glob, grep, ls, edit, write, bash (7 tools).

        Args:
            path: Root directory for the workspace.
            allow_shell: Enable bash tool.
            allow_network: Allow network from shell.
            read_only: Disable edit/write tools.
            max_output_bytes: Max bash output size.
            streaming: Use streaming bash (PTY-based, yields output).
            on_output: Callback for streaming bash output chunks.
        """
        sandbox = SandboxPolicy(
            workspace=str(Path(path).resolve()),
            allow_shell=allow_shell,
            allow_network=allow_network,
            max_output_bytes=max_output_bytes,
        )
        tools = workspace_tools(sandbox, read_only=read_only)

        # Replace blocking bash with streaming if requested
        if streaming and allow_shell:
            tools = [t for t in tools if t.__name__ != "bash"]
            tools.append(make_streaming_bash(sandbox, on_output=on_output))

        return tools

    # =================================================================
    # Permission policies
    # =================================================================

    @staticmethod
    def ask_before(*tool_names: str) -> PermissionPolicy:
        """Require user approval before running these tools."""
        return PermissionPolicy(ask=frozenset(tool_names))

    @staticmethod
    def auto_allow(*tool_names: str) -> PermissionPolicy:
        """Auto-approve these tools without asking."""
        return PermissionPolicy(allow=frozenset(tool_names))

    @staticmethod
    def deny(*tool_names: str) -> PermissionPolicy:
        """Block these tools entirely."""
        return PermissionPolicy(deny=frozenset(tool_names))

    @staticmethod
    def approval_memory() -> ApprovalMemory:
        """Create an approval memory for persistent permission decisions.

        The memory remembers user decisions so the same tool+args
        pattern isn't asked twice in a session::

            memory = H.approval_memory()
            agent.harness(permissions=..., approval_memory=memory)
        """
        return ApprovalMemory()

    # =================================================================
    # Sandbox policies
    # =================================================================

    @staticmethod
    def workspace_only(path: str | Path | None = None) -> SandboxPolicy:
        """Restrict all file operations to the workspace directory."""
        return SandboxPolicy(
            workspace=str(Path(path).resolve()) if path else None,
        )

    @staticmethod
    def sandbox(
        *,
        workspace: str | Path | None = None,
        allow_shell: bool = True,
        allow_network: bool = True,
        read_paths: list[str] | None = None,
        write_paths: list[str] | None = None,
    ) -> SandboxPolicy:
        """Create a custom sandbox policy."""
        return SandboxPolicy(
            workspace=str(Path(workspace).resolve()) if workspace else None,
            allow_shell=allow_shell,
            allow_network=allow_network,
            read_paths=frozenset(read_paths or []),
            write_paths=frozenset(write_paths or []),
        )

    # =================================================================
    # Git checkpoints
    # =================================================================

    @staticmethod
    def git(workspace: str | Path) -> GitCheckpointer:
        """Create a git checkpointer for undo support.

        Usage::

            cp = H.git("/project")
            sha = cp.create("before refactor")
            # ... agent makes changes ...
            cp.restore(sha)  # undo
        """
        return GitCheckpointer(workspace)

    # =================================================================
    # Hooks
    # =================================================================

    @staticmethod
    def hooks(workspace: str | Path | None = None) -> HookRegistry:
        """Create a hook registry for user-defined event scripts.

        Usage::

            hooks = (
                H.hooks("/project")
                .on("tool_call_start", "echo {tool_name} >> audit.log")
                .on("turn_complete", "./scripts/post-turn.sh")
            )
        """
        return HookRegistry(workspace=str(workspace) if workspace else None)

    # =================================================================
    # Artifacts
    # =================================================================

    @staticmethod
    def artifacts(
        path: str | Path,
        *,
        max_inline_bytes: int = 10_000,
    ) -> ArtifactStore:
        """Create an artifact store for large outputs and blobs.

        Usage::

            store = H.artifacts("/project/.harness/artifacts")
            store.save("output.txt", large_text)
            store.save_binary("screenshot.png", png_bytes)
        """
        return ArtifactStore(path, max_inline_bytes=max_inline_bytes)

    # =================================================================
    # Streaming
    # =================================================================

    @staticmethod
    def streaming_bash(sandbox: SandboxPolicy) -> StreamingBash:
        """Create a streaming bash executor.

        Returns a StreamingBash instance for direct async streaming::

            streamer = H.streaming_bash(sandbox)
            async for chunk in streamer.run("npm test"):
                print(chunk, end="")
        """
        return StreamingBash(sandbox)

    # =================================================================
    # Event dispatcher
    # =================================================================

    @staticmethod
    def dispatcher() -> EventDispatcher:
        """Create an event dispatcher for ADK→HarnessEvent translation.

        Usage::

            dispatcher = H.dispatcher()
            dispatcher.on("text", lambda e: print(e.text, end=""))
            dispatcher.on("tool_call_start", lambda e: show_spinner())
        """
        return EventDispatcher()

    # =================================================================
    # Context compression
    # =================================================================

    @staticmethod
    def compressor(
        threshold: int = 100_000,
        strategy: CompressionStrategy | None = None,
        on_compress: Callable[[int], None] | None = None,
    ) -> ContextCompressor:
        """Create a context compressor for auto-compression.

        Usage::

            compressor = H.compressor(threshold=50_000)
            if compressor.should_compress(current_tokens):
                messages = compressor.compress_messages(messages)
        """
        return ContextCompressor(
            threshold=threshold,
            strategy=strategy,
            on_compress=on_compress,
        )

    @staticmethod
    def auto_compress(threshold: int = 100_000) -> int:
        """Set token threshold for automatic context compression.

        Simple integer form for ``.harness(auto_compress=...)``.
        """
        return threshold

    # =================================================================
    # REPL
    # =================================================================

    @staticmethod
    def repl(
        agent: Any,
        *,
        dispatcher: EventDispatcher | None = None,
        hooks: HookRegistry | None = None,
        compressor: ContextCompressor | None = None,
        config: ReplConfig | None = None,
    ) -> HarnessRepl:
        """Create an interactive REPL for a harness agent.

        Usage::

            repl = H.repl(
                agent,
                hooks=H.hooks("/project"),
                compressor=H.compressor(50_000),
            )
            await repl.run()
        """
        return HarnessRepl(
            agent,
            dispatcher=dispatcher,
            hooks=hooks,
            compressor=compressor,
            config=config,
        )

    # =================================================================
    # Unified config builder
    # =================================================================

    @staticmethod
    def config(
        *,
        permissions: PermissionPolicy | None = None,
        sandbox: SandboxPolicy | None = None,
        auto_compress_threshold: int = 100_000,
        approval_handler: Callable[[str, dict], bool] | None = None,
        approval_memory: ApprovalMemory | None = None,
    ) -> Any:
        """Create a unified harness configuration.

        Usage::

            cfg = H.config(
                permissions=H.ask_before("bash").merge(H.auto_allow("read_file")),
                sandbox=H.workspace_only("/project"),
                approval_memory=H.approval_memory(),
            )
        """
        from adk_fluent._harness._config import HarnessConfig

        return HarnessConfig(
            permissions=permissions or PermissionPolicy(),
            sandbox=sandbox or SandboxPolicy(),
            auto_compress_threshold=auto_compress_threshold,
            approval_handler=approval_handler,
            approval_memory=approval_memory,
        )
