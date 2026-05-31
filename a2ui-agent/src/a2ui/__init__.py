"""a2ui — A2UI (Agent-to-UI) protocol toolset for Google ADK.

This package provides:

* ``a2ui.schema`` — protocol version constants, the catalog schema manager,
  and catalog config modifiers.
* ``a2ui.basic_catalog`` — the ``BasicCatalog`` provider exposing the basic
  A2UI component set (Text, Button, TextField, Image, Row, Column, ...).
* ``a2ui.adk`` — the ``SendA2uiToClientToolset`` ADK toolset that lets an LLM
  emit A2UI surfaces (createSurface / updateComponents / updateDataModel) to
  a connected client.

The public surface mirrors what ``adk_fluent`` expects::

    from a2ui.basic_catalog.provider import BasicCatalog
    from a2ui.schema.constants import VERSION_0_9
    from a2ui.schema.manager import A2uiSchemaManager
    from a2ui.schema.common_modifiers import remove_strict_validation
    from a2ui.adk.send_a2ui_to_client_toolset import SendA2uiToClientToolset

    # Convenience re-export used by adk-fluent tests:
    from a2ui.agent import SendA2uiToClientToolset
"""

from __future__ import annotations

__version__ = "0.2.0"

__all__ = ["__version__"]
