"""Typed middleware declarations for adk-fluent agents.

MiddlewareSchema declares what state keys an agent's middleware collectively
reads and writes, making them visible to the contract checker and .show().

Usage::

    from adk_fluent import MiddlewareSchema, Reads, Writes

    class TrackingState(MiddlewareSchema):
        request_id: Annotated[str, Reads(scope="app")]
        log_entry: Annotated[str, Writes(scope="temp")]

    class TrackingMiddleware:
        agents = "proc"
        schema = TrackingState

        async def before_agent(self, ctx, agent_name):
            ...
"""

from __future__ import annotations

from typing import ClassVar

from adk_fluent._schema_base import (
    DeclarativeField,
    DeclarativeMetaclass,
    Reads,
    Writes,
)

__all__ = ["MiddlewareSchema"]


def _scoped_key(name: str, scope: str) -> str:
    return name if scope == "session" else f"{scope}:{name}"


class MiddlewareSchemaMetaclass(DeclarativeMetaclass):
    _schema_base_name = "MiddlewareSchema"


class MiddlewareSchema(metaclass=MiddlewareSchemaMetaclass):
    """Base class for typed middleware declarations."""

    _fields: ClassVar[dict[str, DeclarativeField]]
    _field_list: ClassVar[tuple[DeclarativeField, ...]]

    @classmethod
    def reads_keys(cls) -> frozenset[str]:
        keys: list[str] = []
        for f in cls._field_list:
            r = f.get_annotation(Reads)
            if r is not None:
                keys.append(_scoped_key(f.name, r.scope))
        return frozenset(keys)

    @classmethod
    def writes_keys(cls) -> frozenset[str]:
        keys: list[str] = []
        for f in cls._field_list:
            w = f.get_annotation(Writes)
            if w is not None:
                keys.append(_scoped_key(f.name, w.scope))
        return frozenset(keys)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f.name for f in self._field_list)})"
