"""Harness namespace (H) — building blocks for AI coding harnesses.

A harness is a CodAct agent runtime: sandboxed tools, permissions,
streaming, compression, hooks, checkpoints, and an interactive REPL.

The ``H`` namespace provides composable primitives. This package is
split into focused modules:

    _events.py         — HarnessEvent hierarchy
    _permissions.py    — PermissionPolicy + approval persistence
    _sandbox.py        — SandboxPolicy + symlink-safe paths
    _tools.py          — workspace tool factories
    _streaming.py      — PTY-based streaming bash
    _git.py            — git checkpoint/rollback
    _gitignore.py      — gitignore-aware file filtering
    _hooks             — unified hook foundation (lives at adk_fluent._hooks)
    _artifacts.py      — artifact/blob handling
    _compression.py    — context auto-compression
    _dispatcher.py     — ADK→HarnessEvent translation
    _repl.py           — interactive REPL loop
    _skills.py         — SkillSpec + compilation
    _config.py         — HarnessConfig
    _namespace.py      — H class (public API)

    # New affordance modules
    _web.py            — web fetch and search tools
    _memory.py         — persistent project memory
    _usage.py          — token/cost tracking
    _diff.py           — diff-mode edit previews
    _multimodal.py     — image/PDF reading
    _processes.py      — background process management
    _mcp.py            — bulk MCP server loading
    _error_strategy.py — harness-level error recovery
    _notebook.py       — Jupyter notebook tools
    _tasks.py          — background task management
    _renderer.py       — event display formatting
"""

# Events
# Artifacts
# Agent self-management tools (TodoStore, PlanMode, AskUser, Worktree)
from adk_fluent._harness._agent_tools import (
    MUTATING_TOOLS,
    PlanMode,
    TodoItem,
    TodoStore,
    WorktreeManager,
    make_ask_user_tool,
)
from adk_fluent._harness._artifacts import ArtifactRef, ArtifactStore

# Budget monitor (lives in adk_fluent._budget, re-exported here)
from adk_fluent._budget import BudgetMonitor, BudgetPlugin, BudgetPolicy, Threshold

# Polyglot code execution
from adk_fluent._harness._code_executor import CodeExecutor, CodeRunResult

# Coding-agent preset
from adk_fluent._harness._coding_agent import CodingAgentBundle, coding_agent

# Commands (slash commands)
from adk_fluent._harness._commands import CommandRegistry, CommandSpec

# Compression (lives in adk_fluent._compression, re-exported here)
from adk_fluent._compression import CompressionStrategy, ContextCompressor

# Config
from adk_fluent._harness._config import HarnessConfig

# Diff mode
from adk_fluent._harness._diff import PendingEditStore, make_apply_edit, make_diff_edit_file

# Dispatcher
from adk_fluent._harness._dispatcher import EventDispatcher

# Error strategy
from adk_fluent._harness._error_strategy import ErrorStrategy, make_error_callbacks

# Event bus
from adk_fluent._harness._event_bus import EventBus
from adk_fluent._harness._events import (
    ArtifactSaved,
    CapabilityLoaded,
    CompressionTriggered,
    ErrorOccurred,
    FileEdited,
    GitCheckpoint,
    HarnessEvent,
    HookFired,
    ManifoldFinalized,
    PermissionRequest,
    PermissionResult,
    ProcessEvent,
    TaskEvent,
    TextChunk,
    ToolCallEnd,
    ToolCallStart,
    TurnComplete,
    UsageUpdate,
)

# Fork
from adk_fluent._harness._fork import Branch, ForkManager

# Git
from adk_fluent._harness._git import GitCheckpointer

# Git tools
from adk_fluent._harness._git_tools import git_tools

# Gitignore
from adk_fluent._harness._gitignore import GitignoreMatcher, load_gitignore

# Hooks — unified foundation lives in adk_fluent._hooks
from adk_fluent._hooks import (
    HookAction,
    HookContext,
    HookDecision,
    HookEntry,
    HookEvent,
    HookMatcher,
    HookPlugin,
    HookRegistry,
    SystemMessageChannel,
)

# Interrupt
from adk_fluent._harness._interrupt import (
    CancellationToken,
    TurnSnapshot,
    make_cancellation_callback,
)

# Manifold
from adk_fluent._harness._manifold import (
    CapabilityEntry,
    CapabilityRegistry,
    CapabilityType,
    ManifoldToolset,
)

# MCP
from adk_fluent._harness._mcp import load_mcp_config, load_mcp_tools

# Memory
from adk_fluent._harness._memory import MemoryHierarchy, ProjectMemory

# Multimodal
from adk_fluent._harness._multimodal import make_multimodal_read_file

# H namespace
from adk_fluent._harness._namespace import H

# Notebook
from adk_fluent._harness._notebook import (
    make_edit_notebook_cell,
    make_read_notebook,
    notebook_tools,
)

# Permissions (adk_fluent._permissions — decision-based layer with modes)
from adk_fluent._permissions import (
    ALL_MODES,
    ApprovalMemory,
    DEFAULT_MUTATING_TOOLS,
    DEFAULT_READ_ONLY_TOOLS,
    PermissionBehavior,
    PermissionDecision,
    PermissionHandler,
    PermissionMode,
    PermissionPlugin,
    PermissionPolicy,
)

# Processes
from adk_fluent._harness._processes import ProcessRegistry, process_tools

# Renderer
from adk_fluent._harness._renderer import JsonRenderer, PlainRenderer, RichRenderer

# REPL
from adk_fluent._harness._repl import HarnessRepl, ReplConfig

# Filesystem backends (adk_fluent._fs)
from adk_fluent._fs import (
    FsBackend,
    FsEntry,
    FsStat,
    LocalBackend,
    MemoryBackend,
    SandboxViolation,
    SandboxedBackend,
    workspace_tools_with_backend,
)

