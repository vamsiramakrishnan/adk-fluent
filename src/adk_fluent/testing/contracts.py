"""Inter-agent contract verification."""

from __future__ import annotations

from typing import Any


def check_contracts(ir_node: Any) -> list[str]:
    """Verify that sequential steps satisfy each other's read/write contracts.

    Only checks SequenceNode children. Untyped agents are ignored.
    Returns a list of human-readable issue strings (empty = pass).
    """
    from adk_fluent._ir_generated import SequenceNode

    if not isinstance(ir_node, SequenceNode):
        return []

    issues = []
    available_keys: set[str] = set()

    for child in ir_node.children:
        reads = getattr(child, "reads_keys", frozenset())
        writes = getattr(child, "writes_keys", frozenset())
        child_name = getattr(child, "name", "?")

        if reads:
            missing = reads - available_keys
            for key in sorted(missing):
                issues.append(f"Agent '{child_name}' consumes key '{key}' but no prior step produces it")

        available_keys |= writes

    return issues
