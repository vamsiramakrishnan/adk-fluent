"""Signature parser — converts raw signature strings to IR Param lists.

Handles signatures like:
    (self, agent: BaseAgent | AgentBuilder) -> Self
    (self, fn_or_tool, *, require_confirmation: bool = False) -> Self
    (self) -> Self
"""

from __future__ import annotations

from code_ir import Param
from code_ir.utils import split_at_commas


def parse_signature(sig: str) -> tuple[list[Param], str | None]:
    """Parse a raw signature string into (params, return_type)."""
    # Split off return type
    if " -> " in sig:
        params_part, return_type = sig.rsplit(" -> ", 1)
    else:
        params_part = sig
        return_type = None

    # Strip outer parens
    params_part = params_part.strip()
    if params_part.startswith("("):
        params_part = params_part[1:]
    if params_part.endswith(")"):
        params_part = params_part[:-1]

    params: list[Param] = []
    kw_only = False

    parts = split_at_commas(params_part)

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part == "*":
            kw_only = True
            continue

        # Parse name, type, default
        default = None
        if "=" in part:
            before_eq, default = part.rsplit("=", 1)
            part = before_eq.strip()
            default = default.strip()

        if ":" in part:
            name, type_str = part.split(":", 1)
            name = name.strip()
            type_str = type_str.strip()
        else:
            name = part.strip()
            type_str = None

        params.append(
            Param(
                name=name,
                type=type_str,
                default=default,
                keyword_only=kw_only,
            )
        )

    return params, return_type
