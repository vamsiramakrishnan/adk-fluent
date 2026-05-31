"""``SendA2uiToClientToolset`` — the ADK toolset for LLM-guided A2UI.

This toolset exposes a single ``send_a2ui_to_client`` tool to the model. When
the model calls it with a list of A2UI components, the toolset assembles the
protocol message stream (``createSurface`` + ``updateComponents``), validates
the components against the active catalog, and records the messages on the
session for the host (the A2A executor or a visual runner) to forward to the
connected client.

The toolset is configured with three *provider callables* that read from the
invocation context's session state — mirroring the A2A executor pattern used
by ``adk_fluent``:

* ``a2ui_enabled(ctx) -> bool`` — gate: is A2UI active for this session?
* ``a2ui_catalog(ctx) -> Catalog`` — the selected component catalog.
* ``a2ui_examples(ctx) -> str`` — example messages to prime the model.

When ``a2ui_enabled`` returns ``False`` the toolset exposes no tools, so the
model never sees the A2UI surface for sessions where it is not wanted.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext

from a2ui.schema.constants import DEFAULT_VERSION

#: Session-state key under which emitted A2UI message streams are queued.
A2UI_OUTBOX_STATE_KEY = "a2ui:outbox"

EnabledProvider = Callable[[Any], bool]
CatalogProvider = Callable[[Any], Any]
ExamplesProvider = Callable[[Any], str]


def _default_enabled(_ctx: Any) -> bool:
    return True


def _default_examples(_ctx: Any) -> str:
    return ""


class SendA2uiToClientToolset(BaseToolset):
    """ADK toolset exposing the ``send_a2ui_to_client`` tool.

    Args:
        a2ui_enabled: Callable ``(ctx) -> bool`` deciding whether the tool is
            offered for the current context. Defaults to always-enabled.
        a2ui_catalog: Callable ``(ctx) -> Catalog`` returning the selected
            catalog used to validate emitted components.
        a2ui_examples: Callable ``(ctx) -> str`` returning example messages
            embedded in the tool description to prime the model.
    """

    def __init__(
        self,
        *,
        a2ui_enabled: EnabledProvider | None = None,
        a2ui_catalog: CatalogProvider | None = None,
        a2ui_examples: ExamplesProvider | None = None,
    ) -> None:
        super().__init__()
        self._enabled = a2ui_enabled or _default_enabled
        self._catalog = a2ui_catalog
        self._examples = a2ui_examples or _default_examples

    # ------------------------------------------------------------------
    # BaseToolset API
    # ------------------------------------------------------------------

    async def get_tools(self, readonly_context: ReadonlyContext | None = None) -> list[BaseTool]:
        """Return the ``send_a2ui_to_client`` tool when A2UI is enabled."""
        if readonly_context is not None and not self._enabled(readonly_context):
            return []
        return [FunctionTool(func=self._make_send_tool(readonly_context))]

    async def close(self) -> None:  # pragma: no cover - nothing to release
        """No-op: this toolset holds no external resources."""

    # ------------------------------------------------------------------
    # Tool construction
    # ------------------------------------------------------------------

    def _make_send_tool(self, ro_ctx: ReadonlyContext | None) -> Callable[..., Any]:
        catalog = self._resolve_catalog(ro_ctx)
        examples = self._examples(ro_ctx) if ro_ctx is not None else ""
        component_names = catalog.component_names() if catalog is not None else ()
        toolset = self

        def send_a2ui_to_client(
            components: list[dict[str, Any]],
            tool_context: ToolContext,
            surface_id: str = "main",
        ) -> dict[str, Any]:
            """Render a UI surface on the connected client.

            Send a list of A2UI components to the client to display a rich
            user interface. Exactly one component MUST have ``id`` set to
            ``"root"`` to serve as the tree root.

            Args:
                components: A list of A2UI component objects. Each must include
                    a ``"component"`` type and an ``"id"``.
                surface_id: Identifier for the surface to create/update.

            Returns:
                A status dict describing the queued message stream.
            """
            return toolset._emit(
                components=components,
                surface_id=surface_id,
                tool_context=tool_context,
                catalog=catalog,
            )

        # Enrich the docstring with the live catalog + examples so the model
        # sees the available components and a concrete example.
        doc = [send_a2ui_to_client.__doc__ or ""]
        if component_names:
            doc.append("\nAvailable components: " + ", ".join(component_names) + ".")
        if examples:
            doc.append("\nExample message stream:\n" + examples)
        send_a2ui_to_client.__doc__ = "".join(doc)
        return send_a2ui_to_client

    # ------------------------------------------------------------------
    # Emission + validation
    # ------------------------------------------------------------------

    def _resolve_catalog(self, ro_ctx: ReadonlyContext | None) -> Any:
        if self._catalog is None or ro_ctx is None:
            return None
        try:
            return self._catalog(ro_ctx)
        except Exception:  # pragma: no cover - defensive: never break tool listing
            return None

    def _emit(
        self,
        *,
        components: list[dict[str, Any]],
        surface_id: str,
        tool_context: ToolContext,
        catalog: Any,
    ) -> dict[str, Any]:
        version = getattr(catalog, "version", None) or DEFAULT_VERSION
        catalog_id = getattr(catalog, "catalog_id", None) or "a2ui/basic"

        errors = _validate_components(components, catalog)
        if errors:
            return {"status": "error", "errors": errors}

        messages = [
            {
                "version": version,
                "createSurface": {"surfaceId": surface_id, "catalogId": catalog_id},
            },
            {
                "version": version,
                "updateComponents": {"surfaceId": surface_id, "components": components},
            },
        ]

        # Queue onto session state for the host to forward to the client.
        outbox = list(tool_context.state.get(A2UI_OUTBOX_STATE_KEY, []))
        outbox.extend(messages)
        tool_context.state[A2UI_OUTBOX_STATE_KEY] = outbox

        return {
            "status": "ok",
            "surface_id": surface_id,
            "messages": messages,
            "component_count": len(components),
        }


def _validate_components(components: list[dict[str, Any]], catalog: Any) -> list[str]:
    """Return a list of human-readable validation errors (empty if valid)."""
    errors: list[str] = []
    if not isinstance(components, list) or not components:
        return ["'components' must be a non-empty list of component objects"]

    ids = [c.get("id") for c in components if isinstance(c, dict)]
    if "root" not in ids:
        errors.append("exactly one component must have id == 'root'")

    known = set(getattr(catalog, "components", {}) or {})
    for comp in components:
        if not isinstance(comp, dict):
            errors.append(f"component entries must be objects, got {type(comp).__name__}")
            continue
        kind = comp.get("component")
        if kind is None:
            errors.append("each component must declare a 'component' type")
        elif known and kind not in known:
            errors.append(f"unknown component {kind!r}; known: {sorted(known)}")
    return errors


__all__ = ["SendA2uiToClientToolset", "A2UI_OUTBOX_STATE_KEY"]
