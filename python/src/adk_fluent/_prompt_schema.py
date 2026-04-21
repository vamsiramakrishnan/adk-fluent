"""Typed prompt declarations for adk-fluent agents.

PromptSchema declares what state keys a prompt reads, making them visible
to the contract checker and .show(). Prompts only read state — they
never write it.

Usage::

    from adk_fluent import PromptSchema, Reads

    class TriagePrompt(PromptSchema):
        intent: Annotated[str, Reads()]
        confidence: Annotated[float, Reads()]
        user_tier: Annotated[str, Reads(scope="user")]

    Agent("classifier").prompt_schema(TriagePrompt).instruct("Classify the intent.")
"""

from __future__ import annotations

from typing import ClassVar

from adk_fluent._schema_base import (
    DeclarativeField,
    DeclarativeMetaclass,
    Reads,
)

__all__ = ["PromptSchema"]


def _scoped_key(name: str, scope: str) -> str:
    return name if scope == "session" else f"{scope}:{name}"


class PromptSchemaMetaclass(DeclarativeMetaclass):
    _schema_base_name = "PromptSchema"


class PromptSchema(metaclass=PromptSchemaMetaclass):
    """Base class for typed prompt declarations.

    Declares what state keys a prompt reads. Prompts only read state —
    they never write it.
    """

    _fields: ClassVar[dict[str, DeclarativeField]]
    _field_list: ClassVar[tuple[DeclarativeField, ...]]

    @classmethod
    def reads_keys(cls) -> frozenset[str]:
        """State keys this prompt reads (with scope prefixes)."""
        keys: list[str] = []
        for f in cls._field_list:
            r = f.get_annotation(Reads)
            if r is not None:
                keys.append(_scoped_key(f.name, r.scope))
        return frozenset(keys)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f.name for f in self._field_list)})"
