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
    _hooks.py          — user-configurable event hooks
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
from adk_fluent._harness._artifacts import ArtifactRef, ArtifactStore

# Commands (slash commands)
from adk_fluent._harness._commands import CommandRegistry, CommandSpec

# Compression
from adk_fluent._harness._compression import (
    CompressionStrategy,
    ContextCompressor,
)

# Config
from adk_fluent._harness._config import HarnessConfig

# Diff mode
from adk_fluent._harness._diff import PendingEditStore, make_apply_edit, make_diff_edit_file

# Dispatcher
from adk_fluent._harness._dispatcher import EventDispatcher

# Error strategy
from adk_fluent._harness._error_strategy import ErrorStrategy, make_error_callbacks
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

# Git
from adk_fluent._harness._git import GitCheckpointer

# Git tools
from adk_fluent._harness._git_tools import git_tools

# Gitignore
from adk_fluent._harness._gitignore import GitignoreMatcher, load_gitignore

# Hooks
from adk_fluent._harness._hooks import HookRegistry, HookSpec

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
from adk_fluent._harness._memory import ProjectMemory

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

# Permissions
from adk_fluent._harness._permissions import (
    ApprovalMemory,
    PermissionPolicy,
    make_permission_callback,
)

# Processes
from adk_fluent._harness._processes import ProcessRegistry, process_tools

# Renderer
from adk_fluent._harness._renderer import JsonRenderer, PlainRenderer, RichRenderer

# REPL
from adk_fluent._harness._repl import HarnessRepl, ReplConfig

# Sandbox
from adk_fluent._harness._sandbox import SandboxPolicy

# Skills
from adk_fluent._harness._skills import SkillSpec, compile_skills_to_static

# Streaming
from adk_fluent._harness._streaming import StreamingBash, make_streaming_bash

# Session tape
from adk_fluent._harness._tape import SessionTape

# Tasks
from adk_fluent._harness._tasks import TaskRegistry, TaskStatus, task_tools

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
_make_permission_callback = make_permission_callback
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
    # Manifold
    "CapabilityType",
    "CapabilityEntry",
    "CapabilityRegistry",
    "ManifoldToolset",
    # Permissions
    "PermissionPolicy",
    "ApprovalMemory",
    "make_permission_callback",
    # Sandbox
    "SandboxPolicy",
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
    # Memory
    "ProjectMemory",
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
    # Hooks
    "HookRegistry",
    "HookSpec",
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
