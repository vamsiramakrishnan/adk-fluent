"""Inter-agent contract verification with cross-channel coherence analysis.

Performs nine analysis passes on SequenceNode IR trees:

1. **reads_keys / writes_keys** (backward compat) -- old-style Pydantic-schema contracts.
2. **Output key tracking** -- tracks keys produced by output_key, CaptureNode.key,
   and TransformNode.affected_keys.
3. **Template variable resolution** -- finds ``{var}`` and ``{var?}`` placeholders in
   instruction strings and verifies they are produced by upstream agents.
4. **Channel duplication detection** -- warns when an agent writes to ``output_key``
   AND a downstream agent references that key in its instruction while also reading
   conversation history (``include_contents='default'``).  Now context-spec aware:
   uses the preserved CTransform ``_kind`` to produce smarter messages.
5. **Route key validation** -- ensures a RouteNode's ``key`` was produced upstream.
6. **Data loss detection** -- flags when a non-terminal agent has no ``output_key``
   AND its downstream agent has ``include_contents='none'``.  Context-spec aware.
7. **Visibility coherence (advisory)** -- informs when an internal agent (has a
   successor) has no ``output_key``, meaning its text lives only in conversation.
8. **Dead key detection** -- warns when a key is produced but never consumed by any
   downstream agent (via reads_keys, template variables, or route keys).
9. **Type compatibility** -- warns when produces_type fields don't cover the
   consumes_type fields of a downstream agent.
"""

from __future__ import annotations

import re
from typing import Any


def _context_description(context_spec: Any) -> str:
    """Return a human-readable description of a CTransform context spec."""
    if context_spec is None:
        return "full conversation history"

    kind = getattr(context_spec, "_kind", None)
    if kind == "user_only":
        return "C.user_only() — only user messages"
    if kind == "window":
        n = getattr(context_spec, "n", "?")
        return f"C.window(n={n}) — last {n} turn-pairs"
    if kind == "from_state":
        keys = getattr(context_spec, "keys", ())
        return f"C.from_state({', '.join(repr(k) for k in keys)}) — state keys only"
    if kind == "from_agents":
        agents = getattr(context_spec, "agents", ())
        return f"C.from_agents({', '.join(repr(a) for a in agents)}) — selective agent output"
    if kind == "exclude_agents":
        agents = getattr(context_spec, "agents", ())
        return f"C.exclude_agents({', '.join(repr(a) for a in agents)})"
    if kind == "template":
        return "C.template(...) — rendered state template"

    # Composite or pipe
    cls_name = type(context_spec).__name__
    if cls_name == "CComposite":
        blocks = getattr(context_spec, "blocks", ())
        parts = [_context_description(b) for b in blocks]
        return " + ".join(parts)
    if cls_name == "CPipe":
        source = getattr(context_spec, "source", None)
        transform = getattr(context_spec, "transform", None)
        return f"{_context_description(source)} | {_context_description(transform)}"

    include = getattr(context_spec, "include_contents", "default")
    if include == "none":
        return "C.none() — history suppressed"
    return "C.default() — full history"


