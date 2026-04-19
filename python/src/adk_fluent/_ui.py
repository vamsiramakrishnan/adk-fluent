"""
UI — Agent-to-UI composition namespace (hand-written core).
============================================================
The 9th adk-fluent namespace. Compose declarative agent UIs that emit
A2UI protocol JSON.

This module provides the **foundation types** and **compilation logic**.
Generated component factories live in ``_ui_generated.py`` and are mixed
into the :class:`UI` class via inheritance.

Architecture::

    UIComponent (frozen dataclass)   ─── nested Python tree
         │
         ▼
    compile_surface()                ─── DFS flatten
         │
         ▼
    A2UI JSON messages               ─── createSurface + updateComponents + updateDataModel

Usage::

    from adk_fluent import UI

    surface = UI.surface(
        "contact",
        UI.column(
            UI.text("Hello!", variant="h1"),
            UI.text_field("name", label="Your Name"),
            UI.button("send", label="Send", action="submit"),
        ),
    )

    # Compile to A2UI protocol messages
    messages = surface.compile()
"""

from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Catalog dispatch scope (contextvar)
# ---------------------------------------------------------------------------
#
# ``UI.with_catalog("flux")`` flips a contextvar that the overloaded factory
# methods (``UI.button``, ``UI.text_field``, …) read. A contextvar was chosen
# over a threadlocal or builder attribute for three reasons:
#   1. Surfaces are built inside nested function calls, not on a single
#      builder instance — there is nothing mutable to hang state off of.
#   2. Context managers nest trivially: ``with UI.with_catalog("flux"):``
#      inside another ``with UI.with_catalog("flux"):`` restores the outer
#      value on exit via a reset token. No manual stacking.
#   3. Async-safe: asyncio tasks inherit the parent's contextvar value.
#
# ``"basic"`` is the default and maps to the pre-existing generated factories.
# ``"flux"`` routes to ``_flux_gen.flux_*`` factories and returns dict nodes.

KNOWN_CATALOGS: frozenset[str] = frozenset({"basic", "flux"})

_CURRENT_CATALOG: contextvars.ContextVar[str] = contextvars.ContextVar(
    "adk_fluent._ui._current_catalog", default="basic"
)


def _active_catalog() -> str:
    """Return the currently active catalog name (``"basic"`` by default)."""
    return _CURRENT_CATALOG.get()


# ---------------------------------------------------------------------------
# Theme marker
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _UIThemeMarker:
    """Marker emitted by ``UI.theme(name)``.

    When passed as a positional argument to ``UI.surface(...)`` the marker is
    pulled out and written into ``surface.theme`` as ``{"name": <id>}``. The
    theme id lives at ``createSurface.theme.name`` in the compiled A2UI
    message stream.
    """

    name: str


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UIBinding:
    """Reference to a JSON Pointer path in the A2UI data model.

    Used for one-way reads (``UI.bind("/user/name")``) or two-way
    input binding (``UI.text_field("Name", bind="/form/name")``).
    """

    path: str
    prop: str = "value"
    direction: Literal["read", "write", "two_way"] = "two_way"


@dataclass(frozen=True, slots=True)
class UICheck:
    """A validation rule attached to an input component.

    Maps to A2UI ``CheckRule``: a boolean function call + error message.
    """

    fn: str  # "required", "email", "regex", "length", "numeric"
    args: tuple[tuple[str, Any], ...] = ()
    message: str = ""


@dataclass(frozen=True, slots=True)
class UIAction:
    """An interaction handler — maps to A2UI ``Action``.

    Can be a server-side event or a client-side function call.
    """

    event: str
    context: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class UIComponent:
    """Base component descriptor.

    Components form a nested tree in Python. ``compile_surface()`` flattens
    them to A2UI's flat adjacency list format, assigning stable IDs.
    """

    _kind: str  # "Text", "Button", "Row", etc.
    _id: str | None = None  # Auto-generated if None
    _props: tuple[tuple[str, Any], ...] = ()  # Frozen properties
    _children: tuple[UIComponent, ...] = ()  # Nested children
    _bindings: tuple[UIBinding, ...] = ()  # Data model bindings
    _checks: tuple[UICheck, ...] = ()  # Validation rules
    _action: UIAction | None = None  # Event handler

    # -- Composition operators ---

    def __or__(self, other: UIComponent) -> UIComponent:
        """``a | b`` → ``Row(a, b)``"""
        return _component("Row", _children=(self, other))

    def __rshift__(self, other: UIComponent) -> UIComponent:
        """``a >> b`` → ``Column(a, b)``"""
        return _component("Column", _children=(self, other))

    def __add__(self, other: UIComponent) -> _UIGroup:
        """``a + b`` → sibling group (for passing multiple children)."""
        left = self._as_list() if isinstance(self, _UIGroup) else (self,)
        right = other._as_list() if isinstance(other, _UIGroup) else (other,)
        return _UIGroup(_children=left + right)

    # -- Helpers --

    def _as_list(self) -> tuple[UIComponent, ...]:
        """Unwrap to tuple of components."""
        return (self,)

    def with_id(self, id: str) -> UIComponent:
        """Return copy with explicit ID."""
        return replace(self, _id=id)

    def with_action(self, event: str, **context: Any) -> UIComponent:
        """Return copy with an action handler."""
        return replace(self, _action=UIAction(event, tuple(sorted(context.items()))))

    def with_checks(self, *checks: UICheck) -> UIComponent:
        """Return copy with validation checks."""
        return replace(self, _checks=self._checks + tuple(checks))


@dataclass(frozen=True, slots=True)
class _UIGroup(UIComponent):
    """A virtual group of sibling components (used by + operator)."""

    _kind: str = "__group__"

    def _as_list(self) -> tuple[UIComponent, ...]:
        return self._children


