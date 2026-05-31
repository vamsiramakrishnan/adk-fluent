"""The A2UI schema manager.

:class:`A2uiSchemaManager` merges one or more catalog configs (each produced
by a provider's ``get_config(version)``), applies a list of modifiers, and
exposes the resulting selected :class:`~a2ui.schema.types.Catalog` plus a
small set of generated examples used to prime the LLM.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

from a2ui.schema.constants import DEFAULT_VERSION
from a2ui.schema.types import Catalog, CatalogConfig

Modifier = Callable[[dict[str, Any]], dict[str, Any]]


class A2uiSchemaManager:
    """Merge catalog configs + modifiers into a selected catalog.

    Args:
        version: The A2UI protocol version to target.
        configs: One or more :class:`CatalogConfig` fragments to merge. Later
            configs override earlier ones key-by-key (shallow per-section).
        modifiers: Optional list of ``(dict) -> dict`` transforms applied to
            the merged catalog dict, in order.
    """

    def __init__(
        self,
        version: str = DEFAULT_VERSION,
        configs: Sequence[CatalogConfig] | None = None,
        modifiers: Sequence[Modifier] | None = None,
    ) -> None:
        self.version = version
        self._configs: list[CatalogConfig] = list(configs or [])
        self._modifiers: list[Modifier] = list(modifiers or [])
        self._selected: Catalog | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_selected_catalog(self) -> Catalog:
        """Merge configs, apply modifiers, and return the selected catalog.

        The result is cached; repeated calls return the same object.
        """
        if self._selected is not None:
            return self._selected

        merged = self._merge_configs()
        for modifier in self._modifiers:
            merged = modifier(merged)

        catalog_id = merged.get("catalogId") or merged.get("$id") or "a2ui/basic"
        self._selected = Catalog(
            catalog_id=catalog_id,
            version=self.version,
            components=dict(merged.get("components", {})),
            functions=dict(merged.get("functions", {})),
            raw=merged,
        )
        return self._selected

    def load_examples(self, catalog: Catalog, *, validate: bool = True) -> str:
        """Return a string of example A2UI messages for the given catalog.

        Examples prime the LLM with the createSurface / updateComponents
        message shape using components that actually exist in ``catalog``.

        Args:
            catalog: The selected catalog the examples must be consistent with.
            validate: When ``True``, every component referenced by an example
                is checked against ``catalog.components``; an unknown
                component raises ``ValueError``.
        """
        examples = _build_examples(catalog)
        if validate:
            _validate_examples(examples, catalog)
        return json.dumps(examples, indent=2)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _merge_configs(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for cfg in self._configs:
            _deep_merge(merged, cfg.catalog)
            if cfg.catalog_id:
                merged["catalogId"] = cfg.catalog_id
        return merged


def _deep_merge(into: dict[str, Any], src: dict[str, Any]) -> None:
    """Recursively merge ``src`` into ``into`` (mutates ``into``)."""
    for key, value in src.items():
        if key in into and isinstance(into[key], dict) and isinstance(value, dict):
            _deep_merge(into[key], value)
        else:
            into[key] = value


def _build_examples(catalog: Catalog) -> list[dict[str, Any]]:
    """Construct a minimal, catalog-consistent example message stream.

    Picks components that exist in the catalog so the example always
    validates. Falls back gracefully when the basic components are absent.
    """
    version = catalog.version
    names = set(catalog.components)

    components: list[dict[str, Any]] = []
    children: list[str] = []

    if "Text" in names:
        components.append({"component": "Text", "id": "greeting", "text": "Welcome!", "variant": "h2"})
        children.append("greeting")
    if "TextField" in names:
        components.append({"component": "TextField", "id": "name_field", "label": "Your name"})
        children.append("name_field")
    if "Button" in names:
        components.append(
            {
                "component": "Button",
                "id": "submit",
                "child": "Submit",
                "action": {"action": "submit_form"},
            }
        )
        children.append("submit")

    # Root container — prefer Column, then Row, else inline the first component.
    container = "Column" if "Column" in names else ("Row" if "Row" in names else None)
    if container is not None:
        root = {"component": container, "id": "root", "children": children or ["greeting"]}
    elif components:
        root = dict(components[0])
        root["id"] = "root"
        components = components[1:]
    else:
        root = {"component": "Text", "id": "root", "text": "Hello"}

    return [
        {
            "version": version,
            "createSurface": {
                "surfaceId": "example-surface",
                "catalogId": catalog.catalog_id,
            },
        },
        {
            "version": version,
            "updateComponents": {
                "surfaceId": "example-surface",
                "components": [root, *components],
            },
        },
    ]


def _validate_examples(examples: list[dict[str, Any]], catalog: Catalog) -> None:
    known = set(catalog.components)
    if not known:
        return
    for msg in examples:
        update = msg.get("updateComponents")
        if not update:
            continue
        for comp in update.get("components", []):
            kind = comp.get("component")
            if kind is not None and kind not in known:
                raise ValueError(f"example references unknown component {kind!r}; known: {sorted(known)}")


__all__ = ["A2uiSchemaManager"]
