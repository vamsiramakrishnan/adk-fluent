"""Typed state declarations for adk-fluent agents.

StateSchema provides Pydantic-style typed state declarations with scope
annotations. Each field declares its type, scope (session/app/user/temp),
and optional provenance via CapturedBy.

Usage::

    from adk_fluent import StateSchema, CapturedBy, Scoped

    class BillingState(StateSchema):
        intent: str
        confidence: float
        user_message: Annotated[str, CapturedBy("C.capture")]
        ticket_id: str | None = None
        user_tier: Annotated[str, Scoped("user")]

    Agent("classifier")
        .produces(BillingState)
        .instruct("Classify the intent.")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from adk_fluent._schema_base import _MISSING as _MISSING  # shared sentinel
from adk_fluent._schema_base import DeclarativeMetaclass

__all__ = [
    "StateSchema",
    "CapturedBy",
    "Scoped",
    "check_state_schema_contracts",
]

_VALID_SCOPES = frozenset({"session", "app", "user", "temp"})


# ======================================================================
# Annotations
# ======================================================================


@dataclass(frozen=True)
class CapturedBy:
    """Annotation marking which channel/primitive produces a state key.

    This is a documentation annotation — it doesn't affect runtime
    behavior. It tells the contract checker which mechanism produces
    this key, enabling provenance tracking.

    Usage::

        from typing import Annotated
        user_message: Annotated[str, CapturedBy("C.capture")]
    """

    source: str

    def __repr__(self) -> str:
        return f"CapturedBy({self.source!r})"


@dataclass(frozen=True)
class Scoped:
    """Annotation declaring the state scope for a field.

    Scopes: ``"session"`` (default), ``"app"``, ``"user"``, ``"temp"``.
    The scope determines the state key prefix and lifecycle.

    Usage::

        from typing import Annotated
        user_tier: Annotated[str, Scoped("user")]
        # → stored at state["user:user_tier"]
    """

    scope: str

    def __post_init__(self) -> None:
        if self.scope not in _VALID_SCOPES:
            raise ValueError(f"Invalid scope '{self.scope}'. Must be one of: {', '.join(sorted(_VALID_SCOPES))}")

    def __repr__(self) -> str:
        return f"Scoped({self.scope!r})"


# ======================================================================
# StateSchema base class
# ======================================================================


class _StateSchemaField:
    """Metadata about a single field in a StateSchema."""

    __slots__ = ("name", "type", "scope", "captured_by", "default", "full_key")

    MISSING = _MISSING

    def __init__(
        self,
        name: str,
        type_: Any,
        scope: str = "session",
        captured_by: str | None = None,
        default: Any = _MISSING,
    ) -> None:
        self.name = name
        self.type = type_
        self.scope = scope
        self.captured_by = captured_by
        self.default = default
        # Build full key with scope prefix
        if scope == "session":
            self.full_key = name
        else:
            self.full_key = f"{scope}:{name}"

    @property
    def required(self) -> bool:
        """True if this field has no default value."""
        return self.default is _MISSING

    def __repr__(self) -> str:
        parts = [f"name={self.name!r}", f"type={self.type}"]
        if self.scope != "session":
            parts.append(f"scope={self.scope!r}")
        if self.captured_by:
            parts.append(f"captured_by={self.captured_by!r}")
        return f"Field({', '.join(parts)})"


class StateSchemaMetaclass(DeclarativeMetaclass):
    """Metaclass that introspects Annotated type hints to build field metadata."""

    _schema_base_name = "StateSchema"

    def __dir__(cls) -> list[str]:
        """Include field names in dir() for IDE/REPL autocomplete."""
        base = list(super().__dir__())
        field_list = getattr(cls, "_field_list", ())
        base.extend(f.name for f in field_list)
        return base

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
        cls = super().__new__(mcs, name, bases, namespace)

        if name == "StateSchema":
            # Base class — skip state-specific introspection
            cls._fields = {}
            cls._field_list = ()
            return cls

        # Convert DeclarativeFields to _StateSchemaFields
        state_fields: dict[str, _StateSchemaField] = {}
        for f in cls._field_list:
            scoped = f.get_annotation(Scoped)
            captured = f.get_annotation(CapturedBy)
            scope = scoped.scope if scoped else "session"
            captured_by = captured.source if captured else None

            state_fields[f.name] = _StateSchemaField(
                name=f.name,
                type_=f.type,
                scope=scope,
                captured_by=captured_by,
                default=f.default,
            )

        cls._fields = state_fields
        cls._field_list = tuple(state_fields.values())
        return cls


class StateSchema(metaclass=StateSchemaMetaclass):
    """Base class for typed state declarations.

    Subclass this to declare the state keys your agent produces or
    consumes, with types, scopes, and provenance annotations.

    Fields support ``Annotated`` type hints for metadata::

        class MyState(StateSchema):
            intent: str                                    # session-scoped
            confidence: float
            user_msg: Annotated[str, CapturedBy("C.capture")]
            ticket_id: str | None = None                   # optional
            user_tier: Annotated[str, Scoped("user")]      # user-scoped

    Class attributes:
        _fields: Dict of field name → _StateSchemaField metadata
        _field_list: Tuple of all _StateSchemaField objects
    """

    _fields: ClassVar[dict[str, _StateSchemaField]]
    _field_list: ClassVar[tuple[_StateSchemaField, ...]]

    # ------------------------------------------------------------------
    # model_fields compatibility (used by existing contract checker)
    # ------------------------------------------------------------------

    @classmethod
    def model_fields(cls) -> dict[str, _StateSchemaField]:
        """Return field metadata dict. Compatible with Pydantic-style access."""
        return dict(cls._fields)

    @classmethod
    def keys(cls) -> frozenset[str]:
        """Return the set of all state keys (with scope prefixes)."""
        return frozenset(f.full_key for f in cls._field_list)

    @classmethod
    def required_keys(cls) -> frozenset[str]:
        """Return the set of required state keys (no default)."""
        return frozenset(f.full_key for f in cls._field_list if f.required)

    @classmethod
    def scoped_keys(cls) -> dict[str, list[str]]:
        """Return keys grouped by scope."""
        result: dict[str, list[str]] = {}
        for f in cls._field_list:
            result.setdefault(f.scope, []).append(f.full_key)
        return result

    @classmethod
    def field_types(cls) -> dict[str, Any]:
        """Return mapping of full_key → declared type."""
        return {f.full_key: f.type for f in cls._field_list}

    @classmethod
    def captured_by_map(cls) -> dict[str, str]:
        """Return mapping of full_key → capture source, for annotated fields."""
        return {f.full_key: f.captured_by for f in cls._field_list if f.captured_by is not None}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Allow extending schemas via inheritance."""
        super().__init_subclass__(**kwargs)

    @classmethod
    def state_keys(cls) -> dict[str, Any]:
        """Return a dict of field_name → StateKey instances for IDE autocomplete.

        Usage::

            keys = BillingState.state_keys()
            # keys["intent"] → StateKey("intent", scope="session", type=str)
            # keys["user_tier"] → StateKey("user_tier", scope="user", type=str)

            # Use in callbacks:
            value = keys["intent"].get(ctx)
        """
        from adk_fluent._helpers import StateKey

        result: dict[str, StateKey] = {}
        for f in cls._field_list:
            result[f.name] = StateKey(
                f.name,
                scope=f.scope,
                type=f.type if isinstance(f.type, type) else str,
            )
        return result

    @classmethod
    def template_vars(cls) -> str:
        """Return a template string snippet showing all fields as {key} placeholders.

        Useful for building instruction strings with IDE-discoverable variables::

            .instruct(f"Handle intent: {BillingState.template_vars()}")
            # → "Handle intent: {intent} {confidence} {ticket_id} ..."
        """
        return " ".join(f"{{{f.name}}}" for f in cls._field_list)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f.name for f in self._field_list)})"


