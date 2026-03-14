"""Shared utilities for code generation pipeline."""

from __future__ import annotations


def split_at_commas(s: str) -> list[str]:
    """Split a string on commas, respecting bracket/paren nesting depth.

    Handles nested types like ``Callable[[X], Y]``, ``dict[str, str]``,
    and ``Union[X, Y]`` without incorrectly splitting on commas inside
    brackets.

    Returns a list of stripped, non-empty parts.
    """
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in s:
        if ch in ("(", "[", "{"):
            depth += 1
            current.append(ch)
        elif ch in (")", "]", "}"):
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(ch)
    if current:
        remainder = "".join(current).strip()
        if remainder:
            parts.append(remainder)
    return parts
