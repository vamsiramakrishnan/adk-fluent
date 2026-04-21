"""Extra methods engine — generate non-field helper methods for builders.

Produces methods like .tool(), .step(), .branch(), .transfer_to(), .delegate_to()
that don't map directly to a single Pydantic field but provide ergonomic
builder APIs.

Two approaches:
  - generate_extras(): class-name switch (legacy, explicit)
  - infer_extras(): type-driven inference from list[ComplexType] fields
"""

from __future__ import annotations

from .field_policy import _is_list_of_complex_type, _unwrap_optional

# ---------------------------------------------------------------------------
# EXPLICIT EXTRAS (class-name switch)
# ---------------------------------------------------------------------------


def generate_extras(class_name: str, tag: str, source_class: str) -> list[dict]:
    """Generate extra (non-field) methods for a builder.

    Returns a list of dicts with keys: name, signature, doc, behavior, target_field.
    """
    extras: list[dict] = []

    if class_name in ("SequentialAgent", "LoopAgent"):
        extras.append(
            {
                "name": "step",
                "signature": "(self, agent: BaseAgent | AgentBuilder) -> Self",
                "doc": "Append an agent as the next step (lazy — built at .build() time).",
                "behavior": "list_append",
                "target_field": "sub_agents",
            }
        )
    elif class_name == "ParallelAgent":
        extras.append(
            {
                "name": "branch",
                "signature": "(self, agent: BaseAgent | AgentBuilder) -> Self",
                "doc": "Add a parallel branch agent (lazy — built at .build() time).",
                "behavior": "list_append",
                "target_field": "sub_agents",
            }
        )
        extras.append(
            {
                "name": "step",
                "signature": "(self, agent: BaseAgent | AgentBuilder) -> Self",
                "doc": "Alias for .branch() — add a parallel branch. Consistent with Pipeline/Loop API.",
                "behavior": "delegates_to",
                "target_method": "branch",
            }
        )
    elif class_name == "LlmAgent":
        extras.append(
            {
                "name": "tool",
                "signature": "(self, fn_or_tool: Callable | BaseTool) -> Self",
                "doc": "Add a single tool (appends). Multiple .tool() calls accumulate. Use .tools() to replace the full list.",
                "behavior": "list_append",
                "target_field": "tools",
            }
        )
        extras.append(
            {
                "name": "apply",
                "signature": "(self, stack: MiddlewareStack) -> Self",
                "doc": "Apply a reusable middleware stack (bulk callback registration).",
            }
        )
        extras.append(
            {
                "name": "transfer_to",
                "signature": "(self, agent: BaseAgent | AgentBuilder) -> Self",
                "doc": "Add a sub-agent as a transfer target (LLM decides when to hand off).",
                "behavior": "list_append",
                "target_field": "sub_agents",
            }
        )
        extras.append(
            {
                "name": "delegate_to",
                "signature": "(self, agent) -> Self",
                "doc": "Wrap another agent as a callable AgentTool and add it to this agent's tools.",
                "behavior": "runtime_helper",
                "helper_func": "add_delegate_to",
            }
        )

    return extras


# ---------------------------------------------------------------------------
# TYPE-DRIVEN EXTRAS INFERENCE (A3)
# ---------------------------------------------------------------------------


def _singular_name(plural_field: str) -> str:
    """Derive the singular form of a plural field name.

    ``tools`` -> ``tool``, ``sub_agents`` -> ``sub_agent``,
    ``plugins`` -> ``plugin``.

    Simple rule: strip trailing ``"s"`` unless the name ends in ``"ss"``.
    """
    if plural_field.endswith("ss"):
        return plural_field
    if plural_field.endswith("s"):
        return plural_field[:-1]
    return plural_field


def _inner_type_name(type_str: str) -> str:
    """Extract the inner element type from ``list[X]``.

    Handles ``Union[list[X], NoneType]`` and ``list[X] | None`` by
    unwrapping the optional layer first.

    Returns the raw *type_str* unchanged if it is not a list type.
    """
    s = _unwrap_optional(type_str)
    for prefix in ("list[", "List["):
        if s.startswith(prefix) and s.endswith("]"):
            return s[len(prefix) : -1].strip()
    return s


