"""Convenience facade re-exporting the public A2UI agent surface.

``adk_fluent`` and its test-suite import the toolset from this module::

    from a2ui.agent import SendA2uiToClientToolset
"""

from __future__ import annotations

from a2ui.adk.send_a2ui_to_client_toolset import (
    A2UI_OUTBOX_STATE_KEY,
    SendA2uiToClientToolset,
)
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.schema.constants import VERSION_0_9, VERSION_0_10
from a2ui.schema.manager import A2uiSchemaManager

__all__ = [
    "SendA2uiToClientToolset",
    "A2UI_OUTBOX_STATE_KEY",
    "BasicCatalog",
    "A2uiSchemaManager",
    "remove_strict_validation",
    "VERSION_0_9",
    "VERSION_0_10",
]
