"""SubagentSpec — declarative description of one dynamically-spawned specialist."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["SubagentSpec"]


@dataclass(frozen=True, slots=True)
class SubagentSpec:
    """Declarative description of a subagent role.

    A spec is pure data: the runner is what turns it into a running
    agent. Specs are frozen so they can be shared across threads and
    cached in a registry without defensive copies.

    Args:
        role: Short, stable identifier ("researcher", "reviewer"). The
            parent agent names roles via this string.
        instruction: System prompt / role description. The runner
            usually concatenates it with the per-call prompt.
        description: One-line human description. Surfaced in the task
            tool's auto-generated docstring so the parent LLM knows
            what the specialist is for.
        model: Optional model override. ``None`` means "inherit from
            the runner's default".
        tool_names: Names of tools the subagent may call. The runner
            resolves names to actual tool callables.
        permission_mode: One of the adk_fluent PermissionMode constants.
            Defaults to ``"default"`` (ask for everything not allowed).
        max_tokens: Optional per-invocation token budget. ``None``
            means "unbounded" (or inherit from the runner).
        metadata: Free-form dict for runner-specific configuration.
    """

    role: str
    instruction: str
    description: str = ""
    model: str | None = None
    tool_names: tuple[str, ...] = ()
    permission_mode: str = "default"
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.role:
            raise ValueError("SubagentSpec.role must be a non-empty string")
        if not self.instruction:
            raise ValueError("SubagentSpec.instruction must be a non-empty string")
