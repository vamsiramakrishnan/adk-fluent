"""A2UI schema layer — version constants, catalog manager, modifiers."""

from __future__ import annotations

from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.schema.constants import (
    DEFAULT_VERSION,
    PROTOCOL_VERSION,
    VERSION_0_9,
    VERSION_0_10,
)
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.schema.types import Catalog, CatalogComponent, CatalogConfig

__all__ = [
    "VERSION_0_9",
    "VERSION_0_10",
    "DEFAULT_VERSION",
    "PROTOCOL_VERSION",
    "A2uiSchemaManager",
    "remove_strict_validation",
    "Catalog",
    "CatalogComponent",
    "CatalogConfig",
]
