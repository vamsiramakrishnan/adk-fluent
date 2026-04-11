"""Field policy engine — determine how each field maps to builder methods.

Policies:
  - skip: field not exposed (private, pydantic internals, parent refs)
  - additive: callback fields that accumulate with multiple calls
  - list_extend: list fields that extend with multiple calls
  - normal: single-value setter methods
"""

from __future__ import annotations

_ALWAYS_SKIP = frozenset(
    {
        "parent_agent",
        "model_config",
        "model_fields",
        "model_computed_fields",
        "model_post_init",
    }
)

_LIST_EXTEND_FIELDS = frozenset({"tools", "sub_agents", "plugins"})

_PRIMITIVE_TYPES = frozenset({"str", "int", "float", "bool", "bytes"})

_PYDANTIC_INTERNALS = frozenset({"model_config", "model_fields", "model_computed_fields", "model_post_init"})


def is_parent_reference(field_name: str, type_str: str, mro_chain: list[str]) -> bool:
    """Detect if a field is a parent/back-reference by checking if its type
    appears in the class's MRO and the field name suggests parentage."""
    parent_indicators = {"parent", "owner", "container"}
    has_parent_name = any(ind in field_name for ind in parent_indicators)
    if not has_parent_name:
        return False
    # Check if the field type references a class in the MRO
    return any(cls_name in type_str for cls_name in mro_chain)


def _unwrap_optional(type_str: str) -> str:
    """Unwrap ``Union[X, NoneType]``, ``Optional[X]``, and ``X | None`` to just ``X``.

    If *type_str* is not an optional wrapper, return it unchanged.
    """
    s = type_str.strip()

    # Union[X, NoneType]
    if s.startswith("Union[") and s.endswith("]"):
        inner = s[len("Union[") : -1]
        parts = [p.strip() for p in inner.split(",")]
        non_none = [p for p in parts if p != "NoneType"]
        if len(non_none) == 1:
            return non_none[0]

    # Optional[X]
    if s.startswith("Optional[") and s.endswith("]"):
        return s[len("Optional[") : -1].strip()

    # X | None  (pipe-union syntax, PEP 604)
    if " | " in s:
        parts = [p.strip() for p in s.split("|")]
        non_none = [p for p in parts if p.strip() != "None"]
        if len(non_none) == 1:
            return non_none[0]

    return s


def _is_list_of_complex_type(type_str: str) -> bool:
    """Return True if *type_str* looks like ``list[SomeComplexType]``.

    Handles ``Union[list[X], NoneType]``, ``Optional[list[X]]``, and
    ``list[X] | None`` wrappers by unwrapping them first.

    Primitive element types (str, int, float, bool, bytes) are **not**
    considered complex, so ``list[str]`` returns False.
    """
    s = _unwrap_optional(type_str)
    # Match patterns like "list[Foo]", "List[Foo]"
    for prefix in ("list[", "List["):
        if s.startswith(prefix) and s.endswith("]"):
            inner = s[len(prefix) : -1].strip()
            # Inner may be a union like "BaseTool | None"; take the first element
            parts = [p.strip() for p in inner.replace(",", "|").split("|")]
            first = parts[0]
            return first not in _PRIMITIVE_TYPES
    return False


def infer_field_policy(
    field_name: str,
    type_str: str,
    is_callback: bool,
    *,
    is_parent_ref: bool = False,
) -> str:
    """Infer the field policy from type information rather than hard-coded sets.

    Returns one of: "skip", "additive", "list_extend", "normal".

    Rules (checked in priority order):
        1. Private fields (``_`` prefix) -> skip
        2. Pydantic internals -> skip
        3. Parent reference fields -> skip
        4. Callable fields with ``_callback`` in the name -> additive
        5. ``list[ComplexType]`` fields -> list_extend
        6. Everything else -> normal
    """
    # 1. Private fields
    if field_name.startswith("_"):
        return "skip"
    # 2. Pydantic internals
    if field_name in _PYDANTIC_INTERNALS:
        return "skip"
    # 3. Parent reference
    if is_parent_ref:
        return "skip"
    # 4. Callback fields
    if is_callback and "_callback" in field_name:
        return "additive"
    # 5. List of complex type
    if _is_list_of_complex_type(type_str):
        return "list_extend"
    # 6. Default
    return "normal"


def get_field_policy(field_name: str, type_str: str, is_callback: bool) -> str:
    """Determine how a field should be handled in the fluent builder.

    Returns one of: "skip", "additive", "list_extend", "normal".

    .. deprecated:: Use :func:`infer_field_policy` instead.
    """
    # Internal / private fields
    if field_name in _ALWAYS_SKIP or field_name.startswith("_"):
        return "skip"
    # Callback fields with _callback suffix get additive semantics
    if is_callback and "_callback" in field_name:
        return "additive"
    # List fields that should use extend semantics
    if field_name in _LIST_EXTEND_FIELDS:
        return "list_extend"
    return "normal"
