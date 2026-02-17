"""BuilderBase mixin -- shared capabilities for all generated fluent builders."""
from __future__ import annotations
from typing import Any, Self


class BuilderBase:
    """Mixin base class providing shared builder capabilities.

    All generated builders inherit from this class.
    """
    _ALIASES: dict[str, str]
    _CALLBACK_ALIASES: dict[str, str]
    _ADDITIVE_FIELDS: set[str]