@dataclass(frozen=True, slots=True)
class UISurface:
    """Named A2UI surface — the top-level compilation root.

    A surface has a name, optional catalog, theme, initial data model,
    a root component tree, and event handlers.
    """

    name: str
    root: UIComponent | None = None
    catalog: str = "https://a2ui.org/specification/v0_10/basic_catalog.json"
    theme: tuple[tuple[str, Any], ...] = ()
    data: tuple[tuple[str, Any], ...] = ()
    version: str = "v0.10"
    _handlers: tuple[tuple[str, Callable[..., Any]], ...] = ()

    def with_root(self, root: UIComponent) -> UISurface:
        """Set the root component tree."""
        return replace(self, root=root)

    def with_theme(self, **kw: Any) -> UISurface:
        """Set theme properties."""
        return replace(self, theme=tuple(sorted(kw.items())))

    def with_data(self, **kw: Any) -> UISurface:
        """Set initial data model values."""
        return replace(self, data=tuple(sorted(kw.items())))

    def with_catalog(self, uri: str) -> UISurface:
        """Set catalog URI."""
        return replace(self, catalog=uri)

    def on(self, action: str, handler: Callable[..., Any]) -> UISurface:
        """Register an event handler for a named action."""
        return replace(self, _handlers=self._handlers + ((action, handler),))

    def compile(self) -> list[dict[str, Any]]:
        """Compile to A2UI protocol messages."""
        return compile_surface(self)

    def validate(self) -> UISurface:
        """Statically validate the surface. Raises ``A2UISurfaceError`` on the first issue.

        Checks performed (in order, fail-first — matches the TypeScript port):

        1. Component IDs must be unique across the entire tree.
        2. The root must not be a ``_UIGroup`` — wrap groups in a real container.
        3. Two-way ``UIBinding`` paths must reference declared keys in
           ``surface.data`` (skipped when ``surface.data`` is empty — implicit
           data model is allowed).
        4. If handlers are registered via ``.on(action, fn)``, every component
           ``UIAction.event`` name must appear in the handler set.

        Returns ``self`` to enable fluent chaining.
        """
        from adk_fluent._exceptions import A2UISurfaceError

        if self.root is None:
            return self

        # 1. Walk tree: collect IDs, action events, two-way binding paths.
        seen_ids: set[str] = set()
        action_events: list[str] = []
        two_way_paths: list[str] = []

        def _walk(comp: UIComponent) -> None:
            if isinstance(comp, _UIGroup):
                for child in comp._children:
                    _walk(child)
                return
            cid = comp._id
            if cid is not None:
                if cid in seen_ids:
                    raise A2UISurfaceError(
                        f"duplicate component id '{cid}' in surface tree",
                        surface_name=self.name,
                    )
                seen_ids.add(cid)
            if comp._action is not None:
                action_events.append(comp._action.event)
            for binding in comp._bindings:
                if binding.direction == "two_way":
                    two_way_paths.append(binding.path)
            # Component prop UIBindings
            for _key, value in comp._props:
                if isinstance(value, UIBinding) and value.direction == "two_way":
                    two_way_paths.append(value.path)
            for child in comp._children:
                _walk(child)

        _walk(self.root)

        # 2. Root must not be a virtual group
        if isinstance(self.root, _UIGroup):
            raise A2UISurfaceError(
                "root must be a real component, not a _UIGroup; wrap it in UI.column(...) or UI.row(...)",
                surface_name=self.name,
            )

        # 3. Two-way bindings vs declared data
        if self.data:
            from adk_fluent._exceptions import A2UIBindingError

            declared_paths = {f"/{key}" for key, _ in self.data}
            # Also allow nested paths whose first segment matches a declared key
            declared_roots = {key for key, _ in self.data}
            for path in two_way_paths:
                if path in declared_paths:
                    continue
                # Allow nested: /name/first when /name is declared
                head = path.lstrip("/").split("/", 1)[0]
                if head in declared_roots:
                    continue
                raise A2UIBindingError(
                    f"two-way binding path '{path}' is not declared in surface.data",
                    surface_name=self.name,
                    path=path,
                )

        # 4. Handlers vs actions
        if self._handlers:
            handler_names = {name for name, _ in self._handlers}
            for event in action_events:
                if event not in handler_names:
                    raise A2UISurfaceError(
                        f"Unhandled action '{event}'; surface only registered: {sorted(handler_names)}",
                        surface_name=self.name,
                    )

        return self


class _UIAutoSpec:
    """Marker for LLM-guided mode (schema injection, LLM generates UI)."""

    def __init__(self, catalog: str = "basic", *, _from_flag: bool = False) -> None:
        self.catalog = catalog
        self._from_flag = _from_flag


class _UISchemaSpec:
    """Marker for schema-only prompt injection."""

    def __init__(self, catalog_uri: str | None = None) -> None:
        self.catalog_uri = catalog_uri


# ---------------------------------------------------------------------------
# Internal factory (used by generated code)
# ---------------------------------------------------------------------------


def _component(
    kind: str,
    *,
    id: str | None = None,
    _children: tuple[UIComponent, ...] = (),
    _bindings: tuple[UIBinding, ...] = (),
    _checks: tuple[UICheck, ...] = (),
    _action: UIAction | None = None,
    **props: Any,
) -> UIComponent:
    """Internal factory used by generated component code and hand-written helpers."""
    return UIComponent(
        _kind=kind,
        _id=id,
        _props=tuple(sorted(props.items())),
        _children=_children,
        _bindings=_bindings,
        _checks=_checks,
        _action=_action,
    )


def _flux_node_to_component(node: dict[str, Any]) -> UIComponent:
    """Wrap a ``_flux_gen.flux_*`` dict node as a ``UIComponent``.

    The flux generated factories return plain dicts keyed on ``component`` +
    flux props. This helper lifts them into the ``UIComponent`` tree so flux
    nodes compose with basic-catalog components via the ``|`` / ``>>`` / ``+``
    operators and participate in the standard ``compile_surface`` flatten.
    """
    kind = str(node.get("component", ""))
    comp_id = node.get("id")
    props = {k: v for k, v in node.items() if k not in ("component", "id")}
    return _component(kind, id=comp_id, **props)


# ---------------------------------------------------------------------------
# Compilation: Nested Python → Flat A2UI JSON
# ---------------------------------------------------------------------------


def _make_id(kind: str, counter: dict[str, int]) -> str:
    """Generate a stable, human-readable component ID."""
    key = kind.lower()
    counter[key] = counter.get(key, 0) + 1
    n = counter[key]
    return f"{key}_{n}" if n > 1 else key


def _flatten_tree(
    component: UIComponent,
    counter: dict[str, int],
    flat: list[dict[str, Any]],
    is_root: bool = False,
) -> str:
    """DFS walk: flatten nested tree → A2UI flat component list.

    Returns the assigned ID for the component.
    """
    # Skip virtual groups
    if isinstance(component, _UIGroup):
        # Groups should have been unwrapped by parent; this is a safety net
        if component._children:
            return _flatten_tree(component._children[0], counter, flat)
        return "empty"

    # Assign ID
    comp_id = component._id or ("root" if is_root else _make_id(component._kind, counter))

    # Flatten children first to get their IDs
    child_ids: list[str] = []
    for child in component._children:
        if isinstance(child, _UIGroup):
            for sub in child._as_list():
                child_ids.append(_flatten_tree(sub, counter, flat))
        else:
            child_ids.append(_flatten_tree(child, counter, flat))

    # Build component dict
    comp_dict: dict[str, Any] = {
        "id": comp_id,
        "component": component._kind,
    }

    # Add properties
    for key, value in component._props:
        if isinstance(value, UIBinding):
            comp_dict[key] = {"path": value.path}
        else:
            comp_dict[key] = value

    # Add bindings (value properties pointing to data model)
    for binding in component._bindings:
        comp_dict[binding.prop] = {"path": binding.path}

    # Add children references
    kind = component._kind
    if child_ids:
        if kind in ("Card",) or (kind == "Button" and len(child_ids) == 1):
            comp_dict["child"] = child_ids[0]
        elif kind == "Modal" and len(child_ids) >= 2:
            comp_dict["trigger"] = child_ids[0]
            comp_dict["content"] = child_ids[1]
        elif kind in ("Row", "Column", "List"):
            comp_dict["children"] = child_ids
        # Tabs handled specially — not via children

    # Add action
    if component._action:
        event_dict: dict[str, Any] = {"name": component._action.event}
        if component._action.context:
            event_dict["context"] = dict(component._action.context)
        comp_dict["action"] = {"event": event_dict}

    # Add checks
    if component._checks:
        comp_dict["checks"] = _resolve_checks(component._checks, comp_id)

    flat.append(comp_dict)
    return comp_id


