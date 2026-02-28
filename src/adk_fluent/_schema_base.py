"""Shared declarative metaclass and annotation types for adk-fluent schemas.

DeclarativeMetaclass introspects Annotated type hints at class definition
time, extracting annotation instances into structured field metadata. This
is the shared base for StateSchema, ToolSchema, CallbackSchema, and
PredicateSchema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, get_args, get_origin, get_type_hints

__all__ = [
    "DeclarativeField",
    "DeclarativeMetaclass",
    "DeclarativeSchema",
    "Reads",
    "Writes",
    "Param",
    "Confirms",
    "Timeout",
]


# ======================================================================
# Shared annotations
# ======================================================================

_VALID_SCOPES = frozenset({"session", "app", "user", "temp"})


@dataclass(frozen=True)
class Reads:
    """Field is read from state before execution."""

    scope: str = "session"

    def __post_init__(self) -> None:
        if self.scope not in _VALID_SCOPES:
            raise ValueError(f"Invalid scope '{self.scope}'. Must be one of: {', '.join(sorted(_VALID_SCOPES))}")


@dataclass(frozen=True)
class Writes:
    """Field is written to state after execution."""

    scope: str = "session"

    def __post_init__(self) -> None:
        if self.scope not in _VALID_SCOPES:
            raise ValueError(f"Invalid scope '{self.scope}'. Must be one of: {', '.join(sorted(_VALID_SCOPES))}")


@dataclass(frozen=True)
class Param:
    """Field is a tool/function parameter (not from state)."""

    required: bool = True


@dataclass(frozen=True)
class Confirms:
    """Tool requires user confirmation before execution."""

    message: str = ""


@dataclass(frozen=True)
class Timeout:
    """Execution timeout constraint."""

    seconds: float = 30.0


# ======================================================================
# Field descriptor
# ======================================================================

_MISSING = object()


class DeclarativeField:
    """Metadata about a single field in a DeclarativeSchema."""

    __slots__ = ("name", "type", "default", "_annotations")

    MISSING = _MISSING

    def __init__(
        self,
        name: str,
        type_: Any,
        default: Any = _MISSING,
        annotations: dict[type, Any] | None = None,
    ) -> None:
        self.name = name
        self.type = type_
        self.default = default
        self._annotations: dict[type, Any] = annotations or {}

    @property
    def required(self) -> bool:
        """True if this field has no default value."""
        return self.default is _MISSING

    def get_annotation(self, cls: type) -> Any | None:
        """Return the annotation instance for the given type, or None."""
        return self._annotations.get(cls)

    def has_annotation(self, cls: type) -> bool:
        """True if this field has an annotation of the given type."""
        return cls in self._annotations

    def __repr__(self) -> str:
        parts = [f"name={self.name!r}", f"type={self.type}"]
        if self._annotations:
            parts.append(f"annotations={list(self._annotations.values())}")
        return f"DeclarativeField({', '.join(parts)})"


# ======================================================================
# Metaclass
# ======================================================================


class DeclarativeMetaclass(type):
    """Metaclass that introspects Annotated type hints into field metadata.

    Subclass this metaclass and set ``_schema_base_name`` to the name of your
    schema base class (e.g. "ToolSchema") so the metaclass skips introspection
    for the base class itself.
    """

    _schema_base_name: str = "DeclarativeSchema"

    def __dir__(cls) -> list[str]:
        """Include field names in dir() for IDE/REPL autocomplete."""
        base = list(super().__dir__())
        field_list = getattr(cls, "_field_list", ())
        base.extend(f.name for f in field_list)
        return base

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
        cls = super().__new__(mcs, name, bases, namespace)

        # Skip introspection for the base class itself
        base_names = {mcs._schema_base_name, "DeclarativeSchema"}
        if name in base_names:
            cls._fields = {}
            cls._field_list = ()
            return cls

        # Collect fields from type hints
        fields: dict[str, DeclarativeField] = {}
        try:
            hints = get_type_hints(cls, include_extras=True)
        except Exception:
            hints = getattr(cls, "__annotations__", {})

        for field_name, hint in hints.items():
            if field_name.startswith("_"):
                continue

            field_type = hint
            annotations: dict[type, Any] = {}

            # Extract metadata from Annotated
            if get_origin(hint) is Annotated:
                args = get_args(hint)
                if args:
                    field_type = args[0]
                    for meta in args[1:]:
                        annotations[type(meta)] = meta

            # Check for default value
            default = namespace.get(field_name, _MISSING)

            fields[field_name] = DeclarativeField(
                name=field_name,
                type_=field_type,
                default=default,
                annotations=annotations,
            )

        cls._fields = fields
        cls._field_list = tuple(fields.values())
        return cls


class DeclarativeSchema(metaclass=DeclarativeMetaclass):
    """Base class for all declarative schemas.

    Subclass to create typed declarations with Annotated hints::

        class MySchema(DeclarativeSchema):
            field: Annotated[str, Reads()]
            optional: str = "default"
    """

    _fields: ClassVar[dict[str, DeclarativeField]]
    _field_list: ClassVar[tuple[DeclarativeField, ...]]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f.name for f in self._field_list)})"