# Sandbox
from adk_fluent._harness._sandbox import SandboxPolicy

# Skills
from adk_fluent._harness._skills import SkillSpec, compile_skills_to_static

# Streaming
from adk_fluent._harness._streaming import StreamingBash, make_streaming_bash

# Session tape
from adk_fluent._harness._tape import SessionTape

# Task ledger
from adk_fluent._harness._task_ledger import TaskLedger, TaskState

# Tasks (legacy — prefer TaskLedger)
from adk_fluent._harness._tasks import TaskRegistry, TaskStatus, task_tools

# Tool policy
from adk_fluent._harness._tool_policy import ToolPolicy, ToolRule

# Tools
from adk_fluent._harness._tools import (
    make_bash,
    make_edit_file,
    make_glob_search,
    make_grep_search,
    make_list_dir,
    make_read_file,
    make_write_file,
    workspace_tools,
)

# Usage tracking
from adk_fluent._harness._usage import TurnUsage, UsageTracker

# Web tools
from adk_fluent._harness._web import make_web_fetch, web_tools

# Backward-compatible aliases for old private names
_make_read_file = make_read_file
_make_edit_file = make_edit_file
_make_write_file = make_write_file
_make_glob_search = make_glob_search
_make_grep_search = make_grep_search
_make_bash = make_bash
_make_list_dir = make_list_dir
_compile_skills_to_static = compile_skills_to_static

__all__ = [
    # Namespace
    "H",
    # Config
    "HarnessConfig",
    # Events
    "HarnessEvent",
    "TextChunk",
    "ToolCallStart",
    "ToolCallEnd",
    "PermissionRequest",
    "PermissionResult",
    "TurnComplete",
    "GitCheckpoint",
    "CompressionTriggered",
    "HookFired",
    "ArtifactSaved",
    "FileEdited",
    "ErrorOccurred",
    "UsageUpdate",
    "ProcessEvent",
    "TaskEvent",
    "CapabilityLoaded",
    "ManifoldFinalized",
    # Event bus
    "EventBus",
    # Budget monitor
    "BudgetMonitor",
    "BudgetPlugin",
    "BudgetPolicy",
    "Threshold",
    # Tool policy
    "ToolPolicy",
    "ToolRule",
    # Task ledger
    "TaskLedger",
    "TaskState",
    # Manifold
    "CapabilityType",
    "CapabilityEntry",
    "CapabilityRegistry",
    "ManifoldToolset",
    # Permissions
    "ALL_MODES",
    "ApprovalMemory",
    "DEFAULT_MUTATING_TOOLS",
    "DEFAULT_READ_ONLY_TOOLS",
    "PermissionBehavior",
    "PermissionDecision",
    "PermissionHandler",
    "PermissionMode",
    "PermissionPlugin",
    "PermissionPolicy",
    # Sandbox
    "SandboxPolicy",
    # Filesystem backends
    "FsBackend",
    "FsEntry",
    "FsStat",
    "LocalBackend",
    "MemoryBackend",
    "SandboxedBackend",
    "SandboxViolation",
    "workspace_tools_with_backend",
    # Tools
    "make_read_file",
    "make_edit_file",
    "make_write_file",
    "make_glob_search",
    "make_grep_search",
    "make_bash",
    "make_list_dir",
    "workspace_tools",
    # Web
    "make_web_fetch",
    "web_tools",
    # Polyglot code execution
    "CodeExecutor",
    "CodeRunResult",
    # Agent self-management tools
    "TodoStore",
    "TodoItem",
    "PlanMode",
    "MUTATING_TOOLS",
    "WorktreeManager",
    "make_ask_user_tool",
    # Coding-agent preset
    "coding_agent",
    "CodingAgentBundle",
    # Memory
    "ProjectMemory",
    "MemoryHierarchy",
    # Interrupt
    "CancellationToken",
    "TurnSnapshot",
    "make_cancellation_callback",
    # Fork
    "ForkManager",
    "Branch",
    # Usage
    "UsageTracker",
    "TurnUsage",
    # Diff mode
    "PendingEditStore",
    "make_diff_edit_file",
    "make_apply_edit",
    # Multimodal
    "make_multimodal_read_file",
    # Processes
    "ProcessRegistry",
    "process_tools",
    # MCP
    "load_mcp_tools",
    "load_mcp_config",
    # Error strategy
    "ErrorStrategy",
    "make_error_callbacks",
    # Notebook
    "make_read_notebook",
    "make_edit_notebook_cell",
    "notebook_tools",
    # Tasks
    "TaskRegistry",
    "TaskStatus",
    "task_tools",
    # Renderer
    "PlainRenderer",
    "RichRenderer",
    "JsonRenderer",
    # Streaming
    "StreamingBash",
    "make_streaming_bash",
    # Git
    "GitCheckpointer",
    # Git tools
    "git_tools",
    # Gitignore
    "GitignoreMatcher",
    "load_gitignore",
    # Hooks (unified foundation)
    "HookAction",
    "HookContext",
    "HookDecision",
    "HookEntry",
    "HookEvent",
    "HookMatcher",
    "HookPlugin",
    "HookRegistry",
    "SystemMessageChannel",
    # Artifacts
    "ArtifactStore",
    "ArtifactRef",
    # Compression
    "ContextCompressor",
    "CompressionStrategy",
    # Dispatcher
    "EventDispatcher",
    # REPL
    "HarnessRepl",
    "ReplConfig",
    # Session tape
    "SessionTape",
    # Commands
    "CommandRegistry",
    "CommandSpec",
    # Skills
    "SkillSpec",
    "compile_skills_to_static",
]
