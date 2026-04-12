"""Harness configuration — unified config for .harness()."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from adk_fluent._harness._sandbox import SandboxPolicy
from adk_fluent._permissions import ApprovalMemory, PermissionPolicy

__all__ = ["HarnessConfig"]


@dataclass(slots=True)
class HarnessConfig:
    """Configuration for an agent harness runtime.

    Stores all harness-level settings. The ``.harness()`` method on
    the Agent builder reads these and wires the appropriate callbacks.
    """

    permissions: PermissionPolicy = field(default_factory=PermissionPolicy)
    sandbox: SandboxPolicy = field(default_factory=SandboxPolicy)
    auto_compress_threshold: int = 100_000
    approval_handler: Callable[[str, dict], bool] | None = None
    approval_memory: ApprovalMemory | None = None
    # New affordances
    usage: Any | None = None  # UsageTracker
    memory: Any | None = None  # ProjectMemory
    on_error: Any | None = None  # ErrorStrategy
