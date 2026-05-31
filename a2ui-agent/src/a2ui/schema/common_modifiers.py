"""Catalog config modifiers.

A *modifier* is a callable ``(dict) -> dict`` applied by the
:class:`~a2ui.schema.manager.A2uiSchemaManager` to a merged catalog dict
before it is frozen into a :class:`~a2ui.schema.types.Catalog`. Modifiers let
callers relax or tighten the generated JSON-Schema without forking the catalog.
"""

from __future__ import annotations

from typing import Any

# JSON-Schema keys that enforce closed-world validation. LLM function-calling
# backends frequently reject schemas that contain these (or behave poorly with
# them), so ``remove_strict_validation`` strips them recursively.
_STRICT_KEYS: tuple[str, ...] = (
    "additionalProperties",
    "unevaluatedProperties",
    "additionalItems",
)


def remove_strict_validation(catalog: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``catalog`` with strict-validation keys removed.

    Recursively walks the catalog dict and drops ``additionalProperties``,
    ``unevaluatedProperties`` and ``additionalItems`` wherever they appear.
    This makes the schema permissive — useful when feeding the catalog into a
    constrained-decoding / function-calling backend that does not tolerate
    closed-world JSON Schemas.

    The input is not mutated.
    """
    return _strip(catalog)


def _strip(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in _STRICT_KEYS}
    if isinstance(value, list):
        return [_strip(item) for item in value]
    return value


__all__ = ["remove_strict_validation"]