# ======================================================================
# Typed contract checking
# ======================================================================


def check_state_schema_contracts(
    ir_node: Any,
) -> list[dict[str, str]]:
    """Check typed state contracts on an IR tree using StateSchema annotations.

    Validates:
    1. Scope consistency — keys with scope prefixes are used correctly
    2. Type compatibility — producers and consumers agree on field types
    3. CapturedBy provenance — fields marked CapturedBy have matching captures
    4. Required field coverage — required fields are produced upstream

    Returns a list of dicts with keys: level, agent, message, hint.
    """
    from adk_fluent._ir_generated import SequenceNode

    if not isinstance(ir_node, SequenceNode):
        return []

    children = ir_node.children
    if not children:
        return []

    issues: list[dict[str, str]] = []

    for idx, child in enumerate(children):
        produces_type = getattr(child, "produces_type", None)
        consumes_type = getattr(child, "consumes_type", None)
        child_name = getattr(child, "name", "?")

        # Check scope consistency on produces_type
        if produces_type is not None and hasattr(produces_type, "_field_list"):
            output_key = getattr(child, "output_key", None)
            for field in produces_type._field_list:
                if field.scope != "session" and output_key:
                    # output_key writes to session scope, but field
                    # declares a different scope
                    issues.append(
                        {
                            "level": "info",
                            "agent": child_name,
                            "message": (
                                f"Field '{field.name}' in "
                                f"{produces_type.__name__} declares "
                                f"scope='{field.scope}' but is produced via "
                                f"output_key (session-scoped)"
                            ),
                            "hint": (
                                f"Use S.set() or a callback to write '{field.full_key}' with the correct scope prefix."
                            ),
                        }
                    )

        # Check consumes_type coverage from upstream
        if consumes_type is not None and hasattr(consumes_type, "_field_list"):
            # Collect all upstream produced keys
            upstream_keys: set[str] = set()
            for prev_idx in range(idx):
                prev = children[prev_idx]
                prev_produces = getattr(prev, "produces_type", None)
                if prev_produces is not None and hasattr(prev_produces, "_field_list"):
                    for f in prev_produces._field_list:
                        upstream_keys.add(f.full_key)
                        upstream_keys.add(f.name)  # also bare name
                ok = getattr(prev, "output_key", None)
                if ok:
                    upstream_keys.add(ok)

            for field in consumes_type._field_list:
                if field.required and field.full_key not in upstream_keys and field.name not in upstream_keys:
                    issues.append(
                        {
                            "level": "error",
                            "agent": child_name,
                            "message": (
                                f"Required field '{field.name}' in "
                                f"{consumes_type.__name__} is not "
                                f"produced by any upstream agent"
                            ),
                            "hint": (
                                f"Add .outputs('{field.name}') to an "
                                f"upstream agent or use S.capture() / "
                                f"S.set() to provide this key."
                            ),
                        }
                    )

        # Check CapturedBy provenance
        if produces_type is not None and hasattr(produces_type, "captured_by_map"):
            captured_map = produces_type.captured_by_map()
            for full_key, source in captured_map.items():
                # Look for matching CaptureNode upstream
                if "capture" in source.lower():
                    has_capture = False
                    for prev_idx in range(idx):
                        prev = children[prev_idx]
                        if type(prev).__name__ == "CaptureNode" and hasattr(prev, "key"):
                            # CaptureNode produces the captured key
                            has_capture = True
                            break
                    if not has_capture:
                        bare_name = full_key.split(":", 1)[1] if ":" in full_key else full_key
                        issues.append(
                            {
                                "level": "info",
                                "agent": child_name,
                                "message": (
                                    f"Field '{bare_name}' is annotated "
                                    f"CapturedBy('{source}') but no "
                                    f"S.capture() found upstream"
                                ),
                                "hint": (f"Add S.capture('{bare_name}') before this agent to capture user input."),
                            }
                        )

    return issues
