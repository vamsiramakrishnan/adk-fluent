"""Catalog schema types for the A2UI protocol.

A *catalog* describes the component vocabulary an A2UI surface may use. It is
modelled as a JSON-Schema-shaped dict (matching the on-the-wire
``basic_catalog.json``) wrapped in light dataclasses so that downstream code
(the schema manager, the send toolset) can introspect components and emit
the LLM-facing schema without re-parsing raw JSON every time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CatalogComponent:
    """A single component definition within a catalog.

    Attributes:
        name: The component identifier (e.g. ``"Text"``, ``"Button"``).
        schema: The raw JSON-Schema dict describing the component's props.
    """

    name: str
    schema: dict[str, Any]

    @property
    def properties(self) -> dict[str, Any]:
        """Best-effort extraction of the component's property schema.

        Components in the basic catalog wrap their properties inside an
        ``allOf`` list; this flattens the property blocks into one dict.
        """
        props: dict[str, Any] = {}
        if "properties" in self.schema:
            props.update(self.schema["properties"])
        for part in self.schema.get("allOf", []):
            if isinstance(part, dict) and "properties" in part:
                props.update(part["properties"])
        return props


@dataclass(frozen=True, slots=True)
class Catalog:
    """A resolved, selected catalog.

    Attributes:
        catalog_id: Stable identifier (URI) for the catalog.
        version: The A2UI protocol version this catalog targets.
        components: Mapping of component name -> raw schema dict.
        functions: Mapping of function name -> raw schema dict.
        raw: The complete merged catalog dict (JSON-Schema shaped).
    """

    catalog_id: str
    version: str
    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    functions: dict[str, dict[str, Any]] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def component(self, name: str) -> CatalogComponent:
        """Return the named component, raising ``KeyError`` if absent."""
        return CatalogComponent(name=name, schema=self.components[name])

    def component_names(self) -> tuple[str, ...]:
        """Return all component names, sorted for deterministic output."""
        return tuple(sorted(self.components))

    def to_dict(self) -> dict[str, Any]:
        """Return the full JSON-serialisable catalog dict."""
        return dict(self.raw)


@dataclass(frozen=True, slots=True)
class CatalogConfig:
    """A catalog configuration produced by a provider's ``get_config()``.

    A config is an un-merged catalog fragment plus the version it targets.
    The :class:`A2uiSchemaManager` merges one or more configs and applies
    modifiers to produce the final selected :class:`Catalog`.

    Attributes:
        version: Target protocol version.
        catalog: The raw catalog dict (JSON-Schema shaped) for this config.
        catalog_id: Optional override for the catalog id.
    """

    version: str
    catalog: dict[str, Any]
    catalog_id: str | None = None


__all__ = ["Catalog", "CatalogComponent", "CatalogConfig"]
