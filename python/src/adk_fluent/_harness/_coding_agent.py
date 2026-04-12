"""``coding_agent`` preset — build-your-own-Claude-Code in 5 lines.

Mirrors the TypeScript ``codingAgent`` factory in
``ts/src/namespaces/harness/coding-agent.ts``. Bundles every primitive a
coding agent typically wants behind a single call:

* Workspace tools (read_file, write_file, edit_file, glob, grep, ls, bash)
* Web fetch + search
* Process lifecycle (start_process, check_process, …)
* Polyglot code executor (``run_code`` over python/node/ts/bash)
* Todo list + plan mode + ask-user (the agent self-management trio)
* Git checkpointer + worktree manager
* Project memory (``CLAUDE.md``-style) + usage tracker + event bus
* Sandbox + permissions wired to "ask before mutating"

The intent is *zero ceremony*: the harness author writes
``H.coding_agent("/repo")`` and gets back a ready-to-use bundle. Each
piece is still individually accessible on the returned object so the
author can swap or augment it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from adk_fluent._harness._agent_tools import (
    AskUserHandler,
    PlanMode,
    TodoStore,
    WorktreeManager,
    make_ask_user_tool,
)
from adk_fluent._harness._artifacts import ArtifactStore
from adk_fluent._harness._code_executor import CodeExecutor
from adk_fluent._harness._git import GitCheckpointer
from adk_fluent._harness._memory import ProjectMemory
from adk_fluent._harness._sandbox import SandboxPolicy
from adk_fluent._permissions import ApprovalMemory, PermissionPolicy
from adk_fluent._harness._tools import workspace_tools
from adk_fluent._harness._usage import UsageTracker

__all__ = ["CodingAgentBundle", "coding_agent"]


@dataclass
class CodingAgentBundle:
    """Everything a coding agent needs, returned by :func:`coding_agent`."""

    workspace: str
    tools: list[Callable]
    sandbox: SandboxPolicy
    permissions: PermissionPolicy
    approval_memory: ApprovalMemory
    usage: UsageTracker
    memory: ProjectMemory
    artifacts: ArtifactStore
    todos: TodoStore
    plan_mode: PlanMode
    worktrees: WorktreeManager | None
    git: GitCheckpointer | None
    executor: CodeExecutor


def coding_agent(
    workspace: str | Path,
    *,
    allow_mutations: bool = True,
    allow_network: bool = True,
    on_ask_user: AskUserHandler | None = None,
    memory_path: str | Path | None = None,
    max_output_bytes: int = 200_000,
    interpreters: dict[str, list[str]] | None = None,
    enable_git: bool = True,
) -> CodingAgentBundle:
    """Build a fully-wired coding agent harness in one call.

    Parameters
    ----------
    workspace
        Root directory for the agent. All file ops are sandboxed under it.
    allow_mutations
        If False, drops every write/edit/exec tool — research-only mode.
    allow_network
        If False, drops the web tools.
    on_ask_user
        Optional ``(question, options) -> answer`` handler for the
        ``ask_user_question`` tool. Defaults to a stub that raises.
    memory_path
        Path to a ``CLAUDE.md``-style memory file. Defaults to
        ``<workspace>/CLAUDE.md``.
    max_output_bytes
        Hard cap on captured stdout/stderr for bash, processes, and the
        polyglot code executor.
    interpreters
        Optional override map for the polyglot code executor (see
        :class:`CodeExecutor`).
    enable_git
        Set False for non-git workspaces — drops git tools and the
        worktree manager.

    Returns
    -------
    CodingAgentBundle
        Fully wired bundle with ``tools`` ready to plug into
        ``Agent.tools(...)`` plus every primitive exposed for inspection.

    Example
    -------
    >>> from adk_fluent import Agent, H
    >>> harness = H.coding_agent("/repo")
    >>> agent = (
    ...     Agent("coder", "gemini-2.5-pro")
    ...     .instruct("You are a senior engineer. Use the provided tools.")
    ...     .tools(harness.tools)
    ...     .build()
    ... )
    """
    workspace_str = str(Path(workspace).resolve())

    sandbox = SandboxPolicy(
        workspace=workspace_str,
        allow_shell=allow_mutations,
        allow_network=allow_network,
        max_output_bytes=max_output_bytes,
    )

    # Permission defaults model "Claude Code's safe default":
    # read tools auto-allow; write/exec tools ask the embedding app.
    permissions = PermissionPolicy(
        allow=frozenset(
            {
                "read_file",
                "list_dir",
                "glob_search",
                "grep_search",
                "git_status",
                "git_diff",
                "git_log",
                "git_branch",
            }
        ),
        ask=frozenset(
            {
                "write_file",
                "edit_file",
                "bash",
                "run_code",
                "git_commit",
                "start_process",
                "stop_process",
                "enter_worktree",
                "exit_worktree",
            }
            if allow_mutations
            else set()
        ),
        deny=frozenset(set() if allow_mutations else {"write_file", "edit_file", "bash", "run_code", "git_commit"}),
    )
    approval_memory = ApprovalMemory()

    usage = UsageTracker()
    memory = ProjectMemory(str(memory_path or Path(workspace_str) / "CLAUDE.md"))
    artifacts = ArtifactStore(str(Path(workspace_str) / ".harness" / "artifacts"))

    todos = TodoStore()
    plan_mode = PlanMode()
    worktrees = WorktreeManager(workspace_str) if enable_git else None
    git = GitCheckpointer(workspace_str) if enable_git else None

    executor = CodeExecutor(sandbox, interpreters=interpreters or {})

    tools: list[Callable] = []
    tools.extend(workspace_tools(sandbox, read_only=not allow_mutations))
    if allow_network:
        # Lazy-import to keep import graph minimal for sandboxed envs.
        from adk_fluent._harness._web import web_tools

        tools.extend(web_tools(sandbox))
    if allow_mutations:
        from adk_fluent._harness._processes import process_tools

        tools.extend(process_tools(sandbox))
    if enable_git:
        from adk_fluent._harness._git_tools import git_tools

        tools.extend(git_tools(path=workspace_str, allow_shell=allow_mutations))
    tools.extend(executor.tools())
    tools.extend(todos.tools())
    tools.extend(plan_mode.tools())
    if worktrees is not None:
        tools.extend(worktrees.tools())
    tools.append(make_ask_user_tool(on_ask_user))

    return CodingAgentBundle(
        workspace=workspace_str,
        tools=tools,
        sandbox=sandbox,
        permissions=permissions,
        approval_memory=approval_memory,
        usage=usage,
        memory=memory,
        artifacts=artifacts,
        todos=todos,
        plan_mode=plan_mode,
        worktrees=worktrees,
        git=git,
        executor=executor,
    )
