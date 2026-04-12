"""Python → TypeScript type and value mapping."""

from __future__ import annotations

# Python comparison operators → TypeScript
COMPARISON_MAP: dict[str, str] = {
    "==": "===",
    "!=": "!==",
    "is": "===",
    "is not": "!==",
    "True": "true",
    "False": "false",
    "None": "undefined",
}

# Python built-in class names → TypeScript builder names
CLASS_MAP: dict[str, str] = {
    "Agent": "Agent",
    "Pipeline": "Pipeline",
    "FanOut": "FanOut",
    "Loop": "Loop",
    "Route": "Route",
    "Fallback": "Fallback",
    "RemoteAgent": "RemoteAgent",
}

# Namespace modules that remain the same
NAMESPACE_MODULES: set[str] = {"S", "C", "P", "T", "G", "M", "A", "E", "UI"}

# Python keywords → TS keyword replacement
KEYWORD_MAP: dict[str, str] = {
    "lambda": "=>",  # handled specially
    "and": "&&",
    "or": "||",
    "not": "!",
    "in": "in",
}
