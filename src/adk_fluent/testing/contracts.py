"""Inter-agent contract verification with cross-channel coherence analysis.

Checks SequenceNode, ParallelNode, and LoopNode IR trees:

**Sequence passes (16 total):**

1. **reads_keys / writes_keys** (backward compat) -- old-style Pydantic-schema contracts.
2. **Output key tracking** -- tracks keys produced by output_key, CaptureNode.key,
   and TransformNode.affected_keys.  Now uses transform ``reads_keys`` to consume
   upstream keys and ``affected_keys`` to produce new ones, enabling tracing through
   ``S.rename()``, ``S.merge()``, etc.
3. **Template variable resolution** -- finds ``{var}`` and ``{var?}`` placeholders in
   instruction strings and verifies they are produced by upstream agents.
4. **Channel duplication detection** -- warns when an agent writes to ``output_key``
   AND a downstream agent references that key in its instruction while also reading
   conversation history.  Context-spec aware.
5. **Route key validation** -- ensures a RouteNode's ``key`` was produced upstream.
6. **Data loss detection** -- flags when a non-terminal agent has no ``output_key``
   AND its downstream agent has ``include_contents='none'``.  Context-spec aware.
7. **Visibility coherence (advisory)** -- informs when an internal agent (has a
   successor) has no ``output_key``, meaning its text lives only in conversation.
8. **Dead key detection** -- warns when a key is produced but never consumed by any
   downstream agent (via reads_keys, template variables, or route keys).
9. **Type compatibility** -- warns when produces_type fields don't cover the
   consumes_type fields of a downstream agent.
10. **Transform reads validation** -- verifies that transform reads_keys are
    available upstream.
11. **Rename/pick passthrough** -- for replacement transforms (S.rename, S.pick),
    warns if they consume keys not available upstream.
12. **Dispatch/Join coherence** -- checks that DispatchNode task names are unique
    and that JoinNode target_names reference dispatched tasks upstream.
13. **ToolSchema / CallbackSchema / Predicate dependency validation** -- checks
    that ``reads_keys()`` from ToolSchema, CallbackSchema, and PredicateSchema
    are produced by upstream agents.  Also promotes schema ``writes_keys()``
    so downstream consumers can depend on them.
14. **MiddlewareSchema dependency validation** -- checks that scoped middleware
    ``reads_keys()`` are produced by upstream agents at the target agent's position.
    Promotes middleware ``writes_keys()`` so downstream consumers can depend on them.
15. **Artifact availability** -- checks that ``consumes_artifact`` filenames are
    produced by an upstream ``A.publish()`` or ``A.save()``.  Also validates that
    bridge operations (publish) have their ``from_key`` available in state.
16. **ArtifactSchema dependency validation** -- checks that ``ArtifactSchema``
    consumed artifacts are produced upstream.  Also checks MIME compatibility
    and promotes schema-produced artifacts so downstream consumers can depend
    on them.

**Parallel checks:**
- Write isolation: two branches should not write to the same output_key
- Schema collision: two branches should not produce overlapping writes_keys

**Loop checks:**
- Body sequence validation: runs sequence checks on loop children
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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
    if kind == "notes":
        key = getattr(context_spec, "key", "?")
        return f"C.notes({key!r}) — scratchpad read"
    if kind == "write_notes":
        key = getattr(context_spec, "key", "?")
        return f"C.write_notes({key!r}) — scratchpad write"
    if kind == "rolling":
        n = getattr(context_spec, "n", "?")
        s = getattr(context_spec, "summarize", False)
        return f"C.rolling(n={n}, summarize={s}) — rolling window"
    if kind == "from_agents_windowed":
        aw = getattr(context_spec, "agent_windows", ())
        parts = [f"{a}={n}" for a, n in aw]
        return f"C.from_agents_windowed({', '.join(parts)})"
    if kind == "user_strategy":
        strategy = getattr(context_spec, "strategy", "all")
        return f"C.user(strategy={strategy!r})"
    if kind == "manus_cascade":
        budget = getattr(context_spec, "budget", "?")
        return f"C.manus_cascade(budget={budget})"
    if kind == "pipeline_aware":
        keys = getattr(context_spec, "keys", ())
        return f"C.pipeline_aware({', '.join(repr(k) for k in keys)}) — user messages + state keys"

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


def _get_transform_writes(child: Any) -> set[str]:
    """Extract the keys written by a TransformNode, using affected_keys."""
    affected = getattr(child, "affected_keys", None)
    return set(affected) if affected else set()


def _get_transform_reads(child: Any) -> set[str] | None:
    """Extract the keys read by a TransformNode. None means opaque (reads full state)."""
    reads = getattr(child, "reads_keys", None)
    return set(reads) if reads is not None else None


# ======================================================================
# Sequence contract checking
# ======================================================================


def _check_sequence_contracts(
    children: tuple, scope: str = "", middlewares: tuple | list = ()
) -> list[dict[str, str] | str]:
    """Check contracts on an ordered sequence of children.

    Args:
        children: Tuple of IR nodes in sequence order.
        scope: Optional prefix for nested scopes (e.g., "loop.body").
        middlewares: Optional middleware instances to validate (Pass 14).

    Returns:
        List of issues (str or dict).
    """
    if not children:
        return []

    issues: list[dict[str, str] | str] = []

    def _scoped(name: str) -> str:
        return f"{scope}.{name}" if scope else name

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
                issues.append(f"Agent '{_scoped(child_name)}' consumes key '{key}' but no prior step produces it")

        available_keys |= writes

    # =================================================================
    # Pass 2: Output key tracking with transform tracing
    # =================================================================
    produced_keys: set[str] = set()
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
            transform_writes = _get_transform_writes(child)
            if transform_writes:
                produced_keys |= transform_writes

        produced_at.append(set(produced_keys))

    # =================================================================
    # Pass 3: Template variable resolution
    # =================================================================
    consumed_keys_by_idx: list[set[str]] = [set() for _ in children]

    for idx, child in enumerate(children):
        instruction = getattr(child, "instruction", "")
        if not isinstance(instruction, str) or not instruction:
            continue

        # Capture (name, optional_marker) pairs: {var} → ("var", ""), {var?} → ("var", "?")
        template_matches = re.findall(r"\{(\w+)(\??)\}", instruction)
        if not template_matches:
            continue

        child_name = getattr(child, "name", "?")
        upstream_keys = produced_at[idx - 1] if idx > 0 else set()

        for var, opt_marker in template_matches:
            consumed_keys_by_idx[idx].add(var)
            is_optional = opt_marker == "?"
            if var not in upstream_keys:
                if is_optional:
                    # Optional vars get an advisory, not an error
                    issues.append(
                        {
                            "level": "info",
                            "agent": _scoped(child_name),
                            "message": (
                                f"Optional template variable '{{{var}?}}' is not produced by any upstream agent "
                                f"(will resolve to empty string at runtime)"
                            ),
                            "hint": (
                                f"This is OK if the variable is intentionally optional. "
                                f"Otherwise, add .writes('{var}') to an upstream agent."
                            ),
                        }
                    )
                else:
                    issues.append(
                        {
                            "level": "error",
                            "agent": _scoped(child_name),
                            "message": (
                                f"Template variable '{{{var}}}' in instruction is not produced by any upstream agent"
                            ),
                            "hint": (
                                f"Add .outputs('{var}') to an upstream agent, or use "
                                f"S.capture('{var}') to capture user input into state. "
                                f"If this variable is optional, use '{{{var}?}}' syntax."
                            ),
                        }
                    )

    # Also track reads_keys as consumed (skip None — TransformNode uses None for opaque)
    for idx, child in enumerate(children):
        reads = getattr(child, "reads_keys", None)
        if reads is not None:
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

        for prev_idx in range(idx):
            prev = children[prev_idx]
            prev_output_key = getattr(prev, "output_key", None)
            if prev_output_key and prev_output_key in template_vars:
                ctx_desc = _context_description(context_spec)
                issues.append(
                    {
                        "level": "info",
                        "agent": _scoped(child_name),
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
                    "agent": _scoped(child_name),
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

        if child_type != "AgentNode":
            continue

        output_key = getattr(child, "output_key", None)
        if output_key:
            continue

        child_name = getattr(child, "name", "?")
        successor = children[idx + 1]
        succ_include, succ_context_spec = _resolve_include_contents(successor)

        if succ_include == "none":
            succ_name = getattr(successor, "name", "?")
            succ_ctx_desc = _context_description(succ_context_spec)
            succ_kind = getattr(succ_context_spec, "_kind", None) if succ_context_spec else None

            if succ_kind in ("from_state", "template"):
                issues.append(
                    {
                        "level": "error",
                        "agent": _scoped(child_name),
                        "message": (
                            f"Agent '{child_name}' has no output_key and its successor "
                            f"'{succ_name}' uses {succ_ctx_desc} — output is "
                            f"lost because '{succ_name}' reads only from state"
                        ),
                        "hint": f"Add .outputs('<key>') to '{child_name}' so its output reaches '{succ_name}' via state.",
                    }
                )
            elif succ_kind == "user_only":
                issues.append(
                    {
                        "level": "error",
                        "agent": _scoped(child_name),
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
                succ_agents = getattr(succ_context_spec, "agents", ())
                if child_name not in succ_agents:
                    issues.append(
                        {
                            "level": "error",
                            "agent": _scoped(child_name),
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
            else:
                issues.append(
                    {
                        "level": "error",
                        "agent": _scoped(child_name),
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

        if child_type != "AgentNode":
            continue

        instruction = getattr(child, "instruction", "")
        if not isinstance(instruction, str) or not instruction:
            continue

        output_key = getattr(child, "output_key", None)
        if output_key:
            continue

        child_name = getattr(child, "name", "?")
        issues.append(
            {
                "level": "info",
                "agent": _scoped(child_name),
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
            produced_by_child |= _get_transform_writes(child)
        writes = getattr(child, "writes_keys", frozenset())
        produced_by_child |= writes

        if not produced_by_child:
            continue

        downstream_consumed: set[str] = set()
        for later_idx in range(idx + 1, len(children)):
            downstream_consumed |= consumed_keys_by_idx[later_idx]

        dead = produced_by_child - downstream_consumed
        if dead and idx < len(children) - 1:
            for key in sorted(dead):
                issues.append(
                    {
                        "level": "info",
                        "agent": _scoped(child_name),
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
                        "agent": _scoped(child_name),
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
            break

    # =================================================================
    # Pass 10: Transform reads validation
    # =================================================================
    for idx, child in enumerate(children):
        child_type = type(child).__name__
        if child_type != "TransformNode":
            continue

        transform_reads = _get_transform_reads(child)
        if transform_reads is None:
            continue  # opaque — can't validate

        child_name = getattr(child, "name", "?")
        upstream_keys = produced_at[idx - 1] if idx > 0 else set()

        missing = transform_reads - upstream_keys
        if missing:
            for key in sorted(missing):
                consumed_keys_by_idx[idx].add(key)
                issues.append(
                    {
                        "level": "error",
                        "agent": _scoped(child_name),
                        "message": (f"Transform '{child_name}' reads key '{key}' but no upstream agent produces it"),
                        "hint": (
                            f"Add .outputs('{key}') to an upstream agent, or "
                            f"ensure the key is in state before this transform runs."
                        ),
                    }
                )
        consumed_keys_by_idx[idx] |= transform_reads

    # =================================================================
    # Pass 12: Dispatch/Join coherence
    # =================================================================
    from adk_fluent._ir import DispatchNode, JoinNode

    dispatched_names: set[str] = set()
    for child in children:
        if isinstance(child, DispatchNode):
            for tn in getattr(child, "task_names", ()):
                if tn in dispatched_names:
                    issues.append(
                        {
                            "level": "warning",
                            "agent": _scoped(getattr(child, "name", "?")),
                            "message": f"Duplicate dispatch task name '{tn}'",
                            "hint": "Use unique names for selective join().",
                        }
                    )
                dispatched_names.add(tn)
        elif isinstance(child, JoinNode):
            targets = getattr(child, "target_names", None)
            if targets:
                for tn in targets:
                    if tn not in dispatched_names:
                        issues.append(
                            {
                                "level": "warning",
                                "agent": _scoped(getattr(child, "name", "?")),
                                "message": f"join() references '{tn}' but no dispatch with that name found upstream",
                                "hint": "Ensure dispatch task names match join target names.",
                            }
                        )

    # =================================================================
    # Pass 13: ToolSchema / CallbackSchema dependency validation
    # =================================================================
    schema_available: set[str] = set()
    # Rebuild available keys incrementally for schema checking
    for child in children:
        child_name = getattr(child, "name", "?")

        # Check tool_schema and callback_schema reads
        for schema_attr, label in [
            ("tool_schema", "ToolSchema"),
            ("callback_schema", "CallbackSchema"),
            ("prompt_schema", "PromptSchema"),
        ]:
            schema = getattr(child, schema_attr, None)
            if schema is None or not hasattr(schema, "reads_keys"):
                continue

            schema_reads = schema.reads_keys()
            if schema_reads:
                missing = schema_reads - schema_available
                for key in sorted(missing):
                    issues.append(
                        {
                            "level": "warning",
                            "agent": _scoped(child_name),
                            "message": (f"{label} reads key '{key}' but it is not produced by any upstream agent"),
                            "hint": (
                                f"Add .outputs('{key}') to an upstream agent "
                                f"or use S.set() / S.capture() to provide this key."
                            ),
                        }
                    )

        # Check RouteNode predicate reads
        rules = getattr(child, "rules", ())
        for pred, _agent in rules:
            if hasattr(pred, "reads_keys"):
                pred_reads = pred.reads_keys()
                missing = pred_reads - schema_available
                for key in sorted(missing):
                    issues.append(
                        {
                            "level": "warning",
                            "agent": _scoped(child_name),
                            "message": (f"Predicate reads key '{key}' but it is not produced by any upstream agent"),
                            "hint": (f"Add .outputs('{key}') to an upstream agent or use S.set() to provide this key."),
                        }
                    )

        # Check GateNode predicate reads
        gate_pred = getattr(child, "predicate", None)
        if gate_pred is not None and hasattr(gate_pred, "reads_keys"):
            pred_reads = gate_pred.reads_keys()
            missing = pred_reads - schema_available
            for key in sorted(missing):
                issues.append(
                    {
                        "level": "warning",
                        "agent": _scoped(child_name),
                        "message": (f"Gate predicate reads key '{key}' but it is not produced by any upstream agent"),
                        "hint": (f"Add .outputs('{key}') to an upstream agent or use S.set() to provide this key."),
                    }
                )

        # Update available keys with this child's contributions
        # Mirror the logic from Pass 1-2
        writes = getattr(child, "writes_keys", frozenset())
        if writes:
            schema_available |= writes
        ok = getattr(child, "output_key", None)
        if ok:
            schema_available.add(ok)
        # ToolSchema/CallbackSchema writes also become available
        for schema_attr in ("tool_schema", "callback_schema"):
            schema = getattr(child, schema_attr, None)
            if schema is not None and hasattr(schema, "writes_keys"):
                schema_available |= schema.writes_keys()

    # =================================================================
    # Pass 14: MiddlewareSchema dependency validation
    # =================================================================
    if middlewares:
        # Build available-keys map at each agent position
        mw_available: dict[str, set[str]] = {}
        mw_cumulative: set[str] = set()

        for child in children:
            child_name = getattr(child, "name", "?")
            mw_available[child_name] = set(mw_cumulative)
            # Accumulate keys from this child
            ok = getattr(child, "output_key", None)
            if ok:
                mw_cumulative.add(ok)
            writes = getattr(child, "writes_keys", frozenset())
            if writes:
                mw_cumulative |= writes
            for sa in ("tool_schema", "callback_schema"):
                s = getattr(child, sa, None)
                if s is not None and hasattr(s, "writes_keys"):
                    mw_cumulative |= s.writes_keys()

        # Check each scoped middleware
        for mw in middlewares:
            agents_scope = getattr(mw, "agents", None)
            schema_cls = getattr(mw, "schema", None)
            if agents_scope is None or schema_cls is None:
                continue
            if not hasattr(schema_cls, "reads_keys"):
                continue

            # Normalize target agents
            if isinstance(agents_scope, str):
                target_names = (agents_scope,)
            elif isinstance(agents_scope, tuple):
                target_names = agents_scope
            else:
                continue  # regex/callable scopes can't be statically resolved

            schema_reads = schema_cls.reads_keys()
            schema_writes = schema_cls.writes_keys() if hasattr(schema_cls, "writes_keys") else frozenset()

            for target in target_names:
                if target not in mw_available:
                    continue  # agent not in this pipeline
                available = mw_available[target]
                missing = schema_reads - available
                for key in sorted(missing):
                    issues.append(
                        {
                            "level": "warning",
                            "agent": _scoped(target),
                            "message": (
                                f"MiddlewareSchema reads key '{key}' but it is not produced by any upstream agent"
                            ),
                            "hint": (
                                f"Add .writes('{key}') to an upstream agent "
                                f"or use S.set() / S.capture() to provide this key."
                            ),
                        }
                    )

                # Promote middleware writes at this agent's position
                if schema_writes:
                    found = False
                    for child in children:
                        cn = getattr(child, "name", "?")
                        if cn == target:
                            found = True
                            continue
                        if found and cn in mw_available:
                            mw_available[cn] |= schema_writes

    # =================================================================
    # Pass 15: Artifact availability
    # =================================================================
    from adk_fluent._ir import ArtifactNode

    artifacts_available: set[str] = set()

    for idx, child in enumerate(children):
        child_name = getattr(child, "name", "?")

        if not isinstance(child, ArtifactNode):
            # Non-artifact nodes may still produce state keys (tracked in produced_keys already)
            continue

        # Check consumed artifacts are available upstream
        for artifact_name in child.consumes_artifact:
            if artifact_name not in artifacts_available:
                issues.append(
                    {
                        "level": "error",
                        "agent": _scoped(child_name),
                        "message": (
                            f"Consumes artifact '{artifact_name}' but no upstream A.publish() or A.save() produces it"
                        ),
                    }
                )

        # Check consumed state keys (bridge ops like publish reading from_key)
        if child.bridges_state:
            upstream_keys = produced_at[idx - 1] if idx > 0 else set()
            for key in child.consumes_state:
                if key not in upstream_keys:
                    issues.append(
                        {
                            "level": "error",
                            "agent": _scoped(child_name),
                            "message": (f"A.publish() reads state key '{key}' but no upstream agent produces it"),
                        }
                    )

        # Promote produced artifacts
        for artifact_name in child.produces_artifact:
            artifacts_available.add(artifact_name)

        # Promote produced state keys (so downstream state checks see them)
        for key in child.produces_state:
            produced_keys.add(key)

    # =================================================================
    # Pass 16: ArtifactSchema dependency validation
    # =================================================================

    artifact_mime_map: dict[str, str | None] = {}  # filename -> mime

    for child in children:
        child_name = getattr(child, "name", "?")

        # Track MIME from ArtifactNode produces
        if isinstance(child, ArtifactNode):
            for artifact_name in child.produces_artifact:
                artifact_mime_map[artifact_name] = child.mime

        # Check ArtifactSchema on AgentNodes
        schema = getattr(child, "artifact_schema", None)
        if schema is None:
            continue

        # Check consumed artifacts are available
        for consumed in schema.consumes_fields():
            if consumed.filename not in artifacts_available:
                issues.append(
                    {
                        "level": "error",
                        "agent": _scoped(child_name),
                        "message": (f"ArtifactSchema consumes '{consumed.filename}' but not produced upstream"),
                    }
                )

            # MIME compatibility check
            producer_mime = artifact_mime_map.get(consumed.filename)
            if producer_mime and consumed.mime and producer_mime != consumed.mime:
                issues.append(
                    {
                        "level": "warning",
                        "agent": _scoped(child_name),
                        "message": (
                            f"MIME mismatch: '{consumed.filename}' produced as "
                            f"{producer_mime}, consumed as {consumed.mime}"
                        ),
                    }
                )

        # Promote produced artifacts from schema
        for produced in schema.produces_fields():
            artifacts_available.add(produced.filename)
            artifact_mime_map[produced.filename] = produced.mime

    # =================================================================
    # Pass 17: Cross-channel coherence analysis
    # =================================================================
    # Synthesizes all three channels (conversation, state, instruction)
    # into unified data flow contract suggestions.

    for idx in range(len(children) - 1):
        child = children[idx]
        child_type = type(child).__name__
        if child_type != "AgentNode":
            continue

        child_name = getattr(child, "name", "?")
        output_key = getattr(child, "output_key", None)
        successor = children[idx + 1]
        succ_name = getattr(successor, "name", "?")
        succ_type = type(successor).__name__
        succ_include, succ_context_spec = _resolve_include_contents(successor)

        # --- Inference: successor reads state but predecessor has no output_key ---
        # Check template vars in successor instruction
        succ_instruction = getattr(successor, "instruction", "")
        succ_template_vars: set[str] = set()
        if isinstance(succ_instruction, str) and succ_instruction:
            succ_template_vars = set(re.findall(r"\{(\w+)\??\}", succ_instruction))

        # Check successor .reads() keys (from context spec)
        succ_reads: set[str] = set()
        if succ_context_spec is not None:
            succ_kind = getattr(succ_context_spec, "_kind", None)
            if succ_kind == "from_state":
                succ_reads = set(getattr(succ_context_spec, "keys", ()))

        # Check if successor is a RouteNode
        succ_route_key = None
        if succ_type == "RouteNode":
            succ_route_key = getattr(successor, "key", None)

        # Collect all state keys the successor needs
        succ_needs_keys = succ_template_vars | succ_reads
        if succ_route_key:
            succ_needs_keys.add(succ_route_key)

        if not output_key and succ_needs_keys:
            # Predecessor has no output_key but successor needs state data.
            upstream_keys = produced_at[idx - 1] if idx > 0 else set()
            unresolved = succ_needs_keys - upstream_keys

            if unresolved:
                hint_keys = ", ".join(f"'{k}'" for k in sorted(unresolved))
                issues.append(
                    {
                        "level": "warning",
                        "agent": _scoped(child_name),
                        "message": (
                            f"Agent '{child_name}' precedes '{succ_name}' which reads "
                            f"state keys [{hint_keys}], but '{child_name}' has no "
                            f".writes() — its output does not reach state. "
                            f"Consider adding .writes(<key>) to '{child_name}' "
                            f"or an S.capture() transform between them."
                        ),
                        "hint": (
                            f"The >> operator implies data flow from '{child_name}' "
                            f"to '{succ_name}'. Without .writes(), the output exists "
                            f"only in conversation history, not in session state."
                        ),
                    }
                )

        # --- Cross-channel: output_key set + default history = duplication risk ---
        if (
            output_key
            and succ_include == "default"
            and succ_type == "AgentNode"
            and output_key not in succ_template_vars
            and output_key not in succ_reads
        ):
            issues.append(
                {
                    "level": "info",
                    "agent": _scoped(succ_name),
                    "message": (
                        f"Agent '{child_name}' writes to state['{output_key}'] "
                        f"but '{succ_name}' doesn't read it via template or "
                        f".reads() — the structured output is unused while "
                        f"conversation history carries the raw text"
                    ),
                    "hint": (
                        f"If '{succ_name}' needs '{child_name}''s output, "
                        f"add .reads('{output_key}') or '{{" + output_key + "}}' "
                        f"in the instruction. Otherwise consider removing "
                        f".writes('{output_key}') from '{child_name}'."
                    ),
                }
            )

    return issues


# ======================================================================
# Parallel contract checking
# ======================================================================


def _check_parallel_contracts(children: tuple, parent_name: str = "") -> list[dict[str, str] | str]:
    """Check contracts on parallel (fanout) children.

    Checks:
    - Write isolation: two branches should not write to the same output_key
    - Schema collision: two branches should not produce overlapping writes_keys
    """
    if not children:
        return []

    issues: list[dict[str, str] | str] = []
    scope = parent_name or "parallel"

    # Collect output_keys and writes_keys per branch
    branch_output_keys: dict[str, list[str]] = {}
    branch_writes_keys: dict[str, list[str]] = {}

    def _collect_writes(node: Any, branch_name: str) -> None:
        """Recursively collect all writes from a node and its children."""
        output_key = getattr(node, "output_key", None)
        if output_key:
            branch_output_keys.setdefault(output_key, []).append(branch_name)

        writes = getattr(node, "writes_keys", frozenset())
        for key in writes:
            branch_writes_keys.setdefault(key, []).append(branch_name)

        node_type = type(node).__name__
        if node_type == "TransformNode":
            for key in _get_transform_writes(node):
                branch_writes_keys.setdefault(key, []).append(branch_name)

        for sub in getattr(node, "children", ()):
            _collect_writes(sub, branch_name)

    for child in children:
        child_name = getattr(child, "name", "?")
        _collect_writes(child, child_name)

    # Check output_key collisions
    for key, branches in branch_output_keys.items():
        unique = list(dict.fromkeys(branches))  # dedupe preserving order
        if len(unique) > 1:
            issues.append(
                {
                    "level": "error",
                    "agent": scope,
                    "message": (
                        f"Parallel branches {', '.join(repr(b) for b in unique)} "
                        f"both write to output_key='{key}' — last-write-wins race condition"
                    ),
                    "hint": (
                        "Give each branch a unique output_key, or merge results with a downstream S.merge() transform."
                    ),
                }
            )

    # Check writes_keys collisions
    for key, branches in branch_writes_keys.items():
        unique = list(dict.fromkeys(branches))
        if len(unique) > 1:
            issues.append(
                {
                    "level": "info",
                    "agent": scope,
                    "message": (
                        f"Parallel branches {', '.join(repr(b) for b in unique)} "
                        f"both write to state key '{key}' — potential race condition"
                    ),
                    "hint": "Consider unique output keys per branch if ordering matters.",
                }
            )

    # Also run sequence checks on any child that is itself a sequence
    from adk_fluent._ir_generated import SequenceNode

    for child in children:
        if isinstance(child, SequenceNode) and child.children:
            child_name = getattr(child, "name", "?")
            sub_issues = _check_sequence_contracts(child.children, scope=f"{scope}.{child_name}")
            issues.extend(sub_issues)

    return issues


# ======================================================================
# Loop contract checking
# ======================================================================


def _check_loop_contracts(children: tuple, parent_name: str = "") -> list[dict[str, str] | str]:
    """Check contracts on loop body children.

    Runs sequence validation on the loop body.
    """
    if not children:
        return []

    scope = parent_name or "loop"
    return _check_sequence_contracts(children, scope=scope)


# ======================================================================
# Public entry point (dispatches by node type)
# ======================================================================


def check_contracts(ir_node: Any) -> list[dict[str, str] | str]:
    """Verify contracts on an IR tree. Dispatches by node type.

    Checks SequenceNode (full 16-pass analysis), ParallelNode (isolation),
    LoopNode (body sequence validation), and DispatchNode (independent agents).

    Returns a list where each item is either:
    - a ``str``  (backward compat, from Pass 1)
    - a ``dict`` with keys ``level``, ``agent``, ``message``, ``hint``
    """
    from adk_fluent._ir import DispatchNode
    from adk_fluent._ir_generated import LoopNode, ParallelNode, SequenceNode

    if isinstance(ir_node, SequenceNode):
        if not ir_node.children:
            return []
        middlewares = getattr(ir_node, "middlewares", ())
        return _check_sequence_contracts(ir_node.children, middlewares=middlewares)

    if isinstance(ir_node, ParallelNode):
        if not ir_node.children:
            return []
        return _check_parallel_contracts(ir_node.children, parent_name=ir_node.name)

    if isinstance(ir_node, LoopNode):
        if not ir_node.children:
            return []
        return _check_loop_contracts(ir_node.children, parent_name=ir_node.name)

    if isinstance(ir_node, DispatchNode):
        # Dispatch children are independent agents — no sequence contract needed
        return []

    return []


# ======================================================================
# Data flow inference (topology-aware suggestions)
# ======================================================================


@dataclass(frozen=True)
class DataFlowSuggestion:
    """A suggestion for improving data flow in a pipeline.

    Returned by ``infer_data_flow()`` to help developers wire their
    pipelines correctly.  Each suggestion identifies an agent, the
    recommended action, and the reasoning behind it.
    """

    agent: str
    """Name of the agent the suggestion applies to."""

    action: str
    """Short action verb: 'add_writes', 'add_reads', 'set_context', 'remove_writes'."""

    key: str
    """The state key involved in the suggestion."""

    reason: str
    """Human-readable explanation of why this suggestion exists."""

    successor: str = ""
    """Name of the downstream agent that motivated this suggestion."""

    channel: str = ""
    """Which channel is affected: 'state', 'conversation', 'instruction'."""


def infer_data_flow(ir_node: Any) -> list[DataFlowSuggestion]:
    """Analyze an IR tree and return topology-aware data flow suggestions.

    Examines the pipeline structure to identify:

    1. **Missing writes**: An agent precedes a consumer that reads from
       state (via template vars, ``.reads()``, or Route key) but the
       agent has no ``.writes()`` — its output doesn't reach state.

    2. **Unused writes**: An agent writes to state via ``output_key``
       but no downstream agent reads that key — the write is wasted.

    3. **Missing reads**: A downstream agent receives data only via
       conversation history when it could use structured state access.

    4. **Context recommendations**: Suggestions for using context
       engineering (``C.user_only()``, ``C.from_agents()``) to avoid
       channel duplication.

    Returns:
        List of ``DataFlowSuggestion`` objects, sorted by pipeline position.

    Example::

        pipeline = Agent("classifier") >> Route("intent").eq("book", booker)
        suggestions = infer_data_flow(pipeline.to_ir())
        for s in suggestions:
            print(f"{s.agent}: {s.action}('{s.key}') — {s.reason}")
    """
    from adk_fluent._ir_generated import SequenceNode

    if not isinstance(ir_node, SequenceNode):
        return []
    if not ir_node.children:
        return []

    children = ir_node.children
    suggestions: list[DataFlowSuggestion] = []

    # Build produced_keys map at each position
    produced_keys: set[str] = set()
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
            tw = _get_transform_writes(child)
            if tw:
                produced_keys |= tw
        produced_at.append(set(produced_keys))

    # Analyze each agent's data flow needs
    for idx, child in enumerate(children):
        child_type = type(child).__name__
        child_name = getattr(child, "name", "?")
        output_key = getattr(child, "output_key", None)

        # --- Suggestion 1: Missing writes ---
        if child_type == "AgentNode" and not output_key and idx < len(children) - 1:
            successor = children[idx + 1]
            succ_name = getattr(successor, "name", "?")

            # What does successor need from state?
            needed_keys = _get_consumer_needs(successor)
            upstream_keys = produced_at[idx - 1] if idx > 0 else set()
            unresolved = needed_keys - upstream_keys

            if unresolved:
                # Suggest the most plausible key name
                suggested_key = child_name if len(unresolved) > 1 else next(iter(unresolved))
                suggestions.append(
                    DataFlowSuggestion(
                        agent=child_name,
                        action="add_writes",
                        key=suggested_key,
                        reason=(
                            f"Successor '{succ_name}' reads state keys "
                            f"{sorted(unresolved)} but '{child_name}' has no "
                            f".writes() — output stays in conversation only"
                        ),
                        successor=succ_name,
                        channel="state",
                    )
                )

        # --- Suggestion 2: Unused writes ---
        if output_key and idx < len(children) - 1:
            consumed_downstream = False
            for later_idx in range(idx + 1, len(children)):
                later = children[later_idx]
                later_needs = _get_consumer_needs(later)
                if output_key in later_needs:
                    consumed_downstream = True
                    break
            if not consumed_downstream:
                suggestions.append(
                    DataFlowSuggestion(
                        agent=child_name,
                        action="remove_writes",
                        key=output_key,
                        reason=(
                            f"output_key='{output_key}' is not read by any downstream agent — the write has no consumer"
                        ),
                        channel="state",
                    )
                )

        # --- Suggestion 3: Context recommendations ---
        if child_type == "AgentNode" and output_key and idx < len(children) - 1:
            successor = children[idx + 1]
            succ_type2 = type(successor).__name__
            if succ_type2 == "AgentNode":
                succ_include, succ_ctx = _resolve_include_contents(successor)
                succ_name = getattr(successor, "name", "?")

                # Successor has default history AND reads the key via template
                succ_instruction = getattr(successor, "instruction", "")
                if (
                    isinstance(succ_instruction, str)
                    and f"{{{output_key}}}" in succ_instruction
                    and succ_include == "default"
                ):
                    suggestions.append(
                        DataFlowSuggestion(
                            agent=succ_name,
                            action="set_context",
                            key=output_key,
                            reason=(
                                f"'{succ_name}' reads '{output_key}' via "
                                f"template AND conversation history — "
                                f"consider .context(C.user_only()) or "
                                f".reads('{output_key}') to avoid duplication"
                            ),
                            successor=succ_name,
                            channel="conversation",
                        )
                    )

    return suggestions


def _get_consumer_needs(node: Any) -> set[str]:
    """Extract all state keys a node needs from upstream.

    Combines template variables, .reads() keys, and Route keys
    into a single set.
    """
    needs: set[str] = set()
    node_type = type(node).__name__

    # Template variables in instruction
    instruction = getattr(node, "instruction", "")
    if isinstance(instruction, str) and instruction:
        needs |= set(re.findall(r"\{(\w+)\??\}", instruction))

    # .reads() / context spec keys
    context_spec = getattr(node, "context_spec", None)
    if context_spec is not None:
        kind = getattr(context_spec, "_kind", None)
        if kind == "from_state":
            needs |= set(getattr(context_spec, "keys", ()))

    # Route key
    if node_type == "RouteNode":
        route_key = getattr(node, "key", None)
        if route_key:
            needs.add(route_key)

    # consumes_type keys
    consumes_type = getattr(node, "consumes_type", None)
    if consumes_type is not None and hasattr(consumes_type, "model_fields"):
        needs |= set(consumes_type.model_fields.keys())

    return needs
