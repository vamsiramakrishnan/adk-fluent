"""Harness namespace (H) — building blocks for AI coding harnesses.

A harness is a CodAct agent runtime: sandboxed tools, permissions,
streaming, compression, hooks, checkpoints, and an interactive REPL.

The ``H`` namespace provides composable primitives. This package is
split into focused modules:

    _events.py       — HarnessEvent hierarchy
    _permissions.py  — PermissionPolicy + approval persistence
    _sandbox.py      — SandboxPolicy + symlink-safe paths
    _tools.py        — workspace tool factories
    _streaming.py    — PTY-based streaming bash
    _git.py          — git checkpoint/rollback
    _gitignore.py    — gitignore-aware file filtering
    _hooks.py        — user-configurable event hooks
    _artifacts.py    — artifact/blob handling
    _compression.py  — context auto-compression
    _dispatcher.py   — ADK→HarnessEvent translation
    _repl.py         — interactive REPL loop
    _skills.py       — SkillSpec + compilation
    _config.py       — HarnessConfig
    _namespace.py    — H class (public API)
"""

# Events
from adk_fluent._harness._events import (
    ArtifactSaved,
    CompressionTriggered,
    GitCheckpoint,
    HarnessEvent,
    HookFired,
    PermissionRequest,
    PermissionResult,
    TextChunk,
    ToolCallEnd,
    ToolCallStart,
    TurnComplete,
)

# Permissions
from adk_fluent._harness._permissions import (
    ApprovalMemory,
    PermissionPolicy,
    make_permission_callback,
)

# Sandbox
from adk_fluent._harness._sandbox import SandboxPolicy

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

# Streaming
from adk_fluent._harness._streaming import StreamingBash, make_streaming_bash

# Git
from adk_fluent._harness._git import GitCheckpointer

# Gitignore
from adk_fluent._harness._gitignore import GitignoreMatcher, load_gitignore

# Hooks
from adk_fluent._harness._hooks import HookRegistry, HookSpec

# Artifacts
from adk_fluent._harness._artifacts import ArtifactRef, ArtifactStore

# Compression
from adk_fluent._harness._compression import (
    CompressionStrategy,
    ContextCompressor,
)

# Dispatcher
from adk_fluent._harness._dispatcher import EventDispatcher

# REPL
from adk_fluent._harness._repl import HarnessRepl, ReplConfig

# Skills
from adk_fluent._harness._skills import SkillSpec, compile_skills_to_static

# Config
from adk_fluent._harness._config import HarnessConfig

# H namespace
from adk_fluent._harness._namespace import H

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
    # Streaming
    "StreamingBash",
    "make_streaming_bash",
    # Git
    "GitCheckpointer",
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
    # Skills
    "SkillSpec",
    "compile_skills_to_static",
]