def _resolve_checks(checks: tuple[UICheck, ...], comp_id: str) -> list[dict[str, Any]]:
    """Convert UICheck tuples → A2UI CheckRule format."""
    result = []
    for check in checks:
        rule: dict[str, Any] = {
            "condition": {
                "call": check.fn,
                "args": {"value": {"path": f"/{comp_id}/value"}},
                "returnType": "boolean",
            },
            "message": check.message or f"{check.fn} check failed",
        }
        # Add extra args
        for arg_name, arg_val in check.args:
            rule["condition"]["args"][arg_name] = arg_val
        result.append(rule)
    return result


def compile_surface(surface: UISurface) -> list[dict[str, Any]]:
    """Compile UISurface → list of A2UI protocol messages.

    Returns a list of dicts ready to be serialized as JSON:
    [createSurface, updateComponents, updateDataModel (if data)]
    """
    messages: list[dict[str, Any]] = []

    # 1. createSurface
    create_msg: dict[str, Any] = {
        "version": surface.version,
        "createSurface": {
            "surfaceId": surface.name,
            "catalogId": surface.catalog,
        },
    }
    if surface.theme:
        create_msg["createSurface"]["theme"] = dict(surface.theme)
    messages.append(create_msg)

    # 2. updateComponents (flatten tree)
    if surface.root is not None:
        counter: dict[str, int] = {}
        flat: list[dict[str, Any]] = []
        _flatten_tree(surface.root, counter, flat, is_root=True)
        messages.append(
            {
                "version": surface.version,
                "updateComponents": {
                    "surfaceId": surface.name,
                    "components": flat,
                },
            }
        )

    # 3. updateDataModel (initial data)
    if surface.data:
        for path, value in surface.data:
            messages.append(
                {
                    "version": surface.version,
                    "updateDataModel": {
                        "surfaceId": surface.name,
                        "path": path,
                        "value": value,
                    },
                }
            )

    return messages


# ---------------------------------------------------------------------------
# Schema-driven form helpers
# ---------------------------------------------------------------------------


def _is_pydantic_model(annotation: Any) -> bool:
    """Return True if ``annotation`` is a subclass of ``pydantic.BaseModel``."""
    try:
        from pydantic import BaseModel
    except ImportError:  # pragma: no cover - pydantic is a hard dep
        return False
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def _humanize(name: str) -> str:
    """``snake_case`` → ``"Snake Case"``."""
    return name.replace("_", " ").title()


def _is_email_annotation(ann: Any) -> bool:
    """Detect ``pydantic.EmailStr`` (avoids hard import to keep optional).

    Pydantic's ``EmailStr`` is a string subclass; we accept both identity
    and a name-based fallback to dodge alias rewrites.
    """
    try:
        from pydantic import EmailStr  # type: ignore[import-not-found]

        if ann is EmailStr:
            return True
    except ImportError:  # pragma: no cover
        pass
    return getattr(ann, "__name__", "") == "EmailStr"


def _is_url_annotation(ann: Any) -> bool:
    """Detect ``pydantic.HttpUrl``."""
    try:
        from pydantic import HttpUrl  # type: ignore[import-not-found]

        if ann is HttpUrl:
            return True
    except ImportError:  # pragma: no cover
        pass
    return getattr(ann, "__name__", "") == "HttpUrl"


def _unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """If ``annotation`` is ``Optional[X]`` (``X | None``) return (X, True)."""
    import typing

    origin = typing.get_origin(annotation)
    if origin is typing.Union or (origin is not None and getattr(origin, "__name__", "") == "UnionType"):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(args) == 1 and len(typing.get_args(annotation)) > len(args):
            return args[0], True
    return annotation, False


def _literal_choices(annotation: Any) -> list[Any] | None:
    """Return Literal choices, or None if ``annotation`` is not a Literal."""
    import typing

    if typing.get_origin(annotation) is typing.Literal:
        return list(typing.get_args(annotation))
    return None


def _list_literal_choices(annotation: Any) -> list[Any] | None:
    """Return Literal choices for ``list[Literal[...]]``-shaped annotations."""
    import typing

    origin = typing.get_origin(annotation)
    if origin not in (list, tuple, set, frozenset):
        return None
    args = typing.get_args(annotation)
    if not args:
        return None
    inner = args[0]
    return _literal_choices(inner)


def _checks_from_metadata(field_info: Any, *, allow_required: bool) -> tuple[UICheck, ...]:
    """Translate Pydantic ``FieldInfo`` constraints into ``UICheck`` rules."""
    from adk_fluent._ui_generated import _GeneratedFactories as _GF

    checks: list[UICheck] = []
    if allow_required and field_info.is_required():
        checks.append(_GF.required())

    min_len: int | None = None
    max_len: int | None = None
    pattern: str | None = None
    num_min: float | None = None
    num_max: float | None = None

    for meta in getattr(field_info, "metadata", ()) or ():
        meta_cls = type(meta).__name__
        if meta_cls in ("MinLen", "MinLength"):
            min_len = getattr(meta, "min_length", getattr(meta, "min_value", None))
        elif meta_cls in ("MaxLen", "MaxLength"):
            max_len = getattr(meta, "max_length", getattr(meta, "max_value", None))
        elif meta_cls in ("Pattern", "_PydanticGeneralMetadata") and getattr(meta, "pattern", None) is not None:
            pattern = meta.pattern
        elif meta_cls == "Ge":
            num_min = meta.ge
        elif meta_cls == "Gt":
            num_min = meta.gt
        elif meta_cls == "Le":
            num_max = meta.le
        elif meta_cls == "Lt":
            num_max = meta.lt

    # Check for Field(min_length=, max_length=, pattern=) – exposed via FieldInfo
    fi_min = getattr(field_info, "min_length", None)
    fi_max = getattr(field_info, "max_length", None)
    fi_pattern = getattr(field_info, "pattern", None)
    if min_len is None and fi_min is not None:
        min_len = fi_min
    if max_len is None and fi_max is not None:
        max_len = fi_max
    if pattern is None and fi_pattern is not None:
        pattern = fi_pattern

    if min_len is not None or max_len is not None:
        checks.append(_GF.length(min=min_len, max=max_len))
    if pattern is not None:
        checks.append(_GF.regex(pattern))
    if num_min is not None or num_max is not None:
        checks.append(_GF.numeric(min=num_min, max=num_max))

    return tuple(checks)


