"""Preset class for reusable builder configuration bundles."""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Callable

__all__ = ["Preset"]


# Fields that are always treated as config values, never as callbacks,
# even if they happen to be strings or other non-callable types.
_KNOWN_VALUE_FIELDS = frozenset({
    "model", "instruction", "description", "name",
    "global_instruction", "output_key", "output_format",
    "max_iterations", "generate_content_config",
    "include_contents",
})


class Preset:
    """A reusable bundle of builder configuration.

    Fields are classified as plain config values or callbacks.
    Known value fields (model, instruction, etc.) are always treated as
    config even though strings are not callable.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._fields: dict[str, Any] = {}
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)

        for key, value in kwargs.items():
            if key in _KNOWN_VALUE_FIELDS:
                self._fields[key] = value
            elif callable(value):
                # Treat as a callback -- the key is the callback field name
                self._callbacks[key].append(value)
            else:
                self._fields[key] = value
