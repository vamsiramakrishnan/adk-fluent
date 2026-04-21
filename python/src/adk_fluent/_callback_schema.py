"""Typed callback declarations for adk-fluent agents.

CallbackSchema declares what state keys the agent's callbacks collectively
read and write, making them visible to the contract checker and .show().

Usage::

    from adk_fluent import CallbackSchema, Reads, Writes

    class AuditCallbacks(CallbackSchema):
        user_tier: Annotated[str, Reads(scope="user")]
        call_count: Annotated[int, Writes(scope="temp")]

    Agent("proc").callback_schema(AuditCallbacks).before_agent(audit_fn)
"""

from __future__ import annotations

from typing import ClassVar

from adk_fluent._schema_base import (
    DeclarativeField,
    DeclarativeMetaclass,
    Reads,
    Writes,
)

__all__ = ["CallbackSchema"]


def _scoped_key(name: str, scope: str) -> str:
    return name if scope == "session" else f"{scope}:{name}"


class CallbackSchemaMetaclass(DeclarativeMetaclass):
    _schema_base_name = "CallbackSchema"


class CallbackSchema(metaclass=CallbackSchemaMetaclass):
    """Base class for typed callback declarations."""

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
