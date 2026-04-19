"""adk-fluent exception hierarchy.

All adk-fluent exceptions inherit from :class:`ADKFluentError`.
Users can catch the base class to handle any library error uniformly::

    from adk_fluent import ADKFluentError

    try:
        agent.build()
    except ADKFluentError as e:
        logger.error("adk-fluent error: %s", e)
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ADKFluentError",
    "BuilderError",
    "GuardViolation",
    "PredicateError",
    "A2UIError",
    "A2UINotInstalled",
    "A2UISurfaceError",
    "A2UIBindingError",
]


class ADKFluentError(Exception):
    """Base exception for all adk-fluent errors."""


class BuilderError(ADKFluentError):
    """Raised when ``.build()`` fails due to invalid configuration.

    Attributes:
        builder_name: Name passed to the builder constructor.
        builder_type: Class name of the builder (e.g., ``"Agent"``).
        field_errors: Human-readable list of field-level issues.
        original: The underlying exception (usually ``pydantic.ValidationError``).
    """

    def __init__(
        self,
        builder_name: str,
        builder_type: str,
        field_errors: list[str],
        original: Exception,
    ):
        self.builder_name = builder_name
        self.builder_type = builder_type
        self.field_errors = field_errors
        self.original = original
        lines = [f"Failed to build {builder_type}('{builder_name}'):"]
        for err in field_errors:
            lines.append(f"  - {err}")
        super().__init__("\n".join(lines))


class GuardViolation(ADKFluentError):
    """Raised when a guard rejects input or output.

    Attributes:
        guard_kind: Type of guard (``"pii"``, ``"toxicity"``, ``"length"``, etc.).
        phase: When the violation occurred (``"pre_model"``, ``"post_model"``, etc.).
        detail: Human-readable explanation.
        value: The rejected content (may be truncated for large payloads).
    """

    def __init__(
        self,
        guard_kind: str,
        phase: str,
        detail: str,
        value: Any = None,
    ):
        self.guard_kind = guard_kind
        self.phase = phase
        self.detail = detail
        self.value = value
        super().__init__(f"[{guard_kind}] {detail}")


class PredicateError(ADKFluentError):
    """Raised when a predicate function fails in strict mode.

    In default mode, predicate failures are logged as warnings and treated
    as ``False``. Enable strict mode with ``Agent(...).debug()`` or by
    passing ``strict=True`` to :func:`evaluate_predicate`.

    Attributes:
        predicate_repr: String representation of the failing predicate.
        available_keys: State keys that were available when the error occurred.
        original: The underlying exception.
    """

    def __init__(
        self,
        predicate_repr: str,
        available_keys: list[str],
        original: Exception,
    ):
        self.predicate_repr = predicate_repr
        self.available_keys = available_keys
        self.original = original
        super().__init__(
            f"Predicate {predicate_repr} raised {type(original).__name__}: {original}\n"
            f"  State keys available: {available_keys}\n"
            f"  Hint: Check that your predicate handles missing keys gracefully,\n"
            f"  or use .get() with a default value."
        )


class A2UIError(ADKFluentError):
    """Base for all A2UI errors."""


class A2UINotInstalled(A2UIError):
    """Raised when an A2UI feature requires the optional 'a2ui-agent' package."""


class A2UISurfaceError(A2UIError):
    """Raised when a UISurface fails static validation."""

    def __init__(self, message: str, *, surface_name: str | None = None) -> None:
        self.surface_name = surface_name
        super().__init__(message if not surface_name else f"[{surface_name}] {message}")


class A2UIBindingError(A2UISurfaceError):
    """Raised when a UIBinding references an undeclared data path."""

    def __init__(
        self,
        message: str,
        *,
        surface_name: str | None = None,
        path: str | None = None,
    ) -> None:
        self.path = path
        super().__init__(message, surface_name=surface_name)
