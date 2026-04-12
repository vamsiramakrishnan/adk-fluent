"""Structured events emitted by the harness runtime.

Events follow a typed hierarchy so consumers can pattern-match::

    match event:
        case TextChunk(text=t):  print(t, end="")
        case ToolCallStart():    show_spinner()
        case PermissionRequest():ask_user()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
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
]


@dataclass(frozen=True, slots=True)
class HarnessEvent:
    """Base class for structured harness events."""

    kind: str = ""


@dataclass(frozen=True, slots=True)
class TextChunk(HarnessEvent):
    """A chunk of streamed text from the LLM."""

    text: str = ""
    kind: str = "text"


@dataclass(frozen=True, slots=True)
class ToolCallStart(HarnessEvent):
    """A tool call is about to execute."""

    tool_name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    kind: str = "tool_call_start"


@dataclass(frozen=True, slots=True)
class ToolCallEnd(HarnessEvent):
    """A tool call has completed."""

    tool_name: str = ""
    result: str = ""
    duration_ms: float = 0.0
    kind: str = "tool_call_end"


@dataclass(frozen=True, slots=True)
class PermissionRequest(HarnessEvent):
    """The harness is requesting permission to execute a tool."""

    tool_name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    kind: str = "permission_request"


@dataclass(frozen=True, slots=True)
class PermissionResult(HarnessEvent):
    """Result of a permission decision."""

    tool_name: str = ""
    granted: bool = False
    remembered: bool = False
    kind: str = "permission_result"


@dataclass(frozen=True, slots=True)
class TurnComplete(HarnessEvent):
    """The agent turn has completed."""

    response: str = ""
    token_count: int = 0
    kind: str = "turn_complete"


@dataclass(frozen=True, slots=True)
class GitCheckpoint(HarnessEvent):
    """A git checkpoint was created or restored."""

    commit_sha: str = ""
    action: str = ""  # "create" or "restore"
    kind: str = "git_checkpoint"


@dataclass(frozen=True, slots=True)
class CompressionTriggered(HarnessEvent):
    """Context compression was triggered."""

    token_count: int = 0
    threshold: int = 0
    kind: str = "compression_triggered"


@dataclass(frozen=True, slots=True)
class HookFired(HarnessEvent):
    """A user-defined hook was executed."""

    hook_name: str = ""
    trigger: str = ""
    exit_code: int = 0
    kind: str = "hook_fired"


@dataclass(frozen=True, slots=True)
class ArtifactSaved(HarnessEvent):
    """An artifact/blob was saved."""

    name: str = ""
    size_bytes: int = 0
    kind: str = "artifact_saved"


@dataclass(frozen=True, slots=True)
class FileEdited(HarnessEvent):
    """A file was edited via the harness tools."""

    file_path: str = ""
    kind: str = "file_edited"


@dataclass(frozen=True, slots=True)
class ErrorOccurred(HarnessEvent):
    """A tool or model error occurred."""

    tool_name: str = ""
    error: str = ""
    kind: str = "error"


@dataclass(frozen=True, slots=True)
class UsageUpdate(HarnessEvent):
    """Token usage data from a model call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    kind: str = "usage_update"


@dataclass(frozen=True, slots=True)
class ProcessEvent(HarnessEvent):
    """A background process lifecycle event."""

    process_name: str = ""
    action: str = ""  # "started", "stopped", "exited"
    kind: str = "process_event"


@dataclass(frozen=True, slots=True)
class TaskEvent(HarnessEvent):
    """A background task lifecycle event."""

    task_name: str = ""
    status: str = ""  # "pending", "running", "complete", "failed"
    kind: str = "task_event"


@dataclass(frozen=True, slots=True)
class CapabilityLoaded(HarnessEvent):
    """A capability was loaded into the manifold."""

    capability_name: str = ""
    cap_type: str = ""  # "tool", "skill", "mcp_server"
    kind: str = "capability_loaded"


@dataclass(frozen=True, slots=True)
class ManifoldFinalized(HarnessEvent):
    """The manifold discovery phase completed."""

    tool_count: int = 0
    skill_count: int = 0
    mcp_count: int = 0
    kind: str = "manifold_finalized"
