"""A2UI protocol version constants.

The version string is the wire ``version`` field stamped on every
server-to-client message (e.g. ``{"version": "v0.9", "createSurface": ...}``)
and selects the catalog/schema variant the :class:`A2uiSchemaManager` loads.
"""

from __future__ import annotations

from typing import Final

#: A2UI protocol v0.9 — the version targeted by the bundled basic catalog.
VERSION_0_9: Final[str] = "v0.9"

#: A2UI protocol v0.10 — newer revision of the basic catalog/message schema.
VERSION_0_10: Final[str] = "v0.10"

#: Default protocol version used when none is supplied.
DEFAULT_VERSION: Final[str] = VERSION_0_9

#: Alias retained for callers that expect a generic name.
PROTOCOL_VERSION: Final[str] = DEFAULT_VERSION

#: All versions this package knows how to serve.
KNOWN_VERSIONS: Final[tuple[str, ...]] = (VERSION_0_9, VERSION_0_10)

__all__ = [
    "VERSION_0_9",
    "VERSION_0_10",
    "DEFAULT_VERSION",
    "PROTOCOL_VERSION",
    "KNOWN_VERSIONS",
]