def _component_for_field(name: str, field_info: Any) -> list[UIComponent]:
    """Map one Pydantic field → one or more components.

    Returns a list because a description may emit a sibling caption ``Text``.
    """
    import warnings

    from adk_fluent._ui_generated import _GeneratedFactories as _GF

    annotation, is_optional = _unwrap_optional(field_info.annotation)
    label = field_info.title or _humanize(name)
    binding = UIBinding(path=f"/{name}")

    components: list[UIComponent] = []
    description = getattr(field_info, "description", None)
    if description:
        components.append(_component("Text", text=description, variant="caption"))

    # Literal[...] → ChoicePicker
    choices = _literal_choices(annotation)
    if choices is not None:
        options = [{"label": str(c), "value": c} for c in choices]
        checks = _checks_from_metadata(field_info, allow_required=not is_optional)
        components.append(
            _component(
                "ChoicePicker",
                id=name,
                label=label,
                options=options,
                value=None,
                _bindings=(binding,),
                _checks=checks,
            )
        )
        return components

    # list[Literal[...]] → multi ChoicePicker
    multi = _list_literal_choices(annotation)
    if multi is not None:
        options = [{"label": str(c), "value": c} for c in multi]
        checks = _checks_from_metadata(field_info, allow_required=not is_optional)
        components.append(
            _component(
                "ChoicePicker",
                id=name,
                label=label,
                options=options,
                value=[],
                _bindings=(binding,),
                _checks=checks,
                variant="multi",
            )
        )
        return components

    # bool → CheckBox
    if annotation is bool:
        components.append(
            _component(
                "CheckBox",
                id=name,
                label=label,
                value=False,
                _bindings=(binding,),
            )
        )
        return components

    # Numeric → number TextField
    if annotation in (int, float):
        checks = _checks_from_metadata(field_info, allow_required=not is_optional)
        components.append(
            _component(
                "TextField",
                id=name,
                label=label,
                variant="number",
                _bindings=(binding,),
                _checks=checks,
            )
        )
        return components

    # date / datetime → DateTimeInput
    import datetime as _dt

    if annotation is _dt.date:
        components.append(
            _component(
                "DateTimeInput",
                id=name,
                label=label,
                enableDate=True,
                _bindings=(binding,),
            )
        )
        return components
    if annotation is _dt.datetime:
        components.append(
            _component(
                "DateTimeInput",
                id=name,
                label=label,
                enableDate=True,
                enableTime=True,
                _bindings=(binding,),
            )
        )
        return components

    # EmailStr / HttpUrl → TextField + check
    if _is_email_annotation(annotation):
        checks = (_GF.email(),) + _checks_from_metadata(field_info, allow_required=not is_optional)
        components.append(
            _component(
                "TextField",
                id=name,
                label=label,
                variant="shortText",
                _bindings=(binding,),
                _checks=checks,
            )
        )
        return components
    if _is_url_annotation(annotation):
        checks = (_GF.regex(r"^https?://", msg="Must be a URL"),) + _checks_from_metadata(
            field_info, allow_required=not is_optional
        )
        components.append(
            _component(
                "TextField",
                id=name,
                label=label,
                variant="shortText",
                _bindings=(binding,),
                _checks=checks,
            )
        )
        return components

    # str → shortText TextField
    if annotation is str:
        checks = _checks_from_metadata(field_info, allow_required=not is_optional)
        components.append(
            _component(
                "TextField",
                id=name,
                label=label,
                variant="shortText",
                _bindings=(binding,),
                _checks=checks,
            )
        )
        return components

    # Fallback
    warnings.warn(
        f"UI.form: unsupported annotation {annotation!r} for field {name!r}; defaulting to a shortText TextField",
        RuntimeWarning,
        stacklevel=4,
    )
    checks = _checks_from_metadata(field_info, allow_required=not is_optional)
    components.append(
        _component(
            "TextField",
            id=name,
            label=label,
            variant="shortText",
            _bindings=(binding,),
            _checks=checks,
        )
    )
    return components


def _form_from_schema(
    schema: Any,
    *,
    title: str | None,
    submit: str,
    submit_action: str,
) -> UISurface:
    """Build a ``UISurface`` from a Pydantic v2 model class."""
    if not _is_pydantic_model(schema):  # pragma: no cover - guarded by caller
        from adk_fluent._exceptions import A2UIError

        raise A2UIError(f"{schema!r} is not a Pydantic BaseModel subclass")

    surface_title = title or schema.__name__
    children: list[UIComponent] = [_component("Text", text=surface_title, variant="h1")]

    for field_name, field_info in schema.model_fields.items():
        children.extend(_component_for_field(field_name, field_info))

    btn_label = _component("Text", id="submit_label", text=submit)
    children.append(
        _component(
            "Button",
            id="submit_btn",
            variant="primary",
            _children=(btn_label,),
            _action=UIAction(event=submit_action),
        )
    )

    root = _component("Column", _children=tuple(children))
    return UISurface(name=surface_title.lower().replace(" ", "_"), root=root)


def _form_from_fields(
    title: str,
    *,
    fields: dict[str, str | list[str]],
    submit: str,
    submit_action: str,
) -> UISurface:
    """Legacy ``UI.form(title, fields=...)`` path (preserved verbatim)."""
    children: list[UIComponent] = [_component("Text", text=title, variant="h1")]

    for field_name, field_type in fields.items():
        label = field_name.replace("_", " ").title()
        if isinstance(field_type, list):
            options = [{"label": v, "value": v} for v in field_type]
            children.append(
                _component(
                    "ChoicePicker",
                    id=field_name,
                    label=label,
                    options=options,
                    value=[],
                )
            )
        elif field_type == "email":
            children.append(
                _component(
                    "TextField",
                    id=field_name,
                    label=label,
                    variant="shortText",
                    _checks=(UICheck(fn="email", message="Invalid email"),),
                    _bindings=(UIBinding(path=f"/{field_name}"),),
                )
            )
        elif field_type == "longText":
            children.append(
                _component(
                    "TextField",
                    id=field_name,
                    label=label,
                    variant="longText",
                    _bindings=(UIBinding(path=f"/{field_name}"),),
                )
            )
        elif field_type == "number":
            children.append(
                _component(
                    "TextField",
                    id=field_name,
                    label=label,
                    variant="number",
                    _bindings=(UIBinding(path=f"/{field_name}"),),
                )
            )
        elif field_type == "checkbox":
            children.append(
                _component(
                    "CheckBox",
                    id=field_name,
                    label=label,
                    value=False,
                    _bindings=(UIBinding(path=f"/{field_name}"),),
                )
            )
        else:
            children.append(
                _component(
                    "TextField",
                    id=field_name,
                    label=label,
                    variant="shortText",
                    _bindings=(UIBinding(path=f"/{field_name}"),),
                )
            )

    btn_label = _component("Text", id="submit_label", text=submit)
    children.append(
        _component(
            "Button",
            id="submit_btn",
            variant="primary",
            _children=(btn_label,),
            _action=UIAction(event=submit_action),
        )
    )

    root = _component("Column", _children=tuple(children))
    return UISurface(name=title.lower().replace(" ", "_"), root=root)


