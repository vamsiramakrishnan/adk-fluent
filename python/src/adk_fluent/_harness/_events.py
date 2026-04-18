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
    # Workflow lifecycle (Phase C)
    "StepStarted",
    "StepCompleted",
    "IterationStarted",
    "IterationCompleted",
    "BranchStarted",
    "BranchCompleted",
    "SubagentStarted",
    "SubagentCompleted",
    "AttemptFailed",
    # Signals + interrupt (Phase F/G)
    "SignalChanged",
    "Interrupted",
    # Cross-namespace emitters (Phase H)
    "GuardFired",
    "EvalEvent",
    "EffectRecorded",
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


# ----------------------------------------------------------------------
# Workflow lifecycle (Phase C)
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StepStarted(HarnessEvent):
    """An agent step in any workflow is about to execute.

    Emitted via ADK ``before_agent_callback`` for every agent in the
    invocation tree. Consumers correlate StepStarted/StepCompleted by
    ``agent_name``; the seq numbers on the tape preserve ordering.
    """

    agent_name: str = ""
    agent_type: str = ""
    parent_name: str = ""
    kind: str = "step_started"


@dataclass(frozen=True, slots=True)
class StepCompleted(HarnessEvent):
    """An agent step finished."""

    agent_name: str = ""
    agent_type: str = ""
    parent_name: str = ""
    duration_ms: float = 0.0
    kind: str = "step_completed"


@dataclass(frozen=True, slots=True)
class IterationStarted(HarnessEvent):
    """A Loop iteration is about to run its body."""

    loop_name: str = ""
    iteration: int = 0
    kind: str = "iteration_started"


@dataclass(frozen=True, slots=True)
class IterationCompleted(HarnessEvent):
    """A Loop iteration has finished its body."""

    loop_name: str = ""
    iteration: int = 0
    kind: str = "iteration_completed"


@dataclass(frozen=True, slots=True)
class BranchStarted(HarnessEvent):
    """A FanOut branch is about to execute in parallel."""

    fanout_name: str = ""
    branch_name: str = ""
    branch_index: int = 0
    kind: str = "branch_started"


@dataclass(frozen=True, slots=True)
class BranchCompleted(HarnessEvent):
    """A FanOut branch finished."""

    fanout_name: str = ""
    branch_name: str = ""
    branch_index: int = 0
    duration_ms: float = 0.0
    kind: str = "branch_completed"


@dataclass(frozen=True, slots=True)
class SubagentStarted(HarnessEvent):
    """A dynamically spawned subagent is about to run."""

    role: str = ""
    prompt: str = ""
    kind: str = "subagent_started"


@dataclass(frozen=True, slots=True)
class SubagentCompleted(HarnessEvent):
    """A dynamically spawned subagent finished."""

    role: str = ""
    is_error: bool = False
    output_preview: str = ""
    duration_ms: float = 0.0
    kind: str = "subagent_completed"


@dataclass(frozen=True, slots=True)
class AttemptFailed(HarnessEvent):
    """An attempt in a retry/fallback chain failed."""

    agent_name: str = ""
    attempt_index: int = 0
    error: str = ""
    kind: str = "attempt_failed"


# ----------------------------------------------------------------------
# Signals + interrupt (Phase F / G)
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SignalChanged(HarnessEvent):
    """A reactive signal's value changed."""

    name: str = ""
    version: int = 0
    # Values are serialisable (dicts, strings, numbers, bool, None).
    # Complex objects are stringified to preserve JSONL portability.
    value: Any = None
    previous: Any = None
    kind: str = "signal_changed"


@dataclass(frozen=True, slots=True)
class Interrupted(HarnessEvent):
    """An agent was pre-empted; may be resumed from ``resume_cursor``."""

    agent_name: str = ""
    reason: str = ""
    resume_cursor: int = 0
    kind: str = "interrupted"


# ----------------------------------------------------------------------
# Cross-namespace emitters (Phase H)
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GuardFired(HarnessEvent):
    """An output guard rejected or modified a model response.

    Emitted from ``.guard()``-wired callbacks whenever a guard raises
    ``GuardViolation`` or chooses to rewrite the response. Makes guard
    activity tape-visible so replays can show exactly which rule fired.

    ``action`` is ``"reject"`` for violations that raised the exception,
    ``"rewrite"``/``"redact"`` for silent transformations. Parallels the
    ``HookFired`` event for the hook registry.
    """

    guard_name: str = ""
    agent_name: str = ""
    reason: str = ""
    action: str = "reject"  # "reject" | "rewrite" | "redact"
    kind: str = "guard_fired"


@dataclass(frozen=True, slots=True)
class EvalEvent(HarnessEvent):
    """One case/metric datapoint from an eval suite run."""

    suite_name: str = ""
    case_id: str = ""
    metric: str = ""
    score: float = 0.0
    passed: bool = False
    detail: str = ""
    kind: str = "eval_event"


@dataclass(frozen=True, slots=True)
class EffectRecorded(HarnessEvent):
    """An effectful tool call was memoised or replayed from cache.

    Emitted by the effect-cache interceptor (Phase E) whenever it either
    records a fresh result or short-circuits a call by returning a cached
    value. The ``source`` field discriminates ``"fresh"`` vs ``"cache"``.
    """

    tool_name: str = ""
    key: str = ""
    source: str = "fresh"  # "fresh" | "cache"
    duration_ms: float = 0.0
    kind: str = "effect_recorded"
