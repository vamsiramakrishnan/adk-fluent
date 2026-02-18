"""Hand-written IR node types for adk-fluent primitives.

These represent concepts that have no ADK counterpart — they are
adk-fluent inventions compiled to custom BaseAgent subclasses by the
ADK backend.

For ADK-native agent types (AgentNode, SequenceNode, etc.), see
_ir_generated.py which is produced by scripts/ir_generator.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Union

__all__ = [
    # Primitive nodes
    "TransformNode", "TapNode", "FallbackNode", "RaceNode",
    "GateNode", "MapOverNode", "TimeoutNode", "RouteNode",
    "TransferNode",
    # Config
    "ExecutionConfig", "CompactionConfig",
    # Events
    "AgentEvent", "ToolCallInfo", "ToolResponseInfo",
    # Type union
    "Node",
]


# ======================================================================
# Primitive IR nodes (hand-written — no ADK counterpart)
# ======================================================================

@dataclass(frozen=True)
class TransformNode:
    """Zero-cost state transform. No LLM call."""
    name: str
    fn: Callable
    semantics: Literal["merge", "replace_session", "delete_keys"] = "merge"
    scope: Literal["session", "all"] = "session"
    affected_keys: frozenset[str] | None = None


@dataclass(frozen=True)
class TapNode:
    """Zero-cost observation. No LLM call, no state mutation."""
    name: str
    fn: Callable


@dataclass(frozen=True)
class FallbackNode:
    """Try children in order. First success wins."""
    name: str
    children: tuple = ()


@dataclass(frozen=True)
class RaceNode:
    """Run children concurrently. First to finish wins."""
    name: str
    children: tuple = ()


@dataclass(frozen=True)
class GateNode:
    """Human-in-the-loop approval gate."""
    name: str
    predicate: Callable
    message: str = "Approval required"
    gate_key: str = "_gate_approved"


@dataclass(frozen=True)
class MapOverNode:
    """Iterate a sub-agent over each item in a state list."""
    name: str
    list_key: str
    body: Any = None
    item_key: str = "_item"
    output_key: str = "results"


@dataclass(frozen=True)
class TimeoutNode:
    """Wrap a sub-agent with a time limit."""
    name: str
    body: Any = None
    seconds: float = 0.0


@dataclass(frozen=True)
class RouteNode:
    """Deterministic state-based routing. No LLM call."""
    name: str
    key: str | None = None
    rules: tuple = ()
    default: Any = None


@dataclass(frozen=True)
class TransferNode:
    """Hard agent transfer (ADK's transfer_to_agent)."""
    name: str
    target: str = ""
    condition: Callable | None = None


# ======================================================================
# Execution configuration
# ======================================================================

@dataclass(frozen=True)
class CompactionConfig:
    """Event compaction settings (maps to ADK EventsCompactionConfig)."""
    interval: int = 10
    overlap: int = 2
    token_threshold: int | None = None
    event_retention_size: int | None = None


@dataclass(frozen=True)
class ExecutionConfig:
    """Top-level execution configuration."""
    app_name: str = "adk_fluent_app"
    max_llm_calls: int = 500
    timeout_seconds: float | None = None
    streaming_mode: Literal["none", "sse", "bidi"] = "none"
    resumable: bool = False
    compaction: CompactionConfig | None = None
    custom_metadata: dict[str, Any] | None = None


# ======================================================================
# Backend-agnostic event types
# ======================================================================

@dataclass
class ToolCallInfo:
    """A tool invocation within an event."""
    tool_name: str
    args: dict[str, Any]
    call_id: str


@dataclass
class ToolResponseInfo:
    """A tool response within an event."""
    tool_name: str
    result: Any
    call_id: str


@dataclass
class AgentEvent:
    """Backend-agnostic representation of an execution event."""
    author: str
    content: str | None = None
    state_delta: dict[str, Any] = field(default_factory=dict)
    artifact_delta: dict[str, int] = field(default_factory=dict)
    transfer_to: str | None = None
    escalate: bool = False
    tool_calls: list[ToolCallInfo] = field(default_factory=list)
    tool_responses: list[ToolResponseInfo] = field(default_factory=list)
    is_final: bool = False
    is_partial: bool = False
    end_of_agent: bool = False
    agent_state: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


# ======================================================================
# Node type union (extended by _ir_generated.py)
# ======================================================================

# This is the base union of hand-written node types.
# _ir_generated.py extends this with generated ADK node types.
Node = Union[
    TransformNode, TapNode, FallbackNode, RaceNode,
    GateNode, MapOverNode, TimeoutNode, RouteNode,
    TransferNode,
]
