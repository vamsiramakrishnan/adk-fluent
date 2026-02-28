"""Extra methods engine — generate non-field helper methods for builders.

Produces methods like .tool(), .step(), .branch(), .sub_agent(), .delegate()
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
                "behavior": "list_append",
                "target_field": "sub_agents",
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
                "name": "sub_agent",
                "signature": "(self, agent: BaseAgent | AgentBuilder) -> Self",
                "doc": "Add a sub-agent (appends). Multiple .sub_agent() calls accumulate.",
                "behavior": "list_append",
                "target_field": "sub_agents",
            }
        )
        extras.append(
            {
                "name": "member",
                "signature": "(self, agent: BaseAgent | AgentBuilder) -> Self",
                "doc": "Deprecated: use .sub_agent() instead. Add a sub-agent for coordinator pattern.",
                "behavior": "deprecation_alias",
                "target_method": "sub_agent",
            }
        )
        extras.append(
            {
                "name": "delegate",
                "signature": "(self, agent) -> Self",
                "doc": "Add an agent as a delegatable tool (wraps in AgentTool). The coordinator LLM can route to this agent.",
                "behavior": "runtime_helper",
                "helper_func": "delegate_agent",
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


_CONTAINER_ALIASES: dict[str, dict[str, str]] = {
    "SequentialAgent": {"sub_agent": "step"},
    "LoopAgent": {"sub_agent": "step"},
    "ParallelAgent": {"sub_agent": "branch"},
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

        # Check for a semantic alias override
        alias_map = _CONTAINER_ALIASES.get(class_name, {})
        alias = alias_map.get(singular)  # e.g. "step" for sub_agent

        if alias and alias != singular:
            # Emit the semantic alias first
            if alias not in seen_names:
                extras.append(
                    {
                        "name": alias,
                        "signature": sig,
                        "doc": doc,
                        "behavior": "list_append",
                        "target_field": fname,
                    }
                )
                seen_names.add(alias)
            # Also emit the generic singular form
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
