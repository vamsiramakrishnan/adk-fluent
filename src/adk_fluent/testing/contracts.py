"""Inter-agent contract verification with cross-channel coherence analysis.

Performs seven analysis passes on SequenceNode IR trees:

1. **reads_keys / writes_keys** (backward compat) -- old-style Pydantic-schema contracts.
2. **Output key tracking** -- tracks keys produced by output_key, CaptureNode.key,
   and TransformNode.affected_keys.
3. **Template variable resolution** -- finds ``{var}`` and ``{var?}`` placeholders in
   instruction strings and verifies they are produced by upstream agents.
4. **Channel duplication detection** -- warns when an agent writes to ``output_key``
   AND a downstream agent references that key in its instruction while also reading
   conversation history (``include_contents='default'``).
5. **Route key validation** -- ensures a RouteNode's ``key`` was produced upstream.
6. **Data loss detection** -- flags when a non-terminal agent has no ``output_key``
   AND its downstream agent has ``include_contents='none'``.
7. **Visibility coherence (advisory)** -- informs when an internal agent (has a
   successor) has no ``output_key``, meaning its text lives only in conversation.
"""

from __future__ import annotations

import re
from typing import Any


def check_contracts(ir_node: Any) -> list[dict[str, str] | str]:
    """Verify sequential steps satisfy each other's contracts across all channels.

    Only checks SequenceNode children.  For non-sequence nodes (single agents,
    parallel, loop, etc.) returns an empty list.

    Returns a list where each item is either:
    - a ``str``  (backward compat, from Pass 1)
    - a ``dict`` with keys ``level``, ``agent``, ``message``, ``hint``
    """
    from adk_fluent._ir_generated import SequenceNode

    if not isinstance(ir_node, SequenceNode):
        return []

    children = ir_node.children
    if not children:
        return []

    issues: list[dict[str, str] | str] = []

    # =================================================================
    # Pass 1: Old-style reads_keys / writes_keys (backward compat)
    # =================================================================
    available_keys: set[str] = set()
    for child in children:
        reads = getattr(child, "reads_keys", frozenset())
        writes = getattr(child, "writes_keys", frozenset())
        child_name = getattr(child, "name", "?")

        if reads:
            missing = reads - available_keys
            for key in sorted(missing):
                issues.append(f"Agent '{child_name}' consumes key '{key}' but no prior step produces it")

        available_keys |= writes

    # =================================================================
    # Pass 2: Output key tracking (cumulative produced keys)
    # =================================================================
    produced_keys: set[str] = set()
    # Build a list of (child, produced_keys_after_this_child)
    produced_at: list[set[str]] = []
    for child in children:
        child_type = type(child).__name__

        output_key = getattr(child, "output_key", None)
        if output_key:
            produced_keys.add(output_key)

        if child_type == "CaptureNode":
            capture_key = getattr(child, "key", None)
            if capture_key:
                produced_keys.add(capture_key)

        if child_type == "TransformNode":
            affected = getattr(child, "affected_keys", None)
            if affected:
                produced_keys |= set(affected)

        produced_at.append(set(produced_keys))

    # =================================================================
    # Pass 3: Template variable resolution
    # =================================================================
    for idx, child in enumerate(children):
        instruction = getattr(child, "instruction", "")
        if not isinstance(instruction, str) or not instruction:
            continue

        template_vars = re.findall(r"\{(\w+)\??\}", instruction)
        if not template_vars:
            continue

        child_name = getattr(child, "name", "?")
        # Keys available to this child = everything produced by prior children
        upstream_keys = produced_at[idx - 1] if idx > 0 else set()

        for var in template_vars:
            if var not in upstream_keys:
                issues.append(
                    {
                        "level": "error",
                        "agent": child_name,
                        "message": (
                            f"Template variable '{{{var}}}' in instruction is not produced by any upstream agent"
                        ),
                        "hint": (
                            f"Add .outputs('{var}') to an upstream agent, or use "
                            f"S.capture('{var}') to capture user input into state."
                        ),
                    }
                )

    # =================================================================
    # Pass 4: Channel duplication detection
    # =================================================================
    for idx, child in enumerate(children):
        if idx == 0:
            continue

        instruction = getattr(child, "instruction", "")
        if not isinstance(instruction, str) or not instruction:
            continue

        include_contents = getattr(child, "include_contents", "default")
        # Also check context_spec for include_contents override
        context_spec = getattr(child, "context_spec", None)
        if context_spec is not None:
            cs_include = getattr(context_spec, "include_contents", None)
            if cs_include is not None:
                include_contents = cs_include

        if include_contents != "default":
            continue

        child_name = getattr(child, "name", "?")
        template_vars = set(re.findall(r"\{(\w+)\??\}", instruction))

        # Check each predecessor for output_key overlap
        for prev_idx in range(idx):
            prev = children[prev_idx]
            prev_output_key = getattr(prev, "output_key", None)
            if prev_output_key and prev_output_key in template_vars:
                issues.append(
                    {
                        "level": "info",
                        "agent": child_name,
                        "message": (
                            f"Agent '{child_name}' reads '{prev_output_key}' via both "
                            f"state (template) and conversation history "
                            f"(include_contents='default') -- potential channel duplication"
                        ),
                        "hint": (
                            f"Consider using .history('none') on '{child_name}' to read "
                            f"only from state, or remove '{{{prev_output_key}}}' from "
                            f"the instruction to rely solely on conversation."
                        ),
                    }
                )

    # =================================================================
    # Pass 5: Route key validation
    # =================================================================
    for idx, child in enumerate(children):
        child_type = type(child).__name__
        if child_type != "RouteNode":
            continue

        route_key = getattr(child, "key", None)
        if not route_key:
            continue

        child_name = getattr(child, "name", "?")
        upstream_keys = produced_at[idx - 1] if idx > 0 else set()

        if route_key not in upstream_keys:
            issues.append(
                {
                    "level": "error",
                    "agent": child_name,
                    "message": (f"RouteNode reads key '{route_key}' from state but no upstream agent produces it"),
                    "hint": (f"Add .outputs('{route_key}') to an upstream agent so the route key is available."),
                }
            )

    # =================================================================
    # Pass 6: Data loss detection
    # =================================================================
    for idx in range(len(children) - 1):
        child = children[idx]
        child_type = type(child).__name__

        # Only check agent-like nodes (AgentNode)
        if child_type != "AgentNode":
            continue

        output_key = getattr(child, "output_key", None)
        if output_key:
            continue  # has output_key, state channel is active

        child_name = getattr(child, "name", "?")
        successor = children[idx + 1]

        # Check downstream's include_contents
        succ_include = getattr(successor, "include_contents", "default")
        succ_context_spec = getattr(successor, "context_spec", None)
        if succ_context_spec is not None:
            cs_include = getattr(succ_context_spec, "include_contents", None)
            if cs_include is not None:
                succ_include = cs_include

        if succ_include == "none":
            succ_name = getattr(successor, "name", "?")
            issues.append(
                {
                    "level": "error",
                    "agent": child_name,
                    "message": (
                        f"Agent '{child_name}' has no output_key and its successor "
                        f"'{succ_name}' has include_contents='none' -- output is "
                        f"lost through both state and conversation channels"
                    ),
                    "hint": (
                        f"Add .outputs('<key>') to '{child_name}' so its output "
                        f"reaches '{succ_name}' via state, or change "
                        f"'{succ_name}' to include conversation history."
                    ),
                }
            )

    # =================================================================
    # Pass 7: Visibility coherence (advisory)
    # =================================================================
    for idx in range(len(children) - 1):
        child = children[idx]
        child_type = type(child).__name__

        # Only check agent-like nodes with actual instructions
        if child_type != "AgentNode":
            continue

        instruction = getattr(child, "instruction", "")
        if not isinstance(instruction, str) or not instruction:
            continue

        output_key = getattr(child, "output_key", None)
        if output_key:
            continue  # already saves to state

        child_name = getattr(child, "name", "?")
        issues.append(
            {
                "level": "info",
                "agent": child_name,
                "message": (
                    f"Internal agent '{child_name}' has no output_key -- its "
                    f"output reaches downstream only via conversation history"
                ),
                "hint": (
                    f"Add .outputs('<key>') to '{child_name}' if downstream "
                    f"agents need structured access to its output via state."
                ),
            }
        )

    return issues
