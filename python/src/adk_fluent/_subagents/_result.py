"""SubagentResult — structured return from a subagent invocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["SubagentResult"]


@dataclass(frozen=True, slots=True)
class SubagentResult:
    """Structured output from a subagent run.

    Args:
        role: The role the subagent was invoked under (matches the spec).
        output: Final text output the subagent produced.
        usage: Optional token/cost breakdown
            (``{"input_tokens": int, "output_tokens": int, ...}``).
        artifacts: Optional map of artifact name -> content produced
            during the run.
        metadata: Free-form runner-specific metadata. Keeping this off
            the hot fields lets the runner attach debugging context
            (turn count, stop reason) without polluting the core shape.
        error: Populated if the subagent failed; otherwise empty.
    """

    role: str
    output: str
    usage: dict[str, int] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def is_error(self) -> bool:
        return bool(self.error)

    def to_tool_output(self) -> str:
        """Serialise the result to the string the parent's task tool returns.

        Errors are surfaced as ``[role:error] reason``; successful runs
        prefix the role for provenance so the parent LLM can reason
        about which specialist produced which output.
        """
        if self.is_error:
            return f"[{self.role}:error] {self.error}"
        return f"[{self.role}] {self.output}"
