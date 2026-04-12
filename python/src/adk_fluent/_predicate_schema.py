"""Typed predicate declarations for adk-fluent routing and gates.

PredicateSchema declares what state keys a predicate reads and provides
a structured evaluate() method that receives those keys as arguments.

Usage::

    from adk_fluent import PredicateSchema, Reads

    class QualityGate(PredicateSchema):
        score: Annotated[float, Reads()]
        threshold: Annotated[float, Reads()]

        @staticmethod
        def evaluate(score, threshold) -> bool:
            return score >= threshold

    Route("intent").when(QualityGate, high_agent).otherwise(low_agent)
"""

from __future__ import annotations

from typing import Any, ClassVar

from adk_fluent._schema_base import (
    DeclarativeField,
    DeclarativeMetaclass,
    Reads,
)

__all__ = ["PredicateSchema"]


def _scoped_key(name: str, scope: str) -> str:
    return name if scope == "session" else f"{scope}:{name}"


class PredicateSchemaMetaclass(DeclarativeMetaclass):
    _schema_base_name = "PredicateSchema"

    def __call__(cls, state: dict[str, Any]) -> bool:
        """Make the schema class itself callable: QualityGate(state) -> bool."""
        evaluate = getattr(cls, "evaluate", None)
        if evaluate is None:
            raise TypeError(f"{cls.__name__} must define a static evaluate() method")

        # Extract declared reads keys from state
        kwargs: dict[str, Any] = {}
        for f in cls._field_list:
            r = f.get_annotation(Reads)
            if r is not None:
                full_key = _scoped_key(f.name, r.scope)
                kwargs[f.name] = state.get(full_key)

        return bool(evaluate(**kwargs))


class PredicateSchema(metaclass=PredicateSchemaMetaclass):
    """Base class for typed predicate declarations."""

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

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f.name for f in self._field_list)})"
