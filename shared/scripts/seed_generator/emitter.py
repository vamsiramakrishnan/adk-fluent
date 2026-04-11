"""TOML emitter — serialize builder definitions to seed.toml format."""

from __future__ import annotations

from datetime import UTC, datetime


def _quote_toml_string(s: str) -> str:
    """Properly quote a string for TOML output."""
    if "\n" in s or '"' in s:
        return f'"""{s}"""'
    return f'"{s}"'


def _emit_string_list(items: list[str]) -> str:
    """Format a list of strings for TOML."""
    if not items:
        return "[]"
    inner = ", ".join(f'"{item}"' for item in items)
    return f"[{inner}]"


def emit_seed_toml(
    builders: list[dict],
    global_config: dict,
    adk_version: str = "unknown",
) -> str:
    """Emit a complete seed.toml string from builder definitions and global config.

    Args:
        builders: List of builder dicts with keys: name, source_class, output_module,
                  doc, constructor_args, aliases, callback_aliases, extra_skip_fields,
                  terminals, extras, tag.
        global_config: Dict with keys: skip_fields, additive_fields, list_extend_fields.
        adk_version: ADK version string for the meta section.

    Returns:
        A valid TOML string.
    """
    lines: list[str] = []

    # Meta section
    lines.append("[meta]")
    lines.append('adk_package = "google-adk"')
    lines.append(f'adk_version = "{adk_version}"')
    lines.append(f'generated_at = "{datetime.now(UTC).isoformat()}"')
    lines.append('min_python = "3.11"')
    lines.append('output_package = "adk_fluent"')
    lines.append('output_dir = "src/adk_fluent"')
    lines.append("")

    # Global section
    lines.append("[global]")
    lines.append(f"skip_fields = {_emit_string_list(global_config.get('skip_fields', []))}")
    lines.append(f"additive_fields = {_emit_string_list(global_config.get('additive_fields', []))}")
    lines.append(f"list_extend_fields = {_emit_string_list(global_config.get('list_extend_fields', []))}")
    lines.append("")

    # Field docstring overrides
    field_docs = global_config.get("field_docs", {})
    if field_docs:
        lines.append("[field_docs]")
        for field_name, doc_str in sorted(field_docs.items()):
            lines.append(f"{field_name} = {_quote_toml_string(doc_str)}")
        lines.append("")

    # Builder sections
    for builder in builders:
        name = builder["name"]
        lines.append(f"[builders.{name}]")
        lines.append(f'source_class = "{builder["source_class"]}"')
        lines.append(f'output_module = "{builder["output_module"]}"')
        lines.append(f"doc = {_quote_toml_string(builder.get('doc', ''))}")
        lines.append(f'auto_tag = "{builder.get("tag", "data")}"')
        lines.append(f"constructor_args = {_emit_string_list(builder.get('constructor_args', []))}")
        opt_args = builder.get("optional_constructor_args")
        if opt_args:
            lines.append(f"optional_constructor_args = {_emit_string_list(opt_args)}")
        lines.append(f"extra_skip_fields = {_emit_string_list(builder.get('extra_skip_fields', []))}")
        lines.append("")

        # Aliases
        aliases = builder.get("aliases", {})
        if aliases:
            lines.append(f"[builders.{name}.aliases]")
            for alias, field_name in sorted(aliases.items()):
                lines.append(f'{alias} = "{field_name}"')
            lines.append("")

        # Callback aliases
        cb_aliases = builder.get("callback_aliases", {})
        if cb_aliases:
            lines.append(f"[builders.{name}.callback_aliases]")
            for alias, field_name in sorted(cb_aliases.items()):
                lines.append(f'{alias} = "{field_name}"')
            lines.append("")

        # Deprecated aliases
        dep_aliases = builder.get("deprecated_aliases", {})
        if dep_aliases:
            lines.append(f"[builders.{name}.deprecated_aliases]")
            for dep_name, dep_config in sorted(dep_aliases.items()):
                if isinstance(dep_config, dict):
                    parts = []
                    for k, v in sorted(dep_config.items()):
                        parts.append(f'{k} = "{v}"')
                    lines.append(f"{dep_name} = {{ {', '.join(parts)} }}")
                else:
                    lines.append(f'{dep_name} = "{dep_config}"')
            lines.append("")

        # Terminals
        for terminal in builder.get("terminals", []):
            lines.append(f"[[builders.{name}.terminals]]")
            lines.append(f'name = "{terminal["name"]}"')
            lines.append(f'returns = "{terminal["returns"]}"')
            if "doc" in terminal:
                lines.append(f"doc = {_quote_toml_string(terminal['doc'])}")
            lines.append("")

        # Extras
        for extra in builder.get("extras", []):
            lines.append(f"[[builders.{name}.extras]]")
            lines.append(f'name = "{extra["name"]}"')
            if "signature" in extra:
                lines.append(f'signature = "{extra["signature"]}"')
            if "doc" in extra:
                lines.append(f"doc = {_quote_toml_string(extra['doc'])}")
            if "behavior" in extra:
                lines.append(f'behavior = "{extra["behavior"]}"')
            if "target_field" in extra:
                lines.append(f'target_field = "{extra["target_field"]}"')
            if "target_fields" in extra:
                lines.append(f"target_fields = {_emit_string_list(extra['target_fields'])}")
            if "helper_func" in extra:
                lines.append(f'helper_func = "{extra["helper_func"]}"')
            if "target_method" in extra:
                lines.append(f'target_method = "{extra["target_method"]}"')
            if "example" in extra:
                lines.append(f"example = '''\n{extra['example'].strip()}\n'''")
            if "see_also" in extra:
                lines.append(f"see_also = {_emit_string_list(extra['see_also'])}")
            lines.append("")

    return "\n".join(lines) + "\n"
