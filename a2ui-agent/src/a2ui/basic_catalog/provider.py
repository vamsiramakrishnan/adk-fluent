"""``BasicCatalog`` — provider for the basic A2UI component set.

The basic catalog covers the core component vocabulary shared by every A2UI
client: ``Text``, ``Image``, ``Icon``, ``Video``, ``AudioPlayer``, ``Row``,
``Column``, ``List``, ``Card``, ``Tabs``, ``Modal``, ``Divider``, ``Button``,
``TextField``, ``CheckBox``, ``ChoicePicker``, ``Slider`` and
``DateTimeInput``, plus the standard validation/format functions.

The catalog definition is bundled with the package as
``a2ui/data/basic_catalog.json`` (the canonical A2UI specification document),
so ``BasicCatalog`` works fully offline.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from a2ui.schema.constants import DEFAULT_VERSION
from a2ui.schema.types import CatalogConfig

_CATALOG_RESOURCE = "basic_catalog.json"


@lru_cache(maxsize=1)
def _load_catalog_json() -> dict[str, Any]:
    """Load and cache the bundled basic catalog JSON."""
    data = resources.files("a2ui.data").joinpath(_CATALOG_RESOURCE).read_text(encoding="utf-8")
    return json.loads(data)


class BasicCatalog:
    """Provider for the bundled basic A2UI catalog.

    Usage::

        config = BasicCatalog().get_config(VERSION_0_9)
        mgr = A2uiSchemaManager(VERSION_0_9, [config], [remove_strict_validation])
        catalog = mgr.get_selected_catalog()
    """

    def get_config(self, version: str = DEFAULT_VERSION) -> CatalogConfig:
        """Return a :class:`CatalogConfig` for the requested protocol version.

        Args:
            version: The A2UI protocol version to target. The bundled catalog
                definition is version-agnostic at the component level; the
                version is stamped onto the resulting config so the schema
                manager and send toolset emit the correct wire ``version``.
        """
        raw = _load_catalog_json()
        catalog = {
            "catalogId": raw.get("catalogId", "https://a2ui.org/specification/basic_catalog.json"),
            "components": dict(raw.get("components", {})),
            "functions": dict(raw.get("functions", {})),
        }
        if "$defs" in raw:
            catalog["$defs"] = dict(raw["$defs"])
        return CatalogConfig(
            version=version,
            catalog=catalog,
            catalog_id=catalog["catalogId"],
        )


__all__ = ["BasicCatalog"]