_CONTAINER_ALIASES: dict[str, dict[str, str | list[str]]] = {
    "SequentialAgent": {"sub_agent": "step"},
    "LoopAgent": {"sub_agent": "step"},
    "ParallelAgent": {"sub_agent": ["branch", "step"]},  # branch is primary, step delegates to branch
    "SequentialAgentConfig": {"sub_agent": "step"},
    "LoopAgentConfig": {"sub_agent": "step"},
    "ParallelAgentConfig": {"sub_agent": ["branch", "step"]},
}

# Classes where the generic singular form should be *replaced* by a semantic
# verb, not aliased. Unlike ``_CONTAINER_ALIASES`` (which keeps the generic
# singular as a delegate), these entries suppress the generic form entirely —
# the primary name is the only name. Used for renames like ``sub_agent`` →
# ``transfer_to`` on agent-like classes, where the old name adds noise
# without carrying information the primary name doesn't already convey.
_CONTAINER_RENAMES: dict[str, dict[str, str]] = {
    "BaseAgent": {"sub_agent": "transfer_to"},
    "LlmAgent": {"sub_agent": "transfer_to"},
    "RemoteA2aAgent": {"sub_agent": "transfer_to"},
    "BaseAgentConfig": {"sub_agent": "transfer_to"},
    "LlmAgentConfig": {"sub_agent": "transfer_to"},
}


def infer_extras(class_name: str, tag: str, fields: list[dict]) -> list[dict]:
    """Infer extra (non-field) methods from field type information.

    Any ``list[ComplexType]`` field produces a singular adder method with
    ``list_append`` behavior.  For well-known container agents the method
    is given a semantic name (step, branch) via ``_CONTAINER_ALIASES``;
    when the alias differs from the generic singular, **both** names are
    emitted.
    """
    extras: list[dict] = []
    seen_names: set[str] = set()

    for f in fields:
        fname = f["name"]
        ftype = f.get("type_str", "")

        if not _is_list_of_complex_type(ftype):
            continue

        singular = _singular_name(fname)
        inner = _inner_type_name(ftype)

        # Build the default signature and doc for list_append extras
        sig = f"(self, value: {inner}) -> Self"
        doc = f"Append to ``{fname}`` (lazy — built at .build() time)."

        # Check for a rename (primary-only, no generic singular fallback)
        rename_map = _CONTAINER_RENAMES.get(class_name, {})
        renamed = rename_map.get(singular)
        if renamed:
            if renamed not in seen_names:
                extras.append(
                    {
                        "name": renamed,
                        "signature": sig,
                        "doc": doc,
                        "behavior": "list_append",
                        "target_field": fname,
                    }
                )
                seen_names.add(renamed)
            continue

        # Check for a semantic alias override
        alias_map = _CONTAINER_ALIASES.get(class_name, {})
        alias_spec = alias_map.get(singular)  # e.g. "step" or ["branch", "step"]

        if alias_spec:
            # Normalize to list: first element is primary (gets the body), rest delegate
            aliases = [alias_spec] if isinstance(alias_spec, str) else list(alias_spec)
            primary = aliases[0]

            # Primary alias gets the real body
            if primary not in seen_names:
                extras.append(
                    {
                        "name": primary,
                        "signature": sig,
                        "doc": doc,
                        "behavior": "list_append",
                        "target_field": fname,
                    }
                )
                seen_names.add(primary)

            # Secondary aliases delegate to primary
            for secondary in aliases[1:]:
                if secondary not in seen_names:
                    extras.append(
                        {
                            "name": secondary,
                            "signature": sig,
                            "doc": f"Alias for .{primary}() — consistent API across workflow builders.",
                            "behavior": "delegates_to",
                            "target_method": primary,
                        }
                    )
                    seen_names.add(secondary)

            # The generic singular (e.g. ``sub_agent``) is intentionally NOT
            # emitted. Aliases like ``step`` / ``branch`` already cover the
            # semantics for workflow builders; keeping ``sub_agent`` around
            # as a delegate just adds a second way to say the same thing.
        else:
            # No alias — just the singular adder
            if singular not in seen_names:
                extras.append(
                    {
                        "name": singular,
                        "signature": sig,
                        "doc": doc,
                        "behavior": "list_append",
                        "target_field": fname,
                    }
                )
                seen_names.add(singular)

    return extras


def merge_extras(inferred: list[dict], manual: list[dict]) -> list[dict]:
    """Merge inferred extras with manual overrides.

    Manual entries win on name conflicts (matched by the ``name`` field).
    """
    manual_names = {e["name"] for e in manual}
    merged = [e for e in inferred if e["name"] not in manual_names]
    merged.extend(manual)
    return merged
