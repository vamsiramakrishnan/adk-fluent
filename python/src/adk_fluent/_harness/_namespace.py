"""H namespace — public API for harness building blocks.

All harness primitives are accessed through the ``H`` class::

    from adk_fluent import H

    # Workspace tools
    tools = H.workspace("/project")

    # Permission policies
    perms = H.auto_allow("read_file").merge(H.ask_before("bash"))

    # Sandbox policies
    sandbox = H.workspace_only("/project")

    # Web tools (reuses ADK UrlContextTool / GoogleSearchTool)
    web = H.web()

    # Persistent project memory (composes with C.from_state / .reads)
    mem = H.memory("/project/.agent-memory.md")

    # Token/cost tracking
    tracker = H.usage()

    # Process lifecycle
    procs = H.processes()

    # MCP bulk-loading (delegates to T.mcp / McpToolset)
    mcp_tools = H.mcp([{"url": "http://localhost:3000/mcp"}])

    # Notebook editing
    nb_tools = H.notebook()

    # Background tasks
    tasks = H.tasks()

    # Event rendering
    renderer = H.renderer()
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from adk_fluent._harness._artifacts import ArtifactStore
from adk_fluent._harness._compression import CompressionStrategy, ContextCompressor
from adk_fluent._harness._diff import PendingEditStore, make_apply_edit, make_diff_edit_file
from adk_fluent._harness._dispatcher import EventDispatcher
from adk_fluent._harness._error_strategy import ErrorStrategy
from adk_fluent._harness._git import GitCheckpointer
from adk_fluent._hooks import HookDecision, HookMatcher, HookRegistry
from adk_fluent._harness._memory import ProjectMemory
from adk_fluent._harness._multimodal import make_multimodal_read_file
from adk_fluent._permissions import (
    ApprovalMemory,
    PermissionDecision,
    PermissionHandler,
    PermissionMode,
    PermissionPlugin,
    PermissionPolicy,
)
from adk_fluent._harness._repl import HarnessRepl, ReplConfig
from adk_fluent._harness._sandbox import SandboxPolicy
from adk_fluent._harness._streaming import StreamingBash, make_streaming_bash
from adk_fluent._harness._tools import workspace_tools
from adk_fluent._harness._usage import UsageTracker

__all__ = ["H"]


class H:
    """Harness namespace — building blocks for AI coding harnesses.

    ``H`` is a purely static namespace. Every method returns a composable
    building block. Combine them to construct your harness::

        harness = (
            Agent("coder", "gemini-2.5-pro")
            .tools(H.workspace("/project") + H.web() + H.processes())
            .harness(
                permissions=H.auto_allow("read_file").merge(H.ask_before("bash")),
                sandbox=H.workspace_only("/project"),
                usage=H.usage(),
                memory=H.memory("/project/.agent-memory.md"),
                on_error=H.on_error(retry={"bash"}, skip={"glob_search"}),
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
        diff_mode: bool = False,
        multimodal: bool = False,
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
            diff_mode: Preview edits as diffs before applying. Replaces
                ``edit_file`` with a two-phase diff+apply workflow.
            multimodal: Handle images and PDFs in ``read_file``.
                Returns base64-encoded content for binary files.
        """
        sandbox = SandboxPolicy(
            workspace=str(Path(path).resolve()),
            allow_shell=allow_shell,
            allow_network=allow_network,
            max_output_bytes=max_output_bytes,
        )

        # Start with standard tools
        tools = workspace_tools(sandbox, read_only=read_only)

        # Replace read_file with multimodal version
        if multimodal:
            tools = [t for t in tools if t.__name__ != "read_file"]
            tools.insert(0, make_multimodal_read_file(sandbox))

        # Replace edit_file with diff-mode version
        if diff_mode and not read_only:
            tools = [t for t in tools if t.__name__ != "edit_file"]
            store = PendingEditStore()
            tools.append(make_diff_edit_file(sandbox, store))
            tools.append(make_apply_edit(sandbox, store))

        # Replace blocking bash with streaming if requested
        if streaming and allow_shell:
            tools = [t for t in tools if t.__name__ != "bash"]
            tools.append(make_streaming_bash(sandbox, on_output=on_output))

        return tools

    # =================================================================
    # Permission policies (adk_fluent._permissions)
    # =================================================================

    @staticmethod
    def permissions(
        *,
        mode: str = PermissionMode.DEFAULT,
        allow: list[str] | tuple[str, ...] | None = None,
        deny: list[str] | tuple[str, ...] | None = None,
        ask: list[str] | tuple[str, ...] | None = None,
        allow_patterns: tuple[str, ...] = (),
        deny_patterns: tuple[str, ...] = (),
        ask_patterns: tuple[str, ...] = (),
        pattern_mode: str = "glob",
    ) -> PermissionPolicy:
        """Build a :class:`PermissionPolicy` — the decision-based permission layer.

        The canonical factory. Accepts every field of the policy and returns a
        frozen, composable policy object.

        Install via ``.harness(permissions=policy)`` or
        ``App(...).plugin(PermissionPlugin(policy))``.

        Usage::

            perms = H.permissions(
                mode=PermissionMode.ACCEPT_EDITS,
                allow=["read_file", "list_files"],
                deny=["shell_exec"],
                ask=["bash"],
            )
        """
        return PermissionPolicy(
            mode=mode,
            allow=frozenset(allow or ()),
            deny=frozenset(deny or ()),
            ask=frozenset(ask or ()),
            allow_patterns=tuple(allow_patterns),
            deny_patterns=tuple(deny_patterns),
            ask_patterns=tuple(ask_patterns),
            pattern_mode=pattern_mode,
        )

    @staticmethod
    def ask_before(*tool_names: str) -> PermissionPolicy:
        """Shortcut: require user approval before running these tools."""
        return PermissionPolicy(ask=frozenset(tool_names))

    @staticmethod
    def auto_allow(*tool_names: str) -> PermissionPolicy:
        """Shortcut: auto-approve these tools without asking."""
        return PermissionPolicy(allow=frozenset(tool_names))

    @staticmethod
    def deny(*tool_names: str) -> PermissionPolicy:
        """Shortcut: block these tools entirely."""
        return PermissionPolicy(deny=frozenset(tool_names))

    @staticmethod
    def allow_patterns(*patterns: str, mode: str = "glob") -> PermissionPolicy:
        """Auto-allow tools matching glob/regex patterns.

        Examples::

            H.allow_patterns("read_*", "list_*")           # glob
            H.allow_patterns(".*_search$", mode="regex")   # regex
        """
        return PermissionPolicy(allow_patterns=patterns, pattern_mode=mode)

    @staticmethod
    def deny_patterns(*patterns: str, mode: str = "glob") -> PermissionPolicy:
        """Deny tools matching glob/regex patterns."""
        return PermissionPolicy(deny_patterns=patterns, pattern_mode=mode)

    @staticmethod
    def permissions_plan(
        *,
        allow: list[str] | tuple[str, ...] | None = None,
    ) -> PermissionPolicy:
        """Shortcut: return a policy in ``plan`` mode.

        In plan mode the agent may read the workspace freely but every
        mutating tool is denied. Use as a safety net while the agent drafts
        its approach before executing.
        """
        return PermissionPolicy(
            mode=PermissionMode.PLAN,
            allow=frozenset(allow or ()),
        )

    @staticmethod
    def permissions_bypass() -> PermissionPolicy:
        """Shortcut: allow every tool. Intended for trusted automation only."""
        return PermissionPolicy(mode=PermissionMode.BYPASS)

    @staticmethod
    def permissions_accept_edits(
        *,
        ask: list[str] | tuple[str, ...] | None = None,
    ) -> PermissionPolicy:
        """Shortcut: auto-allow mutating file ops, ask for everything else.

        Mirrors Claude Agent SDK's ``acceptEdits`` mode. Use for trusted
        coding assistants where you still want a prompt before shell access.
        """
        return PermissionPolicy(
            mode=PermissionMode.ACCEPT_EDITS,
            ask=frozenset(ask or ()),
        )

    @staticmethod
    def permissions_dont_ask(
        *,
        allow: list[str] | tuple[str, ...] | None = None,
    ) -> PermissionPolicy:
        """Shortcut: never prompt — allow the allowlist and deny everything else.

        For CI or batch runners where there is no human to answer a prompt.
        """
        return PermissionPolicy(
            mode=PermissionMode.DONT_ASK,
            allow=frozenset(allow or ()),
        )

    @staticmethod
    def permission_decision() -> type[PermissionDecision]:
        """Return the :class:`PermissionDecision` class for use inside handlers.

        Shorthand so handlers can write ``H.permission_decision().allow()``
        without a separate import.
        """
        return PermissionDecision

    @staticmethod
    def permission_plugin(
        policy: PermissionPolicy,
        *,
        handler: PermissionHandler | None = None,
        memory: ApprovalMemory | None = None,
    ) -> PermissionPlugin:
        """Create the ADK :class:`PermissionPlugin` for ``policy``.

        Usually not needed directly — ``.harness(permissions=...)`` builds
        and installs the plugin automatically. Exposed for users who manage
        the ADK ``App`` / ``Runner`` themselves.
        """
        return PermissionPlugin(policy, handler=handler, memory=memory)

    @staticmethod
    def approval_memory() -> ApprovalMemory:
        """Create an :class:`ApprovalMemory` for persistent permission decisions.

        The memory remembers user decisions so the same tool+args pattern
        isn't asked twice in a session::

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
    # Filesystem backends (adk_fluent._fs)
    # =================================================================

    @staticmethod
    def fs_local(root: str | None = None) -> Any:
        """Return a :class:`adk_fluent._fs.LocalBackend` rooted at ``root``."""
        from adk_fluent._fs import LocalBackend

        return LocalBackend(root=root)

    @staticmethod
    def fs_memory(files: dict[str, str | bytes] | None = None) -> Any:
        """Return a :class:`adk_fluent._fs.MemoryBackend` seeded with ``files``.

        Useful for ephemeral scratch workspaces and for tests that want to
        run workspace tools without touching the real disk.
        """
        from adk_fluent._fs import MemoryBackend

        return MemoryBackend(files=files)

    @staticmethod
    def fs_sandboxed(backend: Any, sandbox: SandboxPolicy) -> Any:
        """Wrap ``backend`` in a :class:`SandboxedBackend`.

        The wrapper enforces ``sandbox``'s workspace scope and symlink-safe
        path validation regardless of what the underlying backend does.
        """
        from adk_fluent._fs import SandboxedBackend

        return SandboxedBackend(backend, sandbox)

    # =================================================================
    # Web tools (reuses ADK UrlContextTool / GoogleSearchTool)
    # =================================================================

    @staticmethod
    def web(
        *,
        search: bool = True,
        search_provider: Callable | None = None,
        allow_network: bool = True,
        max_bytes: int = 100_000,
        timeout: int = 30,
    ) -> list:
        """Create web tools: URL fetching and web search.

        Prefers ADK's ``UrlContextTool`` and ``GoogleSearchTool`` when
        available. Falls back to a standalone ``urllib``-based fetcher.

        Args:
            search: Include web search tool.
            search_provider: Custom search tool (replaces default).
            allow_network: Override network policy.
            max_bytes: Max response size for standalone fetcher.
            timeout: Request timeout for standalone fetcher.
        """
        from adk_fluent._harness._web import web_tools

        sandbox = SandboxPolicy(allow_network=allow_network)
        return web_tools(
            sandbox,
            search=search,
            search_provider=search_provider,
            max_bytes=max_bytes,
            timeout=timeout,
        )

    # =================================================================
    # Persistent project memory (composes with C.from_state / .reads)
    # =================================================================

    @staticmethod
    def memory(
        path: str | Path,
        *,
        state_key: str = "project_memory",
        max_entries: int = 100,
    ) -> ProjectMemory:
        """Create a persistent project memory file.

        Loads from and saves to a markdown file that survives across
        sessions. Integrates with existing context primitives::

            mem = H.memory("/project/.agent-memory.md")

            agent = (
                Agent("coder")
                .before_agent(mem.load_callback())    # file → state
                .reads("project_memory")               # state → prompt
                .after_agent(mem.save_callback())      # state → file
            )

        Or with C namespace::

            .context(C.from_state("project_memory"))

        Args:
            path: Path to the memory file.
            state_key: State key for context injection.
            max_entries: Max entries when using .append().
        """
        return ProjectMemory(path, state_key=state_key, max_entries=max_entries)

    @staticmethod
    def memory_hierarchy(
        *paths: str | Path,
        state_key: str = "project_memory",
    ) -> Any:
        """Create a multi-file memory hierarchy.

        Loads and merges memory files in priority order (first = lowest
        priority, last = highest). Follows the CLAUDE.md convention::

            hierarchy = H.memory_hierarchy(
                "~/.config/agent/memory.md",   # global
                "/project/AGENT.md",           # repo
                "/project/src/AGENT.md",       # directory
            )

            agent = (
                Agent("coder")
                .before_agent(hierarchy.load_callback())
                .reads("project_memory")
            )

        Args:
            paths: Memory file paths in priority order.
            state_key: State key for merged content.
        """
        from adk_fluent._harness._memory import MemoryHierarchy

        return MemoryHierarchy(*paths, state_key=state_key)

    # =================================================================
    # Token/cost tracking
    # =================================================================

    @staticmethod
    def usage(
        *,
        cost_per_million_input: float = 0.0,
        cost_per_million_output: float = 0.0,
    ) -> UsageTracker:
        """Create a token usage tracker.

        Attach as an after_model callback to track token consumption::

            tracker = H.usage()
            agent = Agent("coder").after_model(tracker.callback())

            # After execution
            print(tracker.summary())
            print(tracker.total_tokens)

        Args:
            cost_per_million_input: Cost per 1M input tokens (USD).
            cost_per_million_output: Cost per 1M output tokens (USD).
        """
        return UsageTracker(
            cost_per_million_input=cost_per_million_input,
            cost_per_million_output=cost_per_million_output,
        )

    # =================================================================
    # Process lifecycle management
    # =================================================================

    @staticmethod
    def processes(
        path: str | Path | None = None,
        *,
        allow_shell: bool = True,
    ) -> list[Callable]:
        """Create background process management tools.

        Returns [start_process, check_process, stop_process] for
        managing long-running commands (dev servers, builds, etc.)::

            agent = Agent("coder").tools(
                H.workspace("/project") + H.processes("/project")
            )

        Args:
            path: Workspace directory for process cwd.
            allow_shell: Allow shell execution.
        """
        from adk_fluent._harness._processes import process_tools

        sandbox = SandboxPolicy(
            workspace=str(Path(path).resolve()) if path else None,
            allow_shell=allow_shell,
        )
        return process_tools(sandbox)

    # =================================================================
    # MCP bulk-loading (delegates to T.mcp / McpToolset builder)
    # =================================================================

    @staticmethod
    def mcp(
        servers: list[dict[str, Any]],
        *,
        tool_filter: Callable[[str], bool] | list[str] | None = None,
        prefix: str | None = None,
    ) -> list:
        """Load tools from multiple MCP servers at once.

        Delegates to the existing ``McpToolset`` builder for each server.
        Each spec is a dict with ``url`` or ``command``::

            tools = H.mcp([
                {"url": "http://localhost:3000/mcp"},
                {"command": "npx", "args": ["-y", "some-server"]},
            ])

        Args:
            servers: List of server spec dicts.
            tool_filter: Filter tools by name.
            prefix: Prefix for tool names.
        """
        from adk_fluent._harness._mcp import load_mcp_tools

        return load_mcp_tools(servers, tool_filter=tool_filter, prefix=prefix)

    @staticmethod
    def mcp_from_config(
        config_path: str | Path,
        *,
        tool_filter: Callable[[str], bool] | list[str] | None = None,
        prefix: str | None = None,
    ) -> list:
        """Load MCP tools from a JSON config file.

        Supports Claude Code format (``mcpServers`` dict) and
        array format::

            tools = H.mcp_from_config("/project/.agent/mcp.json")

        Args:
            config_path: Path to the config file.
            tool_filter: Filter tools by name.
            prefix: Prefix for tool names.
        """
        from adk_fluent._harness._mcp import load_mcp_config

        return load_mcp_config(config_path, tool_filter=tool_filter, prefix=prefix)

    # =================================================================
    # Notebook tools
    # =================================================================

    @staticmethod
    def notebook(path: str | Path | None = None) -> list[Callable]:
        """Create notebook (.ipynb) editing tools.

        Returns [read_notebook, edit_notebook_cell] for reading and
        editing Jupyter notebooks without a Jupyter dependency::

            agent = Agent("ds").tools(
                H.workspace("/project") + H.notebook("/project")
            )

        Args:
            path: Workspace directory for path resolution.
        """
        from adk_fluent._harness._notebook import notebook_tools

        sandbox = SandboxPolicy(
            workspace=str(Path(path).resolve()) if path else None,
        )
        return notebook_tools(sandbox)

    # =================================================================
    # Background tasks
    # =================================================================

    @staticmethod
    def tasks(*, max_tasks: int = 10) -> list[Callable]:
        """Create background task management tools.

        Returns [launch_task, check_task, list_tasks] for tracking
        named background tasks::

            agent = Agent("coder").tools(H.tasks())

        Args:
            max_tasks: Maximum concurrent tasks.
        """
        from adk_fluent._harness._tasks import TaskRegistry, task_tools

        registry = TaskRegistry(max_tasks=max_tasks)
        return task_tools(registry)

    # =================================================================
    # Error strategy
    # =================================================================

    @staticmethod
    def on_error(
        *,
        retry: set[str] | frozenset[str] | None = None,
        skip: set[str] | frozenset[str] | None = None,
        ask: set[str] | frozenset[str] | None = None,
        fallback_message: str = "Tool call failed and was skipped.",
    ) -> ErrorStrategy:
        """Create a harness-level error recovery policy.

        Maps tool names to actions on failure::

            strategy = H.on_error(
                retry={"bash", "web_fetch"},
                skip={"glob_search"},
                ask={"edit_file"},
            )

        Args:
            retry: Tools to retry once on failure.
            skip: Tools to skip silently on failure.
            ask: Tools to escalate to error handler.
            fallback_message: Message for skipped failures.
        """
        return ErrorStrategy(
            retry=frozenset(retry or set()),
            skip=frozenset(skip or set()),
            ask=frozenset(ask or set()),
            fallback_message=fallback_message,
        )

    # =================================================================
    # Interrupt & resume
    # =================================================================

    @staticmethod
    def cancellation_token() -> Any:
        """Create a cooperative cancellation token.

        The token is checked before each tool call. When cancelled,
        the agent is told to stop gracefully::

            token = H.cancellation_token()
            agent = Agent("coder").before_tool(
                make_cancellation_callback(token)
            )

            # In UI/REPL thread
            token.cancel()  # interrupt
            snapshot = token.snapshot  # mid-turn state
            token.reset()  # ready for next turn
        """
        from adk_fluent._harness._interrupt import CancellationToken

        return CancellationToken()

    # =================================================================
    # Conversation forking
    # =================================================================

    @staticmethod
    def forks(*, max_branches: int = 20) -> Any:
        """Create a conversation fork manager.

        Manages named branches of session state for parallel
        exploration. Fork, switch, compare, and merge::

            forks = H.forks()

            # Save current state
            forks.fork("approach_a", state)

            # Compare branches
            diff = forks.diff("approach_a", "approach_b")

            # Merge
            merged = forks.merge("approach_a", "approach_b")

        Args:
            max_branches: Maximum branches (oldest auto-evicted).
        """
        from adk_fluent._harness._fork import ForkManager

        return ForkManager(max_branches=max_branches)

    # =================================================================
    # Event rendering
    # =================================================================

    @staticmethod
    def renderer(
        format: str = "plain",
        *,
        show_timing: bool = True,
        show_args: bool = False,
        verbose: bool = False,
    ) -> Any:
        """Create an event renderer for display formatting.

        Renderers convert HarnessEvents into display strings. They
        do NOT handle I/O — the caller writes to their output.

        Args:
            format: ``"plain"``, ``"rich"``, or ``"json"``.
            show_timing: Include duration in tool events.
            show_args: Include tool arguments.
            verbose: Show all event types.
        """
        from adk_fluent._harness._renderer import JsonRenderer, PlainRenderer, RichRenderer

        if format == "rich":
            return RichRenderer(show_timing=show_timing, show_args=show_args)
        elif format == "json":
            return JsonRenderer()
        else:
            return PlainRenderer(show_timing=show_timing, show_args=show_args, verbose=verbose)

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
        """Create a hook registry — the unified hook foundation.

        Hooks are session-scoped and subagent-inherited by construction. The
        registry accepts both callable hooks (full decision power) and shell
        hooks (notification-only). Install the registry via
        ``agent.harness(hooks=registry)`` or ``App(...).plugin(registry.as_plugin())``.

        Usage::

            from adk_fluent import H
            from adk_fluent._hooks import HookDecision, HookMatcher, HookEvent

            def block_rm_rf(ctx):
                if "rm -rf" in (ctx.tool_input or {}).get("command", ""):
                    return HookDecision.deny("rm -rf is forbidden")
                return HookDecision.allow()

            def lint_on_edit(ctx):
                return HookDecision.inject(
                    f"You just edited {ctx.tool_input['file_path']}"
                )

            hooks = (
                H.hooks("/project")
                .on(HookEvent.PRE_TOOL_USE, block_rm_rf,
                    match=HookMatcher.for_tool(HookEvent.PRE_TOOL_USE, "bash"))
                .on(HookEvent.POST_TOOL_USE, lint_on_edit,
                    match=HookMatcher.for_tool(
                        HookEvent.POST_TOOL_USE, "edit_file", file_path="*.py"))
                .shell(HookEvent.POST_TOOL_USE, "ruff check {tool_input[file_path]}",
                       match=HookMatcher.for_tool(
                           HookEvent.POST_TOOL_USE, "edit_file"))
            )

        See :doc:`/user-guide/hooks` for the full decision protocol, event
        taxonomy, and cookbook recipes.
        """
        return HookRegistry(workspace=str(workspace) if workspace else None)

    @staticmethod
    def hook_decision() -> type[HookDecision]:
        """Return the :class:`HookDecision` class for use inside hook callables.

        Shorthand so user hooks can write ``H.hook_decision().deny("...")``
        without a separate import.
        """
        return HookDecision

    @staticmethod
    def hook_match(
        event: str,
        tool_name: str | None = None,
        **args: Any,
    ) -> HookMatcher:
        """Build a :class:`HookMatcher` for filtering hook dispatches.

        ``H.hook_match("pre_tool_use", "edit_file", file_path="*.py")`` is
        equivalent to ``HookMatcher.for_tool("pre_tool_use", "edit_file", file_path="*.py")``.
        """
        if tool_name is None:
            return HookMatcher.any(event)
        return HookMatcher.for_tool(event, tool_name, **args)

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
        compressor: ContextCompressor | None = None,
        config: ReplConfig | None = None,
    ) -> HarnessRepl:
        """Create an interactive REPL for a harness agent.

        Hooks are installed at the harness / App layer before building the
        agent — the REPL just drives the input/output loop.

        Usage::

            agent = agent.harness(hooks=H.hooks("/project").on(...))
            repl = H.repl(agent.build(), compressor=H.compressor(50_000))
            await repl.run()
        """
        return HarnessRepl(
            agent,
            dispatcher=dispatcher,
            compressor=compressor,
            config=config,
        )

    # =================================================================
    # Git workspace tools
    # =================================================================

    @staticmethod
    def git_tools(
        path: str | Path | None = None,
        *,
        allow_shell: bool = True,
    ) -> list[Callable]:
        """Create git operation tools for the LLM.

        Returns [git_status, git_diff, git_log, git_commit, git_branch].
        The LLM can commit, branch, and inspect history directly::

            agent = Agent("coder").tools(
                H.workspace("/project") + H.git_tools("/project")
            )

        Args:
            path: Git repository path.
            allow_shell: Allow write operations (commit, branch).
        """
        from adk_fluent._harness._git_tools import git_tools

        return git_tools(path, allow_shell=allow_shell)

    # =================================================================
    # Session tape (recording/replay)
    # =================================================================

    @staticmethod
    def tape(*, max_events: int = 0) -> Any:
        """Create a session tape for event recording and replay.

        Compose with ``EventDispatcher`` as a subscriber::

            tape = H.tape()
            dispatcher = H.dispatcher()
            dispatcher.subscribe(tape.record)

            # After session
            tape.save("session.jsonl")

        Args:
            max_events: Maximum events to buffer (0 = unlimited).
        """
        from adk_fluent._harness._tape import SessionTape

        return SessionTape(max_events=max_events)

    # =================================================================
    # Slash commands
    # =================================================================

    @staticmethod
    def commands(*, prefix: str = "/") -> Any:
        """Create a slash command registry for the REPL.

        Register ``/command`` handlers that the user can invoke::

            cmds = H.commands()
            cmds.register("clear", lambda args: "Cleared.", description="Clear context")
            cmds.register("model", lambda args: set_model(args), description="Switch model")

        Wire into the REPL loop or check with ``cmds.is_command(text)``.

        Args:
            prefix: Command prefix (default: "/").
        """
        from adk_fluent._harness._commands import CommandRegistry

        return CommandRegistry(prefix=prefix)

    # =================================================================
    # Manifold — unified runtime capability discovery
    # =================================================================

    @staticmethod
    def manifold(
        *,
        tools: Any | None = None,
        skills: str | Path | Any | None = None,
        mcp: list[dict[str, Any]] | None = None,
        mcp_config: str | Path | None = None,
        always_loaded: list[str] | None = None,
        max_tools: int = 30,
    ) -> Any:
        """Create a unified runtime capability discovery surface.

        The manifold extends the two-phase ``SearchToolset`` pattern to
        tools, skills, AND MCP servers. The LLM discovers and loads
        capabilities at runtime through a single search interface.

        Phase 1 (Discovery): ``search_capabilities`` → ``load_capability``
        Phase 2 (Execution): ``finalize_capabilities`` → frozen tool set

        Composes with existing building blocks:
            - ``ToolRegistry`` for tool search
            - ``SkillRegistry`` for skill scanning
            - ``McpToolset`` for MCP server wiring

        Usage::

            manifold = H.manifold(
                tools=ToolRegistry.from_tools(fn1, fn2, fn3),
                skills="skills/",
                mcp_config="/project/.agent/mcp.json",
            )

            agent = Agent("coder").tools(manifold)

        After finalization, loaded skills are compiled to
        ``static_instruction`` accessible via ``manifold.compiled_skills``.

        Args:
            tools: A ``ToolRegistry`` instance (for tool discovery).
            skills: Path to skills directory (str/Path) or ``SkillRegistry``.
            mcp: List of MCP server spec dicts.
            mcp_config: Path to MCP JSON config file.
            always_loaded: Capabilities to always include.
            max_tools: Maximum active tools after finalization.
        """
        from adk_fluent._harness._manifold import (
            CapabilityRegistry,
            ManifoldToolset,
        )

        cap_registry = CapabilityRegistry()
        tool_registry = None

        # Import tools
        if tools is not None:
            tool_registry = tools
            cap_registry.add_from_tool_registry(tools)

        # Import skills
        if skills is not None:
            if isinstance(skills, (str, Path)):
                try:
                    from adk_fluent._skill_registry import SkillRegistry

                    skill_reg = SkillRegistry(skills)
                    cap_registry.add_from_skill_registry(skill_reg)
                except Exception:
                    pass  # Directory may not exist or have no SKILL.md files
            else:
                # Assume it's a SkillRegistry instance
                cap_registry.add_from_skill_registry(skills)

        # Import MCP servers
        if mcp is not None:
            cap_registry.add_mcp_servers(mcp)
        if mcp_config is not None:
            cap_registry.add_mcp_config(mcp_config)

        return ManifoldToolset(
            cap_registry,
            tool_registry,
            always_loaded=always_loaded,
            max_tools=max_tools,
        )

    # =================================================================
    # EventBus — session-scoped typed event backbone
    # =================================================================

    @staticmethod
    def event_bus(*, max_buffer: int = 0) -> Any:
        """Create a session-scoped typed event bus.

        The EventBus is the observer backbone. All harness modules
        (dispatcher, tape, renderer, hooks) subscribe to it instead
        of building their own observation layers::

            bus = H.event_bus()
            bus.on("tool_call_start", lambda e: print(e.tool_name))

            tape = bus.tape()           # pre-subscribed SessionTape
            agent = Agent("coder")
                .before_tool(bus.before_tool_hook())
                .after_tool(bus.after_tool_hook())

        Args:
            max_buffer: Events to retain in history (0 = none).
        """
        from adk_fluent._harness._event_bus import EventBus

        return EventBus(max_buffer=max_buffer)

    # =================================================================
    # ToolPolicy — per-tool error recovery
    # =================================================================

    @staticmethod
    def tool_policy(*, default: str = "propagate") -> Any:
        """Create a per-tool error recovery policy.

        Unlike ``H.on_error()`` (which maps tool sets to actions),
        ToolPolicy is a fluent builder with per-tool granularity,
        backoff support, and EventBus integration::

            policy = (
                H.tool_policy()
                .retry("bash", max_attempts=3, backoff=1.0)
                .skip("glob_search", fallback="No results.")
                .ask("edit_file", handler=user_confirm)
            )

            agent = Agent("coder").after_tool(policy.after_tool_hook())

        Args:
            default: Default action for tools without rules.
        """
        from adk_fluent._harness._tool_policy import ToolPolicy

        return ToolPolicy(default=default)

    # =================================================================
    # BudgetMonitor — token lifecycle with threshold triggers
    # =================================================================

    @staticmethod
    def budget_monitor(
        max_tokens: int = 200_000,
    ) -> Any:
        """Create a token budget lifecycle monitor.

        Tracks cumulative token usage and fires callbacks when
        configurable thresholds are crossed. Does NOT compress —
        delegates to whatever handler you wire up::

            monitor = (
                H.budget_monitor(200_000)
                .on_threshold(0.8, lambda m: print(f"⚠ {m.utilization:.0%}"))
                .on_threshold(0.95, compress_handler)
            )

            agent = Agent("coder").after_model(monitor.after_model_hook())

        Args:
            max_tokens: Total token budget for the session.
        """
        from adk_fluent._harness._budget_monitor import BudgetMonitor

        return BudgetMonitor(max_tokens=max_tokens)

    # =================================================================
    # TaskLedger — dispatch/join bridge
    # =================================================================

    @staticmethod
    def task_ledger(*, max_tasks: int = 10) -> Any:
        """Create a task lifecycle tracker with LLM-callable tools.

        Bridges ``dispatch()``/``join()`` expression primitives to
        tool-level task management. The LLM can launch, check,
        list, and cancel tasks::

            ledger = H.task_ledger()
            agent = Agent("coder").tools(ledger.tools())

        Wire to an EventBus for lifecycle events::

            bus = H.event_bus()
            ledger = H.task_ledger().with_bus(bus)

        Args:
            max_tasks: Maximum concurrent active tasks.
        """
        from adk_fluent._harness._task_ledger import TaskLedger

        return TaskLedger(max_tasks=max_tasks)

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
        usage: UsageTracker | None = None,
        memory: ProjectMemory | None = None,
        on_error: ErrorStrategy | None = None,
    ) -> Any:
        """Create a unified harness configuration.

        Usage::

            cfg = H.config(
                permissions=H.ask_before("bash").merge(H.auto_allow("read_file")),
                sandbox=H.workspace_only("/project"),
                approval_memory=H.approval_memory(),
                usage=H.usage(),
                memory=H.memory("/project/.agent-memory.md"),
                on_error=H.on_error(retry={"bash"}),
            )
        """
        from adk_fluent._harness._config import HarnessConfig

        return HarnessConfig(
            permissions=permissions or PermissionPolicy(),
            sandbox=sandbox or SandboxPolicy(),
            auto_compress_threshold=auto_compress_threshold,
            approval_handler=approval_handler,
            approval_memory=approval_memory,
            usage=usage,
            memory=memory,
            on_error=on_error,
        )

    # =================================================================
    # Polyglot code execution
    # =================================================================

    @staticmethod
    def code_executor(
        workspace: str | Path,
        *,
        interpreters: dict[str, list[str]] | None = None,
        default_timeout_ms: int = 60_000,
        disable: frozenset[str] | None = None,
        max_output_bytes: int = 200_000,
    ) -> Any:
        """Create a polyglot :class:`CodeExecutor` rooted at ``workspace``.

        The returned executor exposes ``.tools()`` (LLM-callable
        ``run_code`` + ``which_languages``) and ``.run(language, source)``
        for direct programmatic invocation. Supports python / node /
        typescript / bash out of the box.
        """
        from adk_fluent._harness._code_executor import CodeExecutor

        sandbox = SandboxPolicy(
            workspace=str(Path(workspace).resolve()),
            allow_shell=True,
            max_output_bytes=max_output_bytes,
        )
        return CodeExecutor(
            sandbox=sandbox,
            interpreters=interpreters or {},
            default_timeout_ms=default_timeout_ms,
            disable=disable or frozenset(),
        )

    @staticmethod
    def run_code_tools(
        workspace: str | Path,
        *,
        interpreters: dict[str, list[str]] | None = None,
    ) -> list[Callable]:
        """Shorthand for ``H.code_executor(...).tools()``."""
        return H.code_executor(workspace, interpreters=interpreters).tools()

    # =================================================================
    # Agent self-management tools (TodoWrite, PlanMode, AskUser, Worktree)
    # =================================================================

    @staticmethod
    def todos() -> Any:
        """Create an in-memory :class:`TodoStore` (claude-code style)."""
        from adk_fluent._harness._agent_tools import TodoStore

        return TodoStore()

    @staticmethod
    def plan_mode() -> Any:
        """Create a :class:`PlanMode` latch for plan-then-execute flows."""
        from adk_fluent._harness._agent_tools import PlanMode

        return PlanMode()

    @staticmethod
    def ask_user(handler: Callable[[str, list[str] | None], str] | None = None) -> Callable:
        """Build an ``ask_user_question`` LLM tool wrapping ``handler``."""
        from adk_fluent._harness._agent_tools import make_ask_user_tool

        return make_ask_user_tool(handler)

    @staticmethod
    def worktrees(workspace: str | Path) -> Any:
        """Create a git :class:`WorktreeManager` rooted at ``workspace``."""
        from adk_fluent._harness._agent_tools import WorktreeManager

        return WorktreeManager(workspace)

    # =================================================================
    # Coding-agent preset — build-your-own-Claude-Code in one call
    # =================================================================

    @staticmethod
    def coding_agent(
        workspace: str | Path,
        *,
        allow_mutations: bool = True,
        allow_network: bool = True,
        on_ask_user: Callable[[str, list[str] | None], str] | None = None,
        memory_path: str | Path | None = None,
        max_output_bytes: int = 200_000,
        interpreters: dict[str, list[str]] | None = None,
        enable_git: bool = True,
    ) -> Any:
        """Build a fully-wired coding-agent harness in one call.

        Returns a :class:`CodingAgentBundle` with ``tools`` ready to plug
        into ``Agent.tools(...)`` plus every primitive (sandbox,
        permissions, executor, todos, plan_mode, …) exposed for
        inspection / overrides. See
        :func:`adk_fluent._harness._coding_agent.coding_agent` for the
        full parameter docs.
        """
        from adk_fluent._harness._coding_agent import coding_agent as _coding_agent

        return _coding_agent(
            workspace=workspace,
            allow_mutations=allow_mutations,
            allow_network=allow_network,
            on_ask_user=on_ask_user,
            memory_path=memory_path,
            max_output_bytes=max_output_bytes,
            interpreters=interpreters,
            enable_git=enable_git,
        )
