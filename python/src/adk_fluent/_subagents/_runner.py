"""SubagentRunner — the runtime contract for turning a spec into a result.

The runner is intentionally **not** coupled to ADK. It is a plain callable
the task tool invokes synchronously. That keeps this package testable
without spinning up a live model and lets callers wire in whatever
execution engine they like:

- Run a local ADK agent with a compiled tool set.
- POST to an A2A endpoint.
- Return canned responses in tests.

Two public types:

- :class:`SubagentRunner` — Protocol describing the runner contract.
- :class:`FakeSubagentRunner` — simple deterministic runner for tests
  and for quick local experiments.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

from adk_fluent._subagents._result import SubagentResult
from adk_fluent._subagents._spec import SubagentSpec

__all__ = ["SubagentRunner", "FakeSubagentRunner", "SubagentRunnerError"]


class SubagentRunnerError(RuntimeError):
    """Raised when a runner cannot honour an invocation request."""


@runtime_checkable
class SubagentRunner(Protocol):
    """Protocol: synchronous subagent execution.

    Runners receive a spec, a per-call prompt, and a free-form context
    dict (the state the parent exposes). They must return a fully
    populated :class:`SubagentResult`; exceptions should be caught and
    surfaced via the ``error`` field unless the failure is catastrophic,
    in which case raising :class:`SubagentRunnerError` is acceptable.
    """

    def run(
        self,
        spec: SubagentSpec,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> SubagentResult:
        """Execute ``spec`` with ``prompt`` and return a :class:`SubagentResult`."""


class FakeSubagentRunner:
    """Deterministic runner used by tests and local sandboxes.

    Args:
        responder: Callable invoked per run. Receives ``(spec, prompt,
            context)`` and returns the plain-text output. If omitted,
            the runner echoes the prompt.
        usage: Fixed usage dict attached to every result. Defaults to
            an empty dict.
        error_for_role: Optional mapping role -> error string. When a
            run targets a listed role the runner returns a failed
            result (useful for testing error paths).
    """

    def __init__(
        self,
        responder: Callable[[SubagentSpec, str, dict[str, Any] | None], str]
        | None = None,
        *,
        usage: dict[str, int] | None = None,
        error_for_role: dict[str, str] | None = None,
    ) -> None:
        self._responder = responder or (lambda spec, prompt, ctx: f"echo: {prompt}")
        self._usage = dict(usage or {})
        self._errors = dict(error_for_role or {})
        self._calls: list[tuple[SubagentSpec, str, dict[str, Any] | None]] = []

    @property
    def calls(
        self,
    ) -> list[tuple[SubagentSpec, str, dict[str, Any] | None]]:
        """Return the call log (spec, prompt, context) in invocation order."""
        return list(self._calls)

    def run(
        self,
        spec: SubagentSpec,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> SubagentResult:
        self._calls.append((spec, prompt, context))
        if spec.role in self._errors:
            return SubagentResult(
                role=spec.role,
                output="",
                usage=dict(self._usage),
                error=self._errors[spec.role],
            )
        try:
            output = self._responder(spec, prompt, context)
        except Exception as exc:  # noqa: BLE001
            return SubagentResult(
                role=spec.role,
                output="",
                usage=dict(self._usage),
                error=f"Subagent responder raised: {exc}",
            )
        return SubagentResult(
            role=spec.role,
            output=str(output),
            usage=dict(self._usage),
        )
