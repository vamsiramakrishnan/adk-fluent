"""Shared utilities for backend worker modules."""

from __future__ import annotations

import re


def safe_identifier(name: str) -> str:
    """Convert a node name to a valid Python identifier."""
    result = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if result and result[0].isdigit():
        result = f"n_{result}"
    return result or "unnamed"
