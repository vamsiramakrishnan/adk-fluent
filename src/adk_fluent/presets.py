"""Preset class for reusable builder configuration bundles."""
from __future__ import annotations
import difflib
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

# Complete set of fields accepted by Preset, including value fields,
# callback fields, callback aliases, and other known ADK fields.
_KNOWN_FIELDS = _KNOWN_VALUE_FIELDS | frozenset({
    # Callbacks (full names)
    "before_agent_callback", "after_agent_callback",
    "before_model_callback", "after_model_callback",
    "before_tool_callback", "after_tool_callback",
    "on_model_error_callback", "on_tool_error_callback",
    # Short callback aliases
    "before_agent", "after_agent",
    "before_model", "after_model",
    "before_tool", "after_tool",
    "on_model_error", "on_tool_error",
    # Other known ADK fields
    "sub_agents", "tools", "input_schema",
    "output_schema", "planner", "code_executor",
    "disallow_transfer_to_parent", "disallow_transfer_to_peers",
    "static_instruction",
})


class Preset:
    """A reusable bundle of builder configuration.

    Fields are classified as plain config values or callbacks.
    Known value fields (model, instruction, etc.) are always treated as
    config even though strings are not callable.

    Raises ``ValueError`` for unrecognised field names, with
    ``difflib.get_close_matches`` suggestions when a likely typo is
    detected.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._fields: dict[str, Any] = {}
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)

        for key, value in kwargs.items():
            if key not in _KNOWN_FIELDS:
                close = difflib.get_close_matches(key, _KNOWN_FIELDS, n=3, cutoff=0.6)
                hint = f" Did you mean: {', '.join(close)}?" if close else ""
                raise ValueError(
                    f"Unknown Preset field '{key}'.{hint}"
                )
            if key in _KNOWN_VALUE_FIELDS:
                self._fields[key] = value
            elif callable(value):
                # Treat as a callback -- the key is the callback field name
                self._callbacks[key].append(value)
            else:
                self._fields[key] = value
