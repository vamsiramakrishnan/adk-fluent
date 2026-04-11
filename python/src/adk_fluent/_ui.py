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

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    pass


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


@dataclass(frozen=True)
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


class _UIAutoSpec:
    """Marker for LLM-guided mode (schema injection, LLM generates UI)."""

    def __init__(self, catalog: str = "basic") -> None:
        self.catalog = catalog


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
    def surface(name: str, root: UIComponent | None = None, **kw: Any) -> UISurface:
        """Create a named UI surface.

        Args:
            name: Unique surface identifier.
            root: Root component tree (optional, can set later with ``with_root``).
            **kw: Additional surface options (catalog, theme, data).
        """
        catalog = kw.pop("catalog", "https://a2ui.org/specification/v0_10/basic_catalog.json")
        theme = kw.pop("theme", None)
        data = kw.pop("data", None)
        s = UISurface(name=name, root=root, catalog=catalog)
        if theme:
            s = s.with_theme(**theme)
        if data:
            s = s.with_data(**data)
        return s

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
        title: str,
        *,
        fields: dict[str, str | list[str]],
        submit: str = "Submit",
        submit_action: str = "submit",
    ) -> UISurface:
        """Generate a form surface from a field specification.

        Args:
            title: Form title.
            fields: ``{"name": "text", "email": "email", "bio": "longText",
                       "role": ["Admin", "User", "Guest"]}``.
            submit: Submit button label.
            submit_action: Action event name for submit.
        """
        children: list[UIComponent] = [_component("Text", text=title, variant="h1")]

        for field_name, field_type in fields.items():
            label = field_name.replace("_", " ").title()
            if isinstance(field_type, list):
                # Choice picker
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
                # Default: shortText
                children.append(
                    _component(
                        "TextField",
                        id=field_name,
                        label=label,
                        variant="shortText",
                        _bindings=(UIBinding(path=f"/{field_name}"),),
                    )
                )

        # Submit button with a Text child for the label
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
