"""Runtime helpers for adk-fluent ergonomic features. Hand-written, not generated."""
from __future__ import annotations
import copy
from typing import Any

def deep_clone_builder(builder: Any, new_name: str) -> Any:
    """Deep-copy a builder's internal state and set a new name."""
    new_builder = object.__new__(type(builder))
    new_builder._config = copy.deepcopy(builder._config)
    new_builder._callbacks = copy.deepcopy(builder._callbacks)
    new_builder._lists = copy.deepcopy(builder._lists)
    new_builder._config["name"] = new_name
    return new_builder
