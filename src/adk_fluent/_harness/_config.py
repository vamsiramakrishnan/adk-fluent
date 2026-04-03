"""Harness configuration — unified config for .harness()."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from adk_fluent._harness._permissions import ApprovalMemory, PermissionPolicy
from adk_fluent._harness._sandbox import SandboxPolicy

__all__ = ["HarnessConfig"]


@dataclass(slots=True)
class HarnessConfig:
    """Configuration for an agent harness runtime."""

    permissions: PermissionPolicy = field(default_factory=PermissionPolicy)
    sandbox: SandboxPolicy = field(default_factory=SandboxPolicy)
    auto_compress_threshold: int = 100_000
    approval_handler: Callable[[str, dict], bool] | None = None
    approval_memory: ApprovalMemory | None = None