# ---------------------------------------------------------------------------
# UI.paths(Schema) reflective binding proxy
# ---------------------------------------------------------------------------


class _UIPaths:
    """Reflective binding proxy for a Pydantic schema.

    ``UI.paths(Schema).field_name`` → ``UIBinding(path="/field_name")``.
    Nested ``BaseModel`` annotations return a sub-proxy with the parent
    field name as the path prefix. Typo'd attributes raise ``AttributeError``
    listing the available fields.
    """

    __slots__ = ("_schema", "_prefix", "_field_names")

    def __init__(self, schema: Any, *, _prefix: str = "") -> None:
        if not _is_pydantic_model(schema):
            from adk_fluent._exceptions import A2UIError

            raise A2UIError(f"UI.paths expects a Pydantic BaseModel subclass, got {schema!r}")
        object.__setattr__(self, "_schema", schema)
        object.__setattr__(self, "_prefix", _prefix.rstrip("/"))
        object.__setattr__(self, "_field_names", tuple(schema.model_fields.keys()))

    def __getattr__(self, name: str) -> Any:
        # Dunder fast-path: don't intercept Python internals.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        fields = self._field_names
        if name not in fields:
            available = sorted(fields)
            raise AttributeError(f"{self._schema.__name__!r} has no field {name!r}. Available fields: {available}")
        field_info = self._schema.model_fields[name]
        annotation = field_info.annotation
        # Unwrap Optional[X]
        annotation, _ = _unwrap_optional(annotation)
        path = f"{self._prefix}/{name}"
        if _is_pydantic_model(annotation):
            return _UIPaths(annotation, _prefix=path)
        return UIBinding(path=path)

    def __dir__(self) -> list[str]:
        return list(self._field_names)

    def __repr__(self) -> str:
        return f"<UI.paths({self._schema.__name__}, prefix={self._prefix!r})>"


# ---------------------------------------------------------------------------
# The UI class — imports generated factories at bottom of file
# ---------------------------------------------------------------------------