def _resolve_include_contents(child: Any) -> tuple[str, Any]:
    """Return (effective_include_contents, context_spec) for a node.

    Uses preserved context_spec when available, falls back to include_contents.
    """
    context_spec = getattr(child, "context_spec", None)
    if context_spec is not None:
        cs_include = getattr(context_spec, "include_contents", None)
        if cs_include is not None:
            return cs_include, context_spec
    return getattr(child, "include_contents", "default"), context_spec


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
    # Also collect consumed keys per index for dead key detection (Pass 8)
    consumed_keys_by_idx: list[set[str]] = [set() for _ in children]

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
            consumed_keys_by_idx[idx].add(var)
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

    # Also track reads_keys as consumed
    for idx, child in enumerate(children):
        reads = getattr(child, "reads_keys", frozenset())
        consumed_keys_by_idx[idx] |= reads

    # =================================================================
    # Pass 4: Channel duplication detection (context-spec aware)
    # =================================================================
    for idx, child in enumerate(children):
        if idx == 0:
            continue

        instruction = getattr(child, "instruction", "")
        if not isinstance(instruction, str) or not instruction:
            continue

        include_contents, context_spec = _resolve_include_contents(child)

        if include_contents != "default":
            continue

        child_name = getattr(child, "name", "?")
        template_vars = set(re.findall(r"\{(\w+)\??\}", instruction))

        # Check each predecessor for output_key overlap
        for prev_idx in range(idx):
            prev = children[prev_idx]
            prev_output_key = getattr(prev, "output_key", None)
            if prev_output_key and prev_output_key in template_vars:
                ctx_desc = _context_description(context_spec)
                issues.append(
                    {
                        "level": "info",
                        "agent": child_name,
                        "message": (
                            f"Agent '{child_name}' reads '{prev_output_key}' via both "
                            f"state (template) and conversation history "
                            f"({ctx_desc}) — potential channel duplication"
                        ),
                        "hint": (
                            f"Consider using .context(C.none()) on '{child_name}' to read "
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
        consumed_keys_by_idx[idx].add(route_key)

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
    # Pass 6: Data loss detection (context-spec aware)
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

        # Check downstream's include_contents with context-spec awareness
        succ_include, succ_context_spec = _resolve_include_contents(successor)

        if succ_include == "none":
            succ_name = getattr(successor, "name", "?")
            succ_ctx_desc = _context_description(succ_context_spec)

            # Distinguish between "no history at all" vs "selective history"
            succ_kind = getattr(succ_context_spec, "_kind", None) if succ_context_spec else None
            if succ_kind in ("from_state", "template"):
                # Successor reads only from state — output IS lost unless written to state
                issues.append(
                    {
                        "level": "error",
                        "agent": child_name,
                        "message": (
                            f"Agent '{child_name}' has no output_key and its successor "
                            f"'{succ_name}' uses {succ_ctx_desc} — output is "
                            f"lost because '{succ_name}' reads only from state"
                        ),
                        "hint": (
                            f"Add .outputs('<key>') to '{child_name}' so its output "
                            f"reaches '{succ_name}' via state."
                        ),
                    }
                )
            elif succ_kind == "user_only":
                # User-only: agent output is lost (only user messages kept)
                issues.append(
                    {
                        "level": "error",
                        "agent": child_name,
                        "message": (
                            f"Agent '{child_name}' has no output_key and its successor "
                            f"'{succ_name}' uses {succ_ctx_desc} — agent output is "
                            f"lost because only user messages are included"
                        ),
                        "hint": (
                            f"Add .outputs('<key>') to '{child_name}' so its output "
                            f"reaches '{succ_name}' via state, or change "
                            f"'{succ_name}' to use C.from_agents('{child_name}')."
                        ),
                    }
                )
            elif succ_kind == "from_agents":
                # Check if successor explicitly includes this agent
                succ_agents = getattr(succ_context_spec, "agents", ())
                if child_name not in succ_agents:
                    issues.append(
                        {
                            "level": "error",
                            "agent": child_name,
                            "message": (
                                f"Agent '{child_name}' has no output_key and its successor "
                                f"'{succ_name}' uses {succ_ctx_desc} which does not include "
                                f"'{child_name}' — output is lost"
                            ),
                            "hint": (
                                f"Add '{child_name}' to the C.from_agents() list, or "
                                f"add .outputs('<key>') to '{child_name}'."
                            ),
                        }
                    )
                # If child IS in from_agents list, output is NOT lost — no issue
            else:
                # Generic fallback (C.none() or unknown)
                issues.append(
                    {
                        "level": "error",
                        "agent": child_name,
                        "message": (
                            f"Agent '{child_name}' has no output_key and its successor "
                            f"'{succ_name}' has include_contents='none' — output is "
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
                    f"Internal agent '{child_name}' has no output_key — its "
                    f"output reaches downstream only via conversation history"
                ),
                "hint": (
                    f"Add .outputs('<key>') to '{child_name}' if downstream "
                    f"agents need structured access to its output via state."
                ),
            }
        )

    # =================================================================
    # Pass 8: Dead key detection (produced but never consumed)
    # =================================================================
    all_consumed: set[str] = set()
    for consumed in consumed_keys_by_idx:
        all_consumed |= consumed

    # For each key produced, check if any downstream agent consumes it
    for idx, child in enumerate(children):
        child_name = getattr(child, "name", "?")
        child_type = type(child).__name__

        produced_by_child: set[str] = set()
        output_key = getattr(child, "output_key", None)
        if output_key:
            produced_by_child.add(output_key)
        if child_type == "CaptureNode":
            capture_key = getattr(child, "key", None)
            if capture_key:
                produced_by_child.add(capture_key)
        if child_type == "TransformNode":
            affected = getattr(child, "affected_keys", None)
            if affected:
                produced_by_child |= set(affected)

        # Also count writes_keys
        writes = getattr(child, "writes_keys", frozenset())
        produced_by_child |= writes

        if not produced_by_child:
            continue

        # Check if any downstream agent consumes these keys
        downstream_consumed: set[str] = set()
        for later_idx in range(idx + 1, len(children)):
            downstream_consumed |= consumed_keys_by_idx[later_idx]

        dead = produced_by_child - downstream_consumed
        # Only report if this isn't the last agent (last agent's output goes to user)
        if dead and idx < len(children) - 1:
            for key in sorted(dead):
                issues.append(
                    {
                        "level": "info",
                        "agent": child_name,
                        "message": (
                            f"Key '{key}' produced by '{child_name}' is not consumed "
                            f"by any downstream agent in this sequence"
                        ),
                        "hint": (
                            f"If '{key}' is intentionally unused, this is fine. "
                            f"Otherwise, a downstream agent may need "
                            f".consumes(<schema>) or '{{" + key + "}}' in its instruction."
                        ),
                    }
                )

    # =================================================================
    # Pass 9: Type compatibility (produces_type vs consumes_type)
    # =================================================================
    for idx, child in enumerate(children):
        consumes_type = getattr(child, "consumes_type", None)
        if not consumes_type:
            continue

        child_name = getattr(child, "name", "?")
        consumes_fields = set(consumes_type.model_fields.keys()) if hasattr(consumes_type, "model_fields") else set()
        if not consumes_fields:
            continue

        # Find the most recent upstream agent with produces_type
        for prev_idx in range(idx - 1, -1, -1):
            prev = children[prev_idx]
            produces_type = getattr(prev, "produces_type", None)
            if not produces_type:
                continue

            prev_name = getattr(prev, "name", "?")
            produces_fields = (
                set(produces_type.model_fields.keys()) if hasattr(produces_type, "model_fields") else set()
            )
            if not produces_fields:
                continue

            missing_fields = consumes_fields - produces_fields
            if missing_fields:
                issues.append(
                    {
                        "level": "error",
                        "agent": child_name,
                        "message": (
                            f"Agent '{child_name}' consumes {consumes_type.__name__} "
                            f"but upstream '{prev_name}' produces {produces_type.__name__} "
                            f"which is missing fields: {', '.join(sorted(missing_fields))}"
                        ),
                        "hint": (
                            f"Add the missing fields to {produces_type.__name__} or "
                            f"remove them from {consumes_type.__name__}."
                        ),
                    }
                )
            break  # Only check the nearest upstream producer

    return issues
