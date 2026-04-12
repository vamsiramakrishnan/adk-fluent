"""Typed tool declarations for adk-fluent agents.

ToolSchema provides typed declarations of what state keys a tool reads
and writes, along with parameter, confirmation, and timeout metadata.

Usage::

    from adk_fluent import ToolSchema, Reads, Writes, Param

    class SearchTools(ToolSchema):
        query: Annotated[str, Reads()]
        user_tier: Annotated[str, Reads(scope="user")]
        results: Annotated[list, Writes()]
        max_results: Annotated[int, Param()] = 10

    Agent("search").tool_schema(SearchTools).instruct("Search")
"""

from __future__ import annotations

from typing import ClassVar

from adk_fluent._schema_base import (
    Confirms,
    DeclarativeField,
    DeclarativeMetaclass,
    Param,
    Reads,
    Timeout,
    Writes,
)

__all__ = ["ToolSchema"]


def _scoped_key(name: str, scope: str) -> str:
    return name if scope == "session" else f"{scope}:{name}"


class ToolSchemaMetaclass(DeclarativeMetaclass):
    """Metaclass for ToolSchema — adds reads/writes/param query methods."""

    _schema_base_name = "ToolSchema"


class ToolSchema(metaclass=ToolSchemaMetaclass):
    """Base class for typed tool declarations."""

    _fields: ClassVar[dict[str, DeclarativeField]]
    _field_list: ClassVar[tuple[DeclarativeField, ...]]

    @classmethod
    def reads_keys(cls) -> frozenset[str]:
        """State keys this tool reads (with scope prefixes)."""
        keys: list[str] = []
        for f in cls._field_list:
            r = f.get_annotation(Reads)
            if r is not None:
                keys.append(_scoped_key(f.name, r.scope))
        return frozenset(keys)

    @classmethod
    def writes_keys(cls) -> frozenset[str]:
        """State keys this tool writes (with scope prefixes)."""
        keys: list[str] = []
        for f in cls._field_list:
            w = f.get_annotation(Writes)
            if w is not None:
                keys.append(_scoped_key(f.name, w.scope))
        return frozenset(keys)

    @classmethod
    def param_names(cls) -> frozenset[str]:
        """Tool parameter names (not from state)."""
        return frozenset(f.name for f in cls._field_list if f.has_annotation(Param))

    @classmethod
    def requires_confirmation(cls) -> bool:
        """True if any field has a Confirms annotation."""
        return any(f.has_annotation(Confirms) for f in cls._field_list)

    @classmethod
    def timeout_seconds(cls) -> float | None:
        """Return the timeout in seconds, or None if not set."""
        for f in cls._field_list:
            t = f.get_annotation(Timeout)
            if t is not None:
                return t.seconds
        return None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f.name for f in self._field_list)})"