class UI:
    """The 9th adk-fluent namespace. Compose declarative agent UIs.

    Generated component factories (``text``, ``button``, ``row``, etc.)
    are mixed in from ``_ui_generated.py``. Hand-written methods below
    handle surface lifecycle, data binding, and LLM-guided mode.

    Usage::

        from adk_fluent import UI

        surface = UI.surface("contact",
            UI.column(
                UI.text("Hello!", variant="h1"),
                UI.text_field("name", label="Your Name"),
                UI.button("send", label="Send", action="submit"),
            ),
        )
    """

    # --- Data binding ---

    @staticmethod
    def bind(path: str, *, direction: str = "two_way") -> UIBinding:
        """Create a data binding to a JSON Pointer path.

        Args:
            path: JSON Pointer (e.g., ``"/user/name"``).
            direction: ``"read"``, ``"write"``, or ``"two_way"``.
        """
        return UIBinding(path=path, direction=direction)  # type: ignore[arg-type]

    @staticmethod
    def fmt(template: str) -> dict[str, Any]:
        """Format string with ``${/path}`` interpolation.

        Returns A2UI ``formatString`` function call dict::

            UI.fmt("Hello ${/user/name}!")
            # → {"call": "formatString", "args": {"value": template}, "returnType": "string"}
        """
        return {
            "call": "formatString",
            "args": {"value": template},
            "returnType": "string",
        }

    # --- Surface lifecycle ---

    @staticmethod
    def surface(name: str, *items: Any, **kw: Any) -> UISurface:
        """Create a named UI surface.

        Accepts positional items in any order: at most one ``UIComponent`` root
        plus any number of ``UI.theme(...)`` markers. When a theme marker is
        present its id lives at ``createSurface.theme.name`` in the compiled
        A2UI message stream.

        Args:
            name: Unique surface identifier.
            *items: Root component tree and/or theme markers.
            **kw: Additional surface options (catalog, theme, data).
        """
        catalog = kw.pop("catalog", "https://a2ui.org/specification/v0_10/basic_catalog.json")
        theme = kw.pop("theme", None)
        data = kw.pop("data", None)

        root: UIComponent | None = None
        theme_markers: list[_UIThemeMarker] = []
        for item in items:
            if isinstance(item, _UIThemeMarker):
                theme_markers.append(item)
            elif isinstance(item, UIComponent):
                if root is not None:
                    from adk_fluent._exceptions import A2UIError

                    raise A2UIError(
                        f"UI.surface({name!r}) received multiple root components; "
                        "wrap them in UI.column(...) or UI.row(...) instead."
                    )
                root = item
            elif item is None:
                continue
            else:
                from adk_fluent._exceptions import A2UIError

                raise A2UIError(
                    f"UI.surface({name!r}) received unexpected positional argument {item!r}; "
                    "expected a UIComponent or UI.theme(...) marker."
                )

        s = UISurface(name=name, root=root, catalog=catalog)
        if theme_markers:
            # Last wins; merge with explicit ``theme=`` kwarg if any.
            merged = {"name": theme_markers[-1].name}
            if theme:
                merged = {**theme, **merged}
            s = s.with_theme(**merged)
        elif theme:
            s = s.with_theme(**theme)
        if data:
            s = s.with_data(**data)
        return s

    # --- Theme + catalog scoping ---

    @staticmethod
    def theme(name: str) -> _UIThemeMarker:
        """Attach a theme id to a surface.

        Pass as a positional argument to ``UI.surface(name, UI.theme(id), root)``.
        The id is stored on the surface's ``theme`` attribute and lives at
        ``createSurface.theme.name`` in the compiled A2UI JSON.
        """
        return _UIThemeMarker(name=name)

    @staticmethod
    def with_catalog(name: str) -> contextlib.AbstractContextManager[str]:
        """Scope factory dispatch to a named catalog.

        Inside ``with UI.with_catalog("flux"):`` the overloaded factories
        (``UI.button``, ``UI.text_field``, ``UI.badge``, ``UI.progress``,
        ``UI.skeleton``, ``UI.markdown``, ``UI.link``, ``UI.banner``,
        ``UI.card``, ``UI.stack``) dispatch to ``adk_fluent._flux_gen``
        factories and emit ``FluxX`` dict nodes. Outside the block the default
        ``"basic"`` catalog (pre-existing generated factories) is used.

        Nesting is supported; exiting an inner block restores the outer scope.

        Args:
            name: Catalog identifier. Known values: ``"basic"``, ``"flux"``.

        Raises:
            ValueError: If ``name`` is not a known catalog.
        """
        if name not in KNOWN_CATALOGS:
            raise ValueError(f"Unknown catalog {name!r}. Known catalogs: {sorted(KNOWN_CATALOGS)}")

        @contextlib.contextmanager
        def _scope() -> Iterator[str]:
            token = _CURRENT_CATALOG.set(name)
            try:
                yield name
            finally:
                _CURRENT_CATALOG.reset(token)

        return _scope()

    # --- Catalog-overloaded factories ---
    #
    # Each method below is a tight dispatch on the active catalog contextvar:
    # one ``if _active_catalog() == "flux":`` branch dispatching to
    # ``_flux_gen`` (returning a FluxX UIComponent) and otherwise a single
    # fall-through to the existing basic-catalog emitter.

    @staticmethod
    def button(*args: Any, **kwargs: Any) -> UIComponent:
        """Clickable button — dispatches on the active catalog.

        Flux: emits a ``FluxButton`` with ``tone`` × ``size`` × ``emphasis``.
        Basic: falls through to the generated basic-catalog factory with the
        arguments forwarded verbatim.
        """
        if _active_catalog() == "flux":
            from adk_fluent._flux_gen import flux_button

            # Accept either positional label or keyword label for flux.
            label: str | None = None
            if args:
                label = args[0] if isinstance(args[0], str) else None
            label = kwargs.pop("label", label)
            tone = kwargs.pop("tone", "neutral")
            size = kwargs.pop("size", "md")
            emphasis = kwargs.pop("emphasis", "solid")
            action_raw = kwargs.pop("action", None)
            act = action_raw if isinstance(action_raw, dict) else ({"event": action_raw} if action_raw else {})
            acc = kwargs.pop("accessibility", None)
            if acc is None:
                acc = {"label": label or ""}
            comp_id = kwargs.pop("id", None) or "flux_button"
            extra: dict[str, Any] = {}
            for k in ("disabled", "leadingIcon", "loading", "trailingIcon"):
                v = kwargs.pop(k, None)
                if v is not None:
                    extra[k] = v
            if label is not None:
                extra["label"] = label
            # Remaining kwargs are unknown in flux mode; forward as-is so
            # misuse surfaces as a TypeError from flux_button.
            node = flux_button(
                id=comp_id,
                tone=tone,
                size=size,
                emphasis=emphasis,
                action=act,
                accessibility=acc,
                **extra,
                **kwargs,
            )
            return _flux_node_to_component(node)

        from adk_fluent._ui_generated import _GeneratedFactories as _GF

        return _GF.button(*args, **kwargs)

    @staticmethod
    def text_field(*args: Any, **kwargs: Any) -> UIComponent:
        """Text input — dispatches on the active catalog.

        Flux: emits a ``FluxTextField`` with ``type`` × ``size`` × ``state``.
        Basic: falls through to the generated basic-catalog factory with the
        arguments forwarded verbatim.
        """
        if _active_catalog() == "flux":
            from adk_fluent._flux_gen import flux_text_field

            label_positional = args[0] if args and isinstance(args[0], str) else None
            label = kwargs.pop("label", label_positional)
            acc = kwargs.pop("accessibility", None)
            if acc is None:
                acc = {"label": label or ""}
            comp_id = kwargs.pop("id", None) or "flux_text_field"
            ftype = kwargs.pop("type", "text")
            size = kwargs.pop("size", "md")
            state = kwargs.pop("state", "default")
            extra: dict[str, Any] = {}
            for k in (
                "disabled",
                "error",
                "helper",
                "leadingIcon",
                "maxLength",
                "placeholder",
                "readonly",
                "required",
                "trailingIcon",
                "value",
            ):
                v = kwargs.pop(k, None)
                if v is not None:
                    extra[k] = v
            # Basic-only kwargs that have no flux analogue — silently ignore.
            for basic_only in ("variant", "bind", "checks"):
                kwargs.pop(basic_only, None)
            node = flux_text_field(
                id=comp_id,
                type=ftype,
                size=size,
                state=state,
                accessibility=acc,
                **extra,
                **kwargs,
            )
            return _flux_node_to_component(node)

        from adk_fluent._ui_generated import _GeneratedFactories as _GF

        return _GF.text_field(*args, **kwargs)

    @staticmethod
    def badge(
        label: str,
        *,
        tone: str = "neutral",
        variant: str = "subtle",
        size: str = "sm",
        accessibility: dict[str, Any] | None = None,
        id: str | None = None,
    ) -> UIComponent:
        """Compact status label — dispatches on the active catalog.

        Flux: emits a ``FluxBadge``.
        Basic: falls back to a basic-catalog ``Text`` (the declared fallback).
        """
        if _active_catalog() == "flux":
            from adk_fluent._flux_gen import flux_badge

            extra: dict[str, Any] = {}
            if accessibility is not None:
                extra["accessibility"] = accessibility
            node = flux_badge(
                id=id or "flux_badge",
                label=label,
                tone=tone,  # type: ignore[arg-type]
                variant=variant,  # type: ignore[arg-type]
                size=size,  # type: ignore[arg-type]
                **extra,
            )
            return _flux_node_to_component(node)

        return _component("Text", id=id, text=label, variant="caption")

    @staticmethod
    def progress(
        *,
        value: float = 0.0,
        determinate: bool = True,
        tone: str = "default",
        size: str = "md",
        label: str | None = None,
        accessibility: dict[str, Any] | None = None,
        id: str | None = None,
    ) -> UIComponent:
        """Progress indicator — dispatches on the active catalog.

        Flux: emits a ``FluxProgress``.
        Basic: falls back to a basic-catalog ``Slider`` (the declared fallback).
        """
        if _active_catalog() == "flux":
            from adk_fluent._flux_gen import flux_progress

            acc = accessibility if accessibility is not None else {"label": label or "progress"}
            extra: dict[str, Any] = {}
            if label is not None:
                extra["label"] = label
            node = flux_progress(
                id=id or "flux_progress",
                value=value,
                determinate=determinate,
                tone=tone,  # type: ignore[arg-type]
                size=size,  # type: ignore[arg-type]
                accessibility=acc,
                **extra,
            )
            return _flux_node_to_component(node)

        return _component(
            "Slider",
            id=id,
            min=0,
            max=100,
            value=value,
            label=label,
        )

    @staticmethod
    def skeleton(
        *,
        shape: str = "text",
        size: str = "md",
        count: int | None = None,
        width: str | None = None,
        height: str | None = None,
        accessibility: dict[str, Any] | None = None,
        id: str | None = None,
    ) -> UIComponent:
        """Loading placeholder — dispatches on the active catalog.

        Flux: emits a ``FluxSkeleton``.
        Basic: falls back to a basic-catalog ``Text`` placeholder.
        """
        if _active_catalog() == "flux":
            from adk_fluent._flux_gen import flux_skeleton

            extra: dict[str, Any] = {}
            if accessibility is not None:
                extra["accessibility"] = accessibility
            if count is not None:
                extra["count"] = count
            if height is not None:
                extra["height"] = height
            if width is not None:
                extra["width"] = width
            node = flux_skeleton(
                id=id or "flux_skeleton",
                shape=shape,  # type: ignore[arg-type]
                size=size,  # type: ignore[arg-type]
                **extra,
            )
            return _flux_node_to_component(node)

        return _component("Text", id=id, text="Loading…", variant="caption")

    @staticmethod
    def markdown(
        source: str,
        *,
        size: str = "md",
        proseStyle: str = "default",
        accessibility: dict[str, Any] | None = None,
        id: str | None = None,
    ) -> UIComponent:
        """Markdown prose block — dispatches on the active catalog.

        Flux: emits a ``FluxMarkdown``.
        Basic: falls back to a plain basic-catalog ``Text`` (the declared fallback).
        """
        if _active_catalog() == "flux":
            from adk_fluent._flux_gen import flux_markdown

            extra: dict[str, Any] = {}
            if accessibility is not None:
                extra["accessibility"] = accessibility
            node = flux_markdown(
                id=id or "flux_markdown",
                source=source,
                size=size,  # type: ignore[arg-type]
                proseStyle=proseStyle,  # type: ignore[arg-type]
                **extra,
            )
            return _flux_node_to_component(node)

        return _component("Text", id=id, text=source, variant="body")

    @staticmethod
    def link(
        label: str,
        *,
        href: str | None = None,
        action: dict[str, Any] | None = None,
        tone: str = "default",
        underline: str = "hover",
        external: bool | None = None,
        accessibility: dict[str, Any] | None = None,
        id: str | None = None,
    ) -> UIComponent:
        """Inline hyperlink — dispatches on the active catalog.

        Flux: emits a ``FluxLink``. Exactly one of ``href`` / ``action`` should
        be set (enforced by the schema at compile time).
        Basic: falls back to a basic-catalog ``Text``.
        """
        if _active_catalog() == "flux":
            from adk_fluent._flux_gen import flux_link

            extra: dict[str, Any] = {}
            if accessibility is not None:
                extra["accessibility"] = accessibility
            if action is not None:
                extra["action"] = action
            if external is not None:
                extra["external"] = external
            if href is not None:
                extra["href"] = href
            node = flux_link(
                id=id or "flux_link",
                label=label,
                tone=tone,  # type: ignore[arg-type]
                underline=underline,  # type: ignore[arg-type]
                **extra,
            )
            return _flux_node_to_component(node)

        return _component("Text", id=id, text=label, variant="body")

    @staticmethod
    def banner(
        *,
        title: str,
        message: str,
        tone: str = "info",
        action: str | None = None,
        dismiss: str | None = None,
        icon: str | None = None,
        accessibility: dict[str, Any] | None = None,
        id: str | None = None,
    ) -> UIComponent:
        """Inline banner — dispatches on the active catalog.

        Flux: emits a ``FluxBanner``.
        Basic: falls back to a basic-catalog ``Row`` of ``Text`` children.
        """
        if _active_catalog() == "flux":
            from adk_fluent._flux_gen import flux_banner

            extra: dict[str, Any] = {}
            if accessibility is not None:
                extra["accessibility"] = accessibility
            if action is not None:
                extra["action"] = action
            if dismiss is not None:
                extra["dismiss"] = dismiss
            if icon is not None:
                extra["icon"] = icon
            node = flux_banner(
                id=id or "flux_banner",
                title=title,
                message=message,
                tone=tone,  # type: ignore[arg-type]
                **extra,
            )
            return _flux_node_to_component(node)

        return _component(
            "Row",
            id=id,
            _children=(
                _component("Text", text=title, variant="h3"),
                _component("Text", text=message, variant="body"),
            ),
        )

    @staticmethod
    def card(
        *children: UIComponent,
        emphasis: str = "subtle",
        padding: str = "md",
        header: str | None = None,
        body: str | None = None,
        footer: str | None = None,
        accessibility: dict[str, Any] | None = None,
        id: str | None = None,
        child: UIComponent | None = None,
    ) -> UIComponent:
        """Card container — dispatches on the active catalog.

        Flux: emits a ``FluxCard`` with header / body / footer slots.
        Basic: falls through to the generated basic-catalog ``Card`` factory.
        """
        if _active_catalog() == "flux":
            from adk_fluent._flux_gen import flux_card

            # Default body to concatenated text of positional children when not provided.
            body_text = body
            if body_text is None:
                if children and all(isinstance(c, UIComponent) for c in children):
                    parts: list[str] = []
                    for c in children:
                        for key, val in c._props:
                            if key == "text" and isinstance(val, str):
                                parts.append(val)
                    body_text = "\n".join(parts) if parts else ""
                else:
                    body_text = ""
            extra: dict[str, Any] = {}
            if accessibility is not None:
                extra["accessibility"] = accessibility
            if footer is not None:
                extra["footer"] = footer
            if header is not None:
                extra["header"] = header
            node = flux_card(
                id=id or "flux_card",
                emphasis=emphasis,  # type: ignore[arg-type]
                padding=padding,  # type: ignore[arg-type]
                body=body_text,
                **extra,
            )
            return _flux_node_to_component(node)

        from adk_fluent._ui_generated import _GeneratedFactories as _GF

        # Basic catalog takes a single `child`; use the first positional
        # component or the explicit `child=` kwarg.
        chosen_child = child
        if chosen_child is None and children:
            chosen_child = children[0] if len(children) == 1 else _component("Column", _children=children)
        return _GF.card(child=chosen_child, id=id)

    @staticmethod
    def stack(
        *children: UIComponent,
        direction: str = "vertical",
        gap: str = "2",
        align: str = "stretch",
        justify: str = "start",
        wrap: bool | None = None,
        accessibility: dict[str, Any] | None = None,
        id: str | None = None,
    ) -> UIComponent:
        """Stack layout primitive — dispatches on the active catalog.

        Flux: emits a ``FluxStack`` with spacing tokens.
        Basic: falls back to a basic-catalog ``Column`` / ``Row``.
        """
        if _active_catalog() == "flux":
            from adk_fluent._flux_gen import flux_stack

            extra: dict[str, Any] = {}
            if accessibility is not None:
                extra["accessibility"] = accessibility
            if wrap is not None:
                extra["wrap"] = wrap
            node = flux_stack(
                id=id or "flux_stack",
                direction=direction,  # type: ignore[arg-type]
                gap=gap,  # type: ignore[arg-type]
                align=align,  # type: ignore[arg-type]
                justify=justify,  # type: ignore[arg-type]
                **extra,
            )
            comp = _flux_node_to_component(node)
            if children:
                comp = replace(comp, _children=tuple(children))
            return comp

        kind = "Column" if direction == "vertical" else "Row"
        return _component(kind, id=id, justify=justify, align=align, _children=tuple(children))

    # --- Generic escape hatch ---

    @staticmethod
    def component(kind: str, *, id: str | None = None, **props: Any) -> UIComponent:
        """Catalog-agnostic component factory.

        Use for custom catalog components not in the basic catalog::

            UI.component("BarChart", data=UI.bind("/data"), x="date", y="value")
        """
        return _component(kind, id=id, **props)

    # --- LLM-guided mode ---

    @staticmethod
    def auto(catalog: str = "basic") -> _UIAutoSpec:
        """LLM-guided mode: inject catalog schema, let LLM generate UI dynamically."""
        return _UIAutoSpec(catalog)

    @staticmethod
    def schema(catalog_uri: str | None = None) -> _UISchemaSpec:
        """Schema-only prompt injection (no toolset, just instructions)."""
        return _UISchemaSpec(catalog_uri)

    # --- Presets ---

    @staticmethod
    def form(
        schema_or_title: Any,
        *,
        title: str | None = None,
        fields: dict[str, str | list[str]] | None = None,
        submit: str = "Submit",
        submit_action: str = "submit",
    ) -> UISurface:
        """Generate a form surface — either from a Pydantic model or a field dict.

        Two modes:

        - **Schema mode**: ``UI.form(MyPydanticModel)`` reflects ``model_fields``
          and emits typed inputs (``str`` → TextField, ``EmailStr`` →
          TextField+UI.email, ``bool`` → CheckBox, ``int``/``float`` →
          number TextField, ``Literal[...]`` → ChoicePicker, ``Optional[X]``
          drops the implicit ``UI.required()`` check, etc.).

        - **Legacy mode**: ``UI.form("Contact", fields={"name": "text", ...})``
          dispatches to the original behavior — preserved unchanged.

        Args:
            schema_or_title: A ``pydantic.BaseModel`` subclass (schema mode) or
                a string title (legacy mode).
            title: Optional override for the surface title (schema mode only).
            fields: Field specification dict (legacy mode only).
            submit: Submit button label.
            submit_action: Action event name for submit.

        Note:
            In schema mode, Pydantic field aliases are ignored — the JSON
            Pointer path is always ``/<field_name>``.
        """
        # Dispatch
        is_pydantic_class = isinstance(schema_or_title, type)
        if is_pydantic_class:
            try:
                from pydantic import BaseModel

                if not issubclass(schema_or_title, BaseModel):
                    is_pydantic_class = False
            except ImportError:  # pragma: no cover - pydantic is a hard dep
                is_pydantic_class = False

        if is_pydantic_class:
            return _form_from_schema(
                schema_or_title,
                title=title,
                submit=submit,
                submit_action=submit_action,
            )
        if isinstance(schema_or_title, str) and fields is not None:
            return _form_from_fields(
                schema_or_title,
                fields=fields,
                submit=submit,
                submit_action=submit_action,
            )
        from adk_fluent._exceptions import A2UIError

        raise A2UIError("UI.form expects either a Pydantic model or (title=..., fields=...)")

    @staticmethod
    def paths(schema: Any) -> Any:
        """Return a typed proxy for declaring two-way ``UIBinding`` paths.

        Reflects ``schema.model_fields`` (Pydantic v2) and exposes attribute
        access that returns a ``UIBinding`` rooted at ``/<field_name>``.
        Nested ``BaseModel`` annotations return a sub-proxy whose paths are
        prefixed with the parent field name. Typos raise ``AttributeError``
        listing the available fields.

        Example::

            class Profile(BaseModel):
                email: EmailStr
                age: int

            paths = UI.paths(Profile)
            paths.email   # UIBinding(path="/email", direction="two_way")
            paths.age     # UIBinding(path="/age",   direction="two_way")
            paths.nope    # AttributeError: ... available: ['age', 'email']
        """
        return _UIPaths(schema)

    @staticmethod
    def dashboard(
        title: str,
        *,
        cards: list[dict[str, str]],
    ) -> UISurface:
        """Generate a dashboard surface with metric cards.

        Args:
            title: Dashboard title.
            cards: ``[{"title": "Users", "bind": "/stats/users"}, ...]``.
        """
        children: list[UIComponent] = [_component("Text", text=title, variant="h1")]

        card_components: list[UIComponent] = []
        for card_def in cards:
            card_title = card_def.get("title", "")
            bind_path = card_def.get("bind", "")
            card_content = _component(
                "Column",
                _children=(
                    _component("Text", text=card_title, variant="caption"),
                    _component("Text", _bindings=(UIBinding(path=bind_path, prop="text"),), variant="h3"),
                ),
            )
            card_components.append(_component("Card", _children=(card_content,)))

        children.append(_component("Row", _children=tuple(card_components)))
        root = _component("Column", _children=tuple(children))
        return UISurface(name=title.lower().replace(" ", "_"), root=root)

    @staticmethod
    def confirm(
        message: str,
        *,
        yes: str = "Yes",
        no: str = "No",
        yes_action: str = "confirm_yes",
        no_action: str = "confirm_no",
    ) -> UISurface:
        """Generate a confirmation dialog surface."""
        root = _component(
            "Column",
            _children=(
                _component("Text", text=message, variant="body"),
                _component(
                    "Row",
                    _children=(
                        _component(
                            "Button",
                            id="btn_yes",
                            variant="primary",
                            _children=(_component("Text", id="lbl_yes", text=yes),),
                            _action=UIAction(event=yes_action),
                        ),
                        _component(
                            "Button",
                            id="btn_no",
                            variant="default",
                            _children=(_component("Text", id="lbl_no", text=no),),
                            _action=UIAction(event=no_action),
                        ),
                    ),
                ),
            ),
        )
        return UISurface(name="confirm", root=root)

    @staticmethod
    def table(
        columns: list[str],
        *,
        data_bind: str,
    ) -> UISurface:
        """Generate a data table surface.

        Args:
            columns: Column header labels.
            data_bind: JSON Pointer path to the list of row data.
        """
        # Header row
        header_children = tuple(_component("Text", text=col, variant="caption") for col in columns)
        header = _component("Row", id="header", _children=header_children)

        # Data list with template
        root = _component(
            "Column",
            _children=(
                header,
                _component("List", id="data_list", _bindings=(UIBinding(path=data_bind, prop="children"),)),
            ),
        )
        return UISurface(name="table", root=root)

    @staticmethod
    def wizard(
        title: str,
        *,
        steps: list[tuple[str, UIComponent]],
    ) -> UISurface:
        """Generate a multi-step wizard surface using Tabs."""
        tabs_items: list[UIComponent] = []
        for _step_title, step_content in steps:
            # We'll use the content directly; Tabs need special handling in compile
            tabs_items.append(step_content)

        # For simplicity, use a column with all steps
        # Real wizard would use Tabs or conditional visibility
        step_children: list[UIComponent] = [_component("Text", text=title, variant="h1")]
        for step_title, step_content in steps:
            step_children.append(
                _component(
                    "Card",
                    _children=(
                        _component(
                            "Column",
                            _children=(
                                _component("Text", text=step_title, variant="h3"),
                                step_content,
                            ),
                        ),
                    ),
                )
            )

        root = _component("Column", _children=tuple(step_children))
        return UISurface(name=title.lower().replace(" ", "_"), root=root)


# ---------------------------------------------------------------------------
# Late import: mix in generated factories
# ---------------------------------------------------------------------------

try:
    from adk_fluent._ui_generated import _GeneratedFactories

    # Dynamically copy generated static methods onto UI
    for _attr in dir(_GeneratedFactories):
        if not _attr.startswith("_"):
            _method = getattr(_GeneratedFactories, _attr)
            if callable(_method) and not hasattr(UI, _attr):
                setattr(UI, _attr, _method)
except ImportError:
    # Generated file not yet created — UI works without it
    pass
