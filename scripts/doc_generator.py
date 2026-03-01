#!/usr/bin/env python3
"""
Documentation generator for adk-fluent.

Reads manifest + seed (via generator's BuilderSpec) and produces:
  1. API reference Markdown (one per module + index) — MyST-flavored
  2. Cookbook Markdown (from annotated example files) — sphinx-design tabs
  3. Migration guide (class + field mapping tables) — with cross-refs

Usage:
    python scripts/doc_generator.py seeds/seed.toml manifest.json
    python scripts/doc_generator.py seeds/seed.toml manifest.json --api-only
    python scripts/doc_generator.py seeds/seed.toml manifest.json --cookbook-only
    python scripts/doc_generator.py seeds/seed.toml manifest.json --migration-only
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import importlib.util
import inspect
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

with contextlib.suppress(ImportError):
    import tomllib  # noqa: F401

# Import BuilderSpec resolution from generator (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from generator import BuilderSpec, parse_manifest, parse_seed, resolve_builder_specs

# ---------------------------------------------------------------------------
# NAMESPACE MODULE SPECS (P, C, S, A, M, T)
# ---------------------------------------------------------------------------


@dataclass
class NamespaceSpec:
    """Specification for a hand-written namespace module to document."""

    letter: str  # "P", "C", "S", etc.
    module_path: str  # "adk_fluent._prompt"
    class_name: str  # "P"
    output_stem: str  # "prompt" (-> prompt.md)
    display_name: str  # "Prompt Composition"
    base_type: str  # "PTransform"
    operators: list[tuple[str, str, str]]  # [("op", "name", "description")]


@dataclass
class NamespaceMethod:
    """A public static method extracted from a namespace class."""

    name: str
    signature_str: str  # "(text: str) -> PRole"
    params: list[tuple[str, str, str]]  # [(name, type_str, default_repr)]
    return_type: str
    docstring: str
    category: str  # from phase/section comments


NAMESPACE_MODULES: list[NamespaceSpec] = [
    NamespaceSpec(
        letter="P",
        module_path="adk_fluent._prompt",
        class_name="P",
        output_stem="prompt",
        display_name="Prompt Composition",
        base_type="PTransform",
        operators=[
            ("+", "union (PComposite)", "Merge prompt sections into a composite"),
            ("|", "pipe (PPipe)", "Post-process the compiled output"),
        ],
    ),
    NamespaceSpec(
        letter="C",
        module_path="adk_fluent._context",
        class_name="C",
        output_stem="context",
        display_name="Context Engineering",
        base_type="CTransform",
        operators=[
            ("+", "union (CComposite)", "Combine context transforms"),
            ("|", "pipe (CPipe)", "Chain context processing"),
        ],
    ),
    NamespaceSpec(
        letter="S",
        module_path="adk_fluent._transforms",
        class_name="S",
        output_stem="transforms",
        display_name="State Transforms",
        base_type="STransform",
        operators=[
            (">>", "chain", "Sequential — first runs, state updated, second runs on result"),
            ("+", "combine", "Both run on original state, results merge"),
        ],
    ),
    NamespaceSpec(
        letter="A",
        module_path="adk_fluent._artifacts",
        class_name="A",
        output_stem="artifacts",
        display_name="Artifact Operations",
        base_type="ATransform",
        operators=[],
    ),
    NamespaceSpec(
        letter="M",
        module_path="adk_fluent._middleware",
        class_name="M",
        output_stem="middleware",
        display_name="Middleware Composition",
        base_type="MComposite",
        operators=[
            ("|", "compose (MComposite)", "Stack middleware into a chain"),
        ],
    ),
    NamespaceSpec(
        letter="T",
        module_path="adk_fluent._tools",
        class_name="T",
        output_stem="tools",
        display_name="Tool Composition",
        base_type="TComposite",
        operators=[
            ("|", "compose (TComposite)", "Combine tools into a collection"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _anchor_id(name: str) -> str:
    """Convert a builder name to a lowercase anchor id for MyST targets."""
    return name.lower().replace(" ", "-")


def _usage_example(spec: BuilderSpec) -> str:
    """Generate a short inline usage example (2-3 lines) for a builder."""
    lines: list[str] = []
    args_str = ", ".join(f'"{a}_value"' for a in spec.constructor_args)
    chain = f"{spec.name}({args_str})"

    # Add one representative chained call if available
    if spec.aliases:
        first_alias = next(iter(spec.aliases))
        chain += f'\n    .{first_alias}("...")'
    elif spec.extras:
        first_extra = spec.extras[0]["name"]
        chain += f"\n    .{first_extra}(...)"

    chain += "\n    .build()"

    lines.append("```python")
    lines.append(f"from adk_fluent import {spec.name}")
    lines.append("")
    lines.append("result = (")
    lines.append(f"    {chain}")
    lines.append(")")
    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# API REFERENCE GENERATION
# ---------------------------------------------------------------------------


def _extract_doc_example(doc: str, spec_name: str, method_name: str, is_callback: bool) -> tuple[str, str]:
    """Splits a docstring, strips native examples, and synthesizes a fluent example."""
    if not doc:
        doc = ""
    parts = re.split(r"(?:^|\n)\s*Examples?:\s*(?:\n|$)", doc, maxsplit=1, flags=re.IGNORECASE)
    main_doc = parts[0].strip()
    main_doc = _md_normalize(main_doc)

    # Auto-synthesize a snippet based on the builder context
    var_name = spec_name.lower()
    if var_name.endswith("config"):
        var_name = "config"
    elif var_name in ("agent", "baseagent", "llmagent"):
        var_name = "agent"

    # Heuristics for realistic dummy values
    val = '"..."'
    if method_name in ("model",):
        val = '"gemini-2.5-flash"'
    elif method_name in ("instruct", "static"):
        val = '"You are a helpful assistant."'
    elif method_name in ("name",):
        val = '"my_agent"'
    elif method_name in ("tool",):
        val = "my_function"
    elif method_name in ("history", "include_history"):
        val = '"none"'
    elif method_name in ("outputs", "writes"):
        val = '"result_key"'
    elif is_callback or "callback" in method_name:
        val = "my_callback_fn"
        if method_name.endswith("_if"):
            val = "condition, my_callback_fn"

    if spec_name in ("P", "C", "S", "M", "T", "A"):  # namespace modules
        example_code = f"{spec_name}.{method_name}({val})"
    else:
        # Default chain example
        example_code = f'{var_name} = {spec_name}("{var_name}").{method_name}({val})'

    return main_doc, example_code


@dataclass
class ApiMethod:
    name: str
    signature: str
    doc: str
    example: str
    category: str
    notes: list[str] = field(default_factory=list)


def _categorize_method(method_name: str, is_callback: bool, spec_name: str) -> str:
    CONTROL_FLOW = {
        "proceed_if",
        "loop_until",
        "retry_if",
        "timeout",
        "delegate",
        "isolate",
        "step",
        "branch",
        "build",
        "ask",
        "ask_async",
        "stream",
        "events",
        "map",
        "map_async",
        "session",
        "test",
        "clone",
        "with_",
        "validate",
        "explain",
        "until",
        "max_iterations",
    }
    TRANSFORMS = {"pick", "rename", "merge", "default", "drop", "transform", "compute", "guard", "log"}
    CORE_CONFIG = {
        "model",
        "instruct",
        "static",
        "describe",
        "history",
        "outputs",
        "tool",
        "sub_agent",
        "role",
        "task",
        "name",
        "inject_context",
        "global_instruct",
        "schema",
        "branch",
    }
    if method_name in CONTROL_FLOW:
        return "Control Flow & Execution"
    if method_name in TRANSFORMS and spec_name == "S":
        return "State Transforms"
    if is_callback or method_name == "guardrail":
        return "Callbacks"
    if method_name in CORE_CONFIG:
        return "Core Configuration"
    return "Configuration"


def gen_api_reference_for_builder(spec: BuilderSpec) -> str:
    """Generate MyST-flavored Markdown API reference for a single builder."""
    lines: list[str] = []

    # --- MyST target anchor ---
    _anchor = _anchor_id(spec.name)
    lines.append(f"(builder-{spec.name})=")
    lines.append(f"## {spec.name}")
    lines.append("")

    if spec.is_composite:
        lines.append("> Composite builder (no single ADK class)")
    elif spec.is_standalone:
        lines.append("> Standalone builder (no ADK class)")
    else:
        lines.append(f"> Fluent builder for `{spec.source_class}`")
    lines.append("")

    if spec.doc:
        lines.append(spec.doc)
        lines.append("")

    # --- Inline usage example ---
    lines.append("**Quick start:**")
    lines.append("")
    lines.append(_usage_example(spec))
    lines.append("")

    # --- Constructor ---
    if spec.constructor_args:
        lines.append("### Constructor")
        lines.append("")
        # Full signature with type hints
        sig_parts = []
        for arg in spec.constructor_args:
            arg_type = "str"
            if spec.inspection_mode == "init_signature" and spec.init_params:
                param_info = next((p for p in spec.init_params if p["name"] == arg), None)
                if param_info:
                    arg_type = param_info.get("type_str", "str")
            else:
                field_info = next((f for f in spec.fields if f["name"] == arg), None)
                if field_info:
                    arg_type = field_info["type_str"]
            sig_parts.append(f"{arg}: {arg_type}")

        lines.append("```python")
        lines.append(f"{spec.name}({', '.join(sig_parts)})")
        lines.append("```")
        lines.append("")
        lines.append("| Argument | Type |")
        lines.append("|----------|------|")
        for arg in spec.constructor_args:
            arg_type = "str"
            if spec.inspection_mode == "init_signature" and spec.init_params:
                param_info = next((p for p in spec.init_params if p["name"] == arg), None)
                if param_info:
                    arg_type = param_info.get("type_str", "str")
            else:
                field_info = next((f for f in spec.fields if f["name"] == arg), None)
                if field_info:
                    arg_type = field_info["type_str"]
            safe_type = (
                f"{{py:class}}`{arg_type}`"
                if arg_type in ("str", "bool", "int", "float", "list", "dict", "set")
                else f"`{arg_type}`"
            )
            lines.append(f"| `{arg}` | {safe_type} |")
        lines.append("")

    methods: list[ApiMethod] = []

    # --- Alias Methods ---
    if spec.aliases:
        for fluent_name, field_name in spec.aliases.items():
            field_info = next((f for f in spec.fields if f["name"] == field_name), None)
            type_hint = field_info["type_str"] if field_info else "Any"
            doc = spec.field_docs.get(field_name, "")
            if not doc and field_info:
                doc = field_info.get("description", "")
            if not doc:
                doc = f"Set the `{field_name}` field."

            main_doc, example_code = _extract_doc_example(doc, spec.name, fluent_name, False)
            category = _categorize_method(fluent_name, False, spec.name)

            methods.append(
                ApiMethod(
                    name=fluent_name,
                    signature=f"(value: {type_hint}) -> Self",
                    doc=f"- **Maps to:** `{field_name}`\n- {main_doc}",
                    example=example_code,
                    category=category,
                )
            )

    # --- Callback Methods ---
    if spec.callback_aliases:
        for short_name, full_name in spec.callback_aliases.items():
            category = _categorize_method(short_name, True, spec.name)
            _, example_code = _extract_doc_example("", spec.name, short_name, True)
            _, example_code_if = _extract_doc_example("", spec.name, f"{short_name}_if", True)

            methods.append(
                ApiMethod(
                    name=short_name,
                    signature="(*fns: Callable) -> Self",
                    doc=f"Append callback(s) to `{full_name}`.",
                    example=example_code,
                    category=category,
                    notes=[
                        "Multiple calls accumulate. Each invocation appends to the callback list rather than replacing previous callbacks."
                    ],
                )
            )
            methods.append(
                ApiMethod(
                    name=f"{short_name}_if",
                    signature="(condition: bool, fn: Callable) -> Self",
                    doc=f"Append callback to `{full_name}` only if `condition` is `True`.",
                    example=example_code_if,
                    category=category,
                    notes=[],
                )
            )

    # --- Extra Methods ---
    if spec.extras:
        for extra in spec.extras:
            name = extra["name"]
            sig = extra.get("signature", "(self) -> Self")
            display_sig = sig.replace("(self, ", "(").replace("(self)", "()")

            doc = extra.get("doc", "")
            main_doc, example_code = _extract_doc_example(doc, spec.name, name, False)
            if extra.get("example"):
                example_code = extra["example"].strip()

            see_also = extra.get("see_also", [])
            notes = []
            if see_also:
                see_also_links = ", ".join(f"`{ref}`" for ref in see_also)
                notes.append(f"**See also:** {see_also_links}")

            category = _categorize_method(name, False, spec.name)
            methods.append(
                ApiMethod(
                    name=name, signature=display_sig, doc=main_doc, example=example_code, category=category, notes=notes
                )
            )

    # --- Terminal Methods ---
    if spec.terminals:
        for terminal in spec.terminals:
            t_name = terminal["name"]
            if "signature" in terminal:
                display_sig = terminal["signature"].replace("(self, ", "(").replace("(self)", "()")
            elif "returns" in terminal:
                display_sig = f"() -> {terminal['returns']}"
            else:
                display_sig = "()"

            doc = terminal.get("doc", "")
            main_doc, example_code = _extract_doc_example(doc, spec.name, t_name, False)
            category = "Control Flow & Execution"

            methods.append(
                ApiMethod(
                    name=t_name,
                    signature=display_sig,
                    doc=main_doc,
                    example=example_code,
                    category=category,
                )
            )

    # Render grouped methods
    groups = defaultdict(list)
    for m in methods:
        groups[m.category].append(m)

    for category in [
        "Core Configuration",
        "Configuration",
        "Callbacks",
        "State Transforms",
        "Control Flow & Execution",
    ]:
        if category in groups:
            lines.append(f"### {category}")
            lines.append("")
            for m in sorted(groups[category], key=lambda x: x.name):
                badge_color = (
                    "primary" if "Control Flow" in m.category else ("success" if "Core" in m.category else "info")
                )
                lines.append(f"#### `.{m.name}{m.signature}` {{bdg-{badge_color}}}`{m.category}`")
                lines.append("")
                if m.doc:
                    lines.append(m.doc)
                    lines.append("")
                for note in m.notes:
                    if note.startswith("**See also"):
                        lines.append(note)
                        lines.append("")
                    else:
                        lines.append(":::{note}")
                        lines.append(note)
                        lines.append(":::")
                        lines.append("")
                if m.example:
                    lines.append("**Example:**")
                    lines.append("")
                    lines.append("```python")
                    lines.append(m.example)
                    lines.append("```")
                    lines.append("")

    # --- Forwarded Fields ---
    if not spec.is_composite and not spec.is_standalone:
        aliased_fields = set(spec.aliases.values())
        callback_fields = set(spec.callback_aliases.values())
        extra_names = {e["name"] for e in spec.extras}

        forwarded = []
        if spec.inspection_mode == "init_signature" and spec.init_params:
            for param in spec.init_params:
                pname = param["name"]
                if pname in ("self", "args", "kwargs", "kwds"):
                    continue
                if pname in spec.skip_fields:
                    continue
                if pname in aliased_fields:
                    continue
                if pname in callback_fields:
                    continue
                if pname in extra_names:
                    continue
                if pname in spec.constructor_args:
                    continue
                forwarded.append((pname, param.get("type_str", "Any")))
        else:
            for field in spec.fields:
                fname = field["name"]
                if fname in spec.skip_fields:
                    continue
                if fname in aliased_fields:
                    continue
                if fname in callback_fields:
                    continue
                if fname in extra_names:
                    continue
                if fname in spec.constructor_args:
                    continue
                forwarded.append((fname, field["type_str"]))

        if forwarded:
            lines.append("### Forwarded Fields")
            lines.append("")
            lines.append("These fields are available via `__getattr__` forwarding.")
            lines.append("")
            lines.append("| Field | Type |")
            lines.append("|-------|------|")
            for fname, ftype in forwarded:
                safe_type = (
                    f"{{py:class}}`{ftype}`"
                    if ftype in ("str", "bool", "int", "float", "list", "dict", "set")
                    else f"`{ftype}`"
                )
                lines.append(f"| `.{fname}(value)` | {safe_type} |")
            lines.append("")

    return "\n".join(lines)


def gen_api_reference_module(specs: list[BuilderSpec], module_name: str) -> str:
    """Generate API reference Markdown for an entire module (multiple builders).

    Includes a table of contents listing all builders at the top.
    """
    parts: list[str] = []
    parts.append(f"# Module: `{module_name}`")
    parts.append("")

    # --- Table of contents ---
    parts.append("## Builders in this module")
    parts.append("")
    parts.append("| Builder | Description |")
    parts.append("|---------|-------------|")
    for spec in specs:
        doc_short = spec.doc.split(".")[0] + "." if spec.doc else ""
        parts.append(f"| [{spec.name}](builder-{spec.name}) | {doc_short} |")
    parts.append("")

    # --- Builder sections ---
    for i, spec in enumerate(specs):
        if i > 0:
            parts.append("---")
            parts.append("")
        parts.append(gen_api_reference_for_builder(spec))

    return "\n".join(parts)


def gen_api_index(
    by_module: dict[str, list[BuilderSpec]],
    namespace_specs: list[NamespaceSpec] | None = None,
) -> str:
    """Generate docs/generated/api/index.md with module summary and toctree."""
    lines: list[str] = []

    total_builders = sum(len(specs) for specs in by_module.values())

    lines.append("# API Reference")
    lines.append("")
    lines.append(f"Complete API reference for all **{total_builders} builders** across")
    lines.append(f"**{len(by_module)} modules**.")
    lines.append("")

    # --- Module summary table ---
    lines.append("## Modules")
    lines.append("")
    lines.append("| Module | Builders | Link |")
    lines.append("|--------|----------|------|")
    for module_name in sorted(by_module.keys()):
        count = len(by_module[module_name])
        lines.append(f"| `{module_name}` | {count} | [{module_name}]({module_name}.md) |")

    # Append namespace modules to the table
    if namespace_specs:
        for ns in namespace_specs:
            lines.append(f"| `{ns.output_stem}` | {ns.letter} | [{ns.output_stem}]({ns.output_stem}.md) |")
    lines.append("")

    # --- Toctree ---
    lines.append("```{toctree}")
    lines.append(":hidden:")
    lines.append("")
    for module_name in sorted(by_module.keys()):
        lines.append(module_name)
    if namespace_specs:
        for ns in namespace_specs:
            lines.append(ns.output_stem)
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# NAMESPACE MODULE INTROSPECTION & GENERATION
# ---------------------------------------------------------------------------


def _md_normalize(text: str) -> str:
    """Normalize reStructuredText conventions in docstrings for Markdown.

    - Convert ``double backticks`` to `single backticks`
    - Convert Args:/Returns: sections to markdown lists
    - Convert Note:/Warning: sections to admonitions
    - Escape bare [ ] in body text (not inside backticks)
    - Convert :: code-block markers to plain colons
    """
    if not text:
        return ""

    # 1. Format Google-style headers (Args, Returns, Raises, Yields)
    text = re.sub(r"(?:^|\n)(Args|Arguments|Returns|Raises|Yields):\s*\n", r"\n**\1:**\n\n", text)

    # Convert indented argument lines: "    param_name (type): description" to "- **param_name** *(type)*: description"
    def _format_args(m):
        lines = m.group(0).split("\n")
        out = []
        for line in lines:
            if not line.strip():
                out.append(line)
                continue
            if line.startswith("    ") or line.startswith("\t"):
                # Detect param: desc or param (type): desc
                arg_match = re.match(r"^\s+([a-zA-Z0-9_]+)\s*(?:\(([^)]+)\))?\s*:\s*(.*)", line)
                if arg_match:
                    name, typ, desc = arg_match.groups()
                    if typ:
                        out.append(f"- **`{name}`** (*{typ}*): {desc}")
                    else:
                        out.append(f"- **`{name}`**: {desc}")
                else:
                    out.append(f"  {line.strip()}")  # Continued description
            else:
                out.append(line)
        return "\n".join(out)

    text = re.sub(r"(?:\n\*\*Args:\*\*\n\n|\n\*\*Arguments:\*\*\n\n)(?:[ \t]+.+\n?)+", _format_args, text)

    # 2. Convert Note: and Warning: to MyST admonitions
    def _format_admonition(match):
        adm_type = match.group(1).lower()
        content = match.group(2).strip()
        # remove hanging indents from the content
        content = re.sub(r"\n\s+", "\n", content)
        return f"\n:::{{{adm_type}}}\n{content}\n:::\n"

    text = re.sub(r"(?:^|\n)(Note|Warning):\s*((?:(?!\n\n)[^\n]+\n?)+)", _format_admonition, text)

    # 3. Convert ``foo`` -> `foo`
    text = re.sub(r"``(.+?)``", r"`\1`", text)

    # 4. Trailing :: (rst literal block) -> :
    text = re.sub(r"::\s*$", ":", text, flags=re.MULTILINE)

    # 5. Escape [ ] outside backtick spans so mdformat doesn't touch them
    parts = re.split(r"(`[^`]+`)", text)
    result: list[str] = []
    for part in parts:
        if part.startswith("`") and part.endswith("`"):
            result.append(part)  # inside backticks, leave as-is
        else:
            # Escape [ and ] that aren't part of markdown links
            part = re.sub(r"\[(?![^\]]*\]\()", r"\\[", part)
            part = re.sub(r"(?<!\])\](?!\()", r"\\]", part)
            result.append(part)
    return "".join(result)


def _md_table(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    """Build a markdown table with mdformat-compatible column alignment."""
    n_cols = len(header)
    # Compute column widths (min width from header and all rows)
    widths = [len(h) for h in header]
    for row in rows:
        for i in range(n_cols):
            widths[i] = max(widths[i], len(row[i]))

    def _pad_row(cells: tuple[str, ...]) -> str:
        parts = [cells[i].ljust(widths[i]) for i in range(n_cols)]
        return "| " + " | ".join(parts) + " |"

    result: list[str] = []
    result.append(_pad_row(header))
    separator = "| " + " | ".join("-" * w for w in widths) + " |"
    result.append(separator)
    for row in rows:
        result.append(_pad_row(row))
    return result


def _first_sentence(text: str) -> str:
    """Extract the first sentence from a docstring."""
    if not text:
        return ""
    # Take first line or first sentence (up to period+space or period+newline)
    line = text.split("\n\n", 1)[0].replace("\n", " ").strip()
    # Normalize rst conventions for markdown
    line = _md_normalize(line)
    m = re.match(r"(.+?\.)\s", line)
    return m.group(1) if m else line.rstrip(".")


def _format_annotation(annotation: object) -> str:
    """Render a type annotation as a readable string."""
    if annotation is inspect.Parameter.empty:
        return ""
    if isinstance(annotation, str):
        return annotation
    if hasattr(annotation, "__name__"):
        return annotation.__name__  # type: ignore[union-attr]
    return str(annotation).replace("typing.", "")


def _introspect_namespace(ns: NamespaceSpec) -> list[NamespaceMethod]:
    """Introspect a namespace class and return its public static methods."""
    mod = importlib.import_module(ns.module_path)
    cls = getattr(mod, ns.class_name)

    # --- Parse source for category comments ---
    # Matches patterns like "# --- Phase A: Core sections ---"
    # or "# --- Built-in factories ---"
    try:
        source = inspect.getsource(cls)
        source_lines = source.split("\n")
    except (OSError, TypeError):
        source_lines = []

    # Build (line_offset -> category_name) mapping
    category_map: list[tuple[int, str]] = []
    for i, line in enumerate(source_lines):
        m = re.match(r"\s*#\s*---\s*(?:Phase\s+\w+:\s*)?(.+?)\s*---\s*$", line)
        if m:
            category_map.append((i, m.group(1).strip()))

    def _category_for_line(lineno: int) -> str:
        """Find the most recent category comment before the given line offset."""
        result = "Methods"
        for offset, cat in category_map:
            if offset <= lineno:
                result = cat
            else:
                break
        return result

    # --- Extract public static methods ---
    methods: list[NamespaceMethod] = []

    # Use source order by finding def lines in the class source
    method_order: dict[str, int] = {}
    for i, line in enumerate(source_lines):
        m = re.match(r"\s+def\s+(\w+)\s*\(", line)
        if m:
            method_order[m.group(1)] = i

    members = inspect.getmembers(cls, predicate=inspect.isfunction)
    for name, func in members:
        if name.startswith("_"):
            continue

        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            continue

        # Build params list
        params: list[tuple[str, str, str]] = []
        for pname, param in sig.parameters.items():
            type_str = _format_annotation(param.annotation).strip("'")
            if param.default is not inspect.Parameter.empty:
                default_repr = repr(param.default)
            else:
                default_repr = ""
            # Prefix with * or ** for VAR_POSITIONAL/VAR_KEYWORD
            display_name = pname
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                display_name = f"*{pname}"
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                display_name = f"**{pname}"
            elif param.kind == inspect.Parameter.KEYWORD_ONLY and not default_repr:
                default_repr = ""  # keyword-only without default
            params.append((display_name, type_str, default_repr))

        return_type = _format_annotation(sig.return_annotation).strip("'")
        docstring = inspect.getdoc(func) or ""

        # Build signature string — strip quotes from stringified annotations
        sig_str = str(sig).replace("'", "")

        # Determine category from source position
        source_line = method_order.get(name, 0)
        category = _category_for_line(source_line)

        methods.append(
            NamespaceMethod(
                name=name,
                signature_str=sig_str,
                params=params,
                return_type=return_type,
                docstring=docstring,
                category=category,
            )
        )

    # Sort by source order
    methods.sort(key=lambda m: method_order.get(m.name, 999))
    return methods


def gen_namespace_reference(ns: NamespaceSpec, methods: list[NamespaceMethod]) -> str:
    """Generate MyST-flavored Markdown API reference for a namespace module."""
    lines: list[str] = []

    # --- Header ---
    lines.append(f"# Module: {ns.output_stem}")
    lines.append("")
    lines.append(f"> `from adk_fluent import {ns.letter}`")
    lines.append("")

    # Class docstring (first paragraph)
    mod = importlib.import_module(ns.module_path)
    cls = getattr(mod, ns.class_name)
    class_doc = inspect.getdoc(cls) or ""
    if class_doc:
        first_para = class_doc.split("\n\n", 1)[0].strip()
        lines.append(_md_normalize(first_para))
        lines.append("")

    # --- Quick Reference Table (mdformat-aligned) ---
    lines.append("## Quick Reference")
    lines.append("")
    # Build rows first, then compute column widths for alignment
    header = ("Method", "Returns", "Description")
    rows: list[tuple[str, str, str]] = []
    for m in methods:
        compact_params = ", ".join(p[0] if not p[2] else f"{p[0]}={p[2]}" for p in m.params)
        desc = _first_sentence(m.docstring)
        ret = m.return_type or ns.base_type
        rows.append((f"`{ns.letter}.{m.name}({compact_params})`", f"`{ret}`", desc))
    lines.extend(_md_table(header, rows))
    lines.append("")

    # --- Methods grouped by category ---
    current_category = None
    for m in methods:
        if m.category != current_category:
            current_category = m.category
            lines.append(f"## {current_category}")
            lines.append("")

        # Method heading with full signature
        lines.append(f"### `{ns.letter}.{m.name}{m.signature_str}`")
        lines.append("")

        # Docstring (strip leading >>> examples for cleaner display)
        if m.docstring:
            doc_lines = m.docstring.split("\n")
            # Separate main doc from examples
            main_doc: list[str] = []
            for dl in doc_lines:
                if dl.strip().startswith(">>>"):
                    break
                main_doc.append(dl)
            doc_text = _md_normalize("\n".join(main_doc).strip())
            if doc_text:
                lines.append(doc_text)
                lines.append("")

        # Parameters
        if m.params:
            lines.append("**Parameters:**")
            lines.append("")
            for pname, ptype, pdefault in m.params:
                parts = [f"- `{pname}`"]
                if ptype:
                    # Escape brackets in type annotations for markdown
                    escaped_type = ptype.replace("[", "\\[").replace("]", "\\]")
                    parts.append(f" (*{escaped_type}*)")
                if pdefault:
                    parts.append(f" — default: `{pdefault}`")
                lines.append("".join(parts))
            lines.append("")

    # --- Composition Operators ---
    if ns.operators:
        lines.append("## Composition Operators")
        lines.append("")
        for op, op_name, op_desc in ns.operators:
            lines.append(f"### `{op}` ({op_name})")
            lines.append("")
            lines.append(op_desc)
            lines.append("")

    # --- Types table ---
    mod_all = getattr(mod, "__all__", [])
    type_entries: list[tuple[str, str]] = []
    for type_name in mod_all:
        if type_name == ns.class_name or type_name.startswith("_"):
            continue
        obj = getattr(mod, type_name, None)
        if obj is None or not isinstance(obj, type):
            continue
        type_doc = _first_sentence(inspect.getdoc(obj) or "")
        type_entries.append((type_name, _md_normalize(type_doc)))

    if type_entries:
        lines.append("## Types")
        lines.append("")
        type_rows = [(f"`{tname}`", tdoc) for tname, tdoc in type_entries]
        lines.extend(_md_table(("Type", "Description"), type_rows))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# COOKBOOK PROCESSOR
# ---------------------------------------------------------------------------


def process_cookbook_file(filepath: str) -> dict:
    """Parse an annotated cookbook example into sections."""
    text = Path(filepath).read_text()

    # Extract title from module docstring
    title_match = re.match(r'"""(.+?)"""', text, re.DOTALL)
    title = title_match.group(1).strip() if title_match else Path(filepath).stem

    sections = {"native": "", "fluent": "", "assertion": ""}
    current = None
    for line in text.split("\n"):
        if "# --- NATIVE ---" in line:
            current = "native"
            continue
        elif "# --- FLUENT ---" in line:
            current = "fluent"
            continue
        elif "# --- ASSERT ---" in line:
            current = "assertion"
            continue
        if current:
            sections[current] += line + "\n"

    return {
        "title": title,
        "native": sections["native"].strip(),
        "fluent": sections["fluent"].strip(),
        "assertion": sections["assertion"].strip(),
        "filename": Path(filepath).name,
    }


def _learn_summary(title: str) -> str:
    """Generate a 'what you'll learn' one-liner based on the cookbook title."""
    title_lower = title.lower()
    if "simple" in title_lower or "agent creation" in title_lower:
        return "How to create a basic agent with the fluent API."
    if "tool" in title_lower:
        return "How to attach tools to an agent using the fluent API."
    if "callback" in title_lower:
        return "How to register lifecycle callbacks with accumulation semantics."
    if "sequential" in title_lower or "pipeline" in title_lower:
        return "How to compose agents into a sequential pipeline."
    if "parallel" in title_lower or "fanout" in title_lower:
        return "How to run agents in parallel using FanOut."
    if "loop" in title_lower:
        return "How to create looping agent workflows."
    if "team" in title_lower or "coordinator" in title_lower:
        return "How to build a team of agents with a coordinator."
    if "stream" in title_lower:
        return "How to use streaming execution for real-time output."
    if "session" in title_lower:
        return "How to manage interactive sessions with agents."
    if "guard" in title_lower:
        return "How to attach guardrails to agent model calls."
    if "test" in title_lower:
        return "How to run inline smoke tests on agents."
    if "clone" in title_lower or "clon" in title_lower:
        return "How to clone and customize builders."
    if "ask" in title_lower or "one-shot" in title_lower or "one_shot" in title_lower:
        return "How to use one-shot execution for quick queries."
    if "preset" in title_lower:
        return "How to define and apply reusable configuration presets."
    if "operator" in title_lower or "algebra" in title_lower:
        return "How to use operator syntax for composing agents."
    if "route" in title_lower or "branch" in title_lower:
        return "How to implement conditional routing and branching."
    if "state" in title_lower:
        return "How to work with state keys and state transforms."
    if "serial" in title_lower:
        return "How to serialize and deserialize builder configurations."
    if "delegate" in title_lower:
        return "How to delegate tasks between agents."
    if "decorator" in title_lower:
        return "How to use the agent decorator pattern."
    if "output" in title_lower or "typed" in title_lower:
        return "How to work with typed outputs."
    if "fallback" in title_lower:
        return "How to implement fallback patterns."
    if "dynamic" in title_lower or "forwarding" in title_lower:
        return "How to use dynamic field forwarding."
    if "production" in title_lower or "runtime" in title_lower:
        return "How to configure agents for production runtime."
    if "validate" in title_lower or "explain" in title_lower:
        return "How to validate and explain builder configurations."
    if "variant" in title_lower:
        return "How to create builder variants."
    if "conditional" in title_lower or "gating" in title_lower:
        return "How to apply conditional gating logic."
    if "until" in title_lower:
        return "How to use loop-until patterns."
    if "function" in title_lower and "step" in title_lower:
        return "How to use plain functions as pipeline steps."
    if "dict" in title_lower and "rout" in title_lower:
        return "How to use dict-based routing."
    if "context" in title_lower and "engineer" in title_lower:
        return "How to use declarative context transforms to control what agents see."
    if "capture" in title_lower and "route" in title_lower:
        return "How to capture user input and route it to different agents."
    if "visibility" in title_lower:
        return "How to control which agent events are shown to users."
    if "contract" in title_lower and "check" in title_lower:
        return "How to verify data contracts between pipeline steps."
    return f"How to use {title.lower()} with the fluent API."


def _guess_related_api(filename: str) -> tuple[str, str] | None:
    """Guess the relevant API module from a cookbook filename."""
    stem = filename.lower()
    if "agent" in stem and "tool" not in stem:
        return ("agent", "Agent")
    if "pipeline" in stem or "sequential" in stem:
        return ("workflow", "Pipeline")
    if "fanout" in stem or "parallel" in stem:
        return ("workflow", "FanOut")
    if "loop" in stem:
        return ("workflow", "Loop")
    if "tool" in stem:
        return ("tool", "FunctionTool")
    if "session" in stem:
        return ("service", "InMemorySessionService")
    if "runtime" in stem or "production" in stem:
        return ("runtime", "Runner")
    return None


def _get_mermaid_from_cookbook(filepath: str) -> str:
    """Attempts to run the cookbook file and find a builder to generate a mermaid diagram."""
    try:
        spec = importlib.util.spec_from_file_location("mod", filepath)
        mod = importlib.util.module_from_spec(spec)

        # Monkeypatch build on all generated builder classes in adk_fluent + Route
        import adk_fluent
        from adk_fluent._routing import Route

        patched = {}
        for name in dir(adk_fluent):
            obj = getattr(adk_fluent, name)
            if isinstance(obj, type) and hasattr(obj, "build"):
                patched[obj] = obj.build

                def mock_build(self, *args, **kwargs):
                    self._mock_built = True
                    return self

                obj.build = mock_build

        # Route is already in adk_fluent namespace, so the loop above covers it.
        # Only patch if the loop missed it (shouldn't happen, but defensive).
        if Route not in patched:
            patched[Route] = Route.build
            Route.build = lambda self, *a, **kw: self

        with contextlib.suppress(Exception):
            spec.loader.exec_module(mod)

        # Unpatch
        for obj, orig_build in patched.items():
            obj.build = orig_build

        # Now find the largest/most complex builder or Route
        from adk_fluent._base import BuilderBase
        from adk_fluent._routing import Route

        best_mermaid = ""
        max_nodes = 0

        for name in dir(mod):
            obj = getattr(mod, name)
            if isinstance(obj, BuilderBase | Route):
                with contextlib.suppress(Exception):
                    mermaid = obj.to_mermaid()
                    nodes = mermaid.count("    n")  # rough heuristic
                    if nodes > max_nodes:
                        max_nodes = nodes
                        best_mermaid = mermaid

        if max_nodes >= 2:  # At least a couple of nodes
            return best_mermaid

        # Fallback: detect delegate patterns (AgentTool wrapping agents)
        # These don't produce multi-node IR but show coordinator→specialist topology
        from google.adk.tools.agent_tool import AgentTool

        for name in dir(mod):
            obj = getattr(mod, name)
            if not isinstance(obj, BuilderBase) or not obj._lists.get("tools"):
                continue
            # Filter to only AgentTool instances (not plain function tools)
            agent_tools = [t for t in obj._lists["tools"] if isinstance(t, AgentTool)]
            if len(agent_tools) < 1:
                continue
            coordinator_name = obj._config.get("name", "coordinator")
            mermaid_lines = ["graph TD"]
            mermaid_lines.append(f'    c["{coordinator_name}"]')
            for i, at in enumerate(agent_tools):
                inner = at.agent
                d_name = f"specialist_{i}"
                if isinstance(inner, BuilderBase):
                    d_name = inner._config.get("name", d_name)
                elif hasattr(inner, "name"):
                    d_name = inner.name
                mermaid_lines.append(f'    d{i}["{d_name}"]')
                mermaid_lines.append(f"    c -.->|delegates| d{i}")
            return "\n".join(mermaid_lines)

    except Exception:  # noqa: SIM105
        pass
    return ""


def cookbook_to_markdown(parsed: dict) -> str:
    """Convert parsed cookbook data to MyST Markdown with sphinx-design tabs."""
    lines: list[str] = []

    lines.append(f"# {parsed['title']}")
    lines.append("")

    # --- "What you'll learn" one-liner ---
    learn = _learn_summary(parsed["title"])
    lines.append(":::{tip} What you'll learn")
    lines.append(learn)
    lines.append(":::")
    lines.append("")

    lines.append(f"_Source: `{parsed['filename']}`_")
    lines.append("")

    # --- Optional Mermaid Diagram ---
    # We try to dynamically evaluate the file to grab the mermaid graph
    filepath = str(Path("examples/cookbook") / parsed["filename"])
    mermaid_src = _get_mermaid_from_cookbook(filepath)

    # --- Tabbed comparison + Architecture ---
    if parsed["native"] or parsed["fluent"] or mermaid_src:
        lines.append("::::{tab-set}")

        if parsed["fluent"]:
            lines.append(":::{tab-item} adk-fluent")
            lines.append("```python")
            lines.append(parsed["fluent"])
            lines.append("```")
            lines.append(":::")

        if parsed["native"]:
            lines.append(":::{tab-item} Native ADK")
            lines.append("```python")
            lines.append(parsed["native"])
            lines.append("```")
            lines.append(":::")

        if mermaid_src:
            lines.append(":::{tab-item} Architecture")
            lines.append("```mermaid")
            lines.append(mermaid_src)
            lines.append("```")
            lines.append(":::")

        lines.append("::::")
        lines.append("")

    if parsed["assertion"]:
        lines.append("## Equivalence")
        lines.append("")
        lines.append("```python")
        lines.append(parsed["assertion"])
        lines.append("```")
        lines.append("")

    # --- See also link to API reference ---
    related = _guess_related_api(parsed["filename"])
    if related:
        module_name, builder_name = related
        lines.append(":::{seealso}")
        lines.append(f"API reference: [{builder_name}](../api/{module_name}.md#builder-{builder_name})")
        lines.append(":::")
        lines.append("")

    return "\n".join(lines)


def _categorize_cookbook(filename: str) -> str:
    """Categorize a cookbook file by its numeric prefix."""
    match = re.match(r"^(\d+)", filename)
    if not match:
        return "Other"
    num = int(match.group(1))
    if num <= 7:
        return "Basics"
    elif num <= 13:
        return "Execution"
    elif num <= 20:
        return "Advanced"
    elif num <= 43:
        return "Patterns"
    elif num <= 48:
        return "v4 Features"
    else:
        return "v5.1 Features"


def gen_cookbook_index(cookbook_files: list[dict]) -> str:
    """Generate docs/generated/cookbook/index.md with categorized toctree."""
    lines: list[str] = []

    lines.append("# Cookbook")
    lines.append("")
    lines.append("Side-by-side examples comparing native ADK code with the adk-fluent")
    lines.append("equivalent. Each recipe demonstrates a specific pattern or feature.")
    lines.append("")

    lines.append(":::{note}")
    lines.append("Looking for a specific scenario? Check out the [Recipes by Use Case](recipes-by-use-case.md) guide.")
    lines.append(":::")
    lines.append("")

    # Group by category
    categories: dict[str, list[dict]] = defaultdict(list)
    for cb in cookbook_files:
        if cb["filename"] == "conftest.md" or cb["filename"] == "recipes-by-use-case.md":
            continue
        cat = _categorize_cookbook(cb["filename"])
        categories[cat].append(cb)

    # Defined order
    cat_order = ["Basics", "Execution", "Advanced", "Patterns", "v4 Features", "v5.1 Features", "Other"]
    cat_descriptions = {
        "Basics": "Foundational patterns: creating agents, adding tools, callbacks, and simple workflows.",
        "Execution": "Running agents: one-shot, streaming, cloning, testing, and sessions.",
        "Advanced": "Advanced composition: dynamic forwarding, operators, routing, and conditional logic.",
        "Patterns": "Real-world patterns: state management, presets, decorators, serialization, and more.",
        "v4 Features": "IR compilation, middleware, contracts, testing, dependency injection, and visualization.",
        "v5.1 Features": "Context engineering, visibility, memory, and contract verification.",
        "Other": "Additional examples.",
    }

    for cat in cat_order:
        if cat not in categories:
            continue
        items = categories[cat]

        lines.append(f"## {cat}")
        lines.append("")
        lines.append(cat_descriptions.get(cat, ""))
        lines.append("")

        # List items
        lines.append("````{grid} 1 2 2 2")
        lines.append("---")
        lines.append("gutter: 3")
        lines.append("---")
        for item in items:
            stem = Path(item["filename"]).stem
            # Strip numeric prefix from title for cleaner display
            display_title = re.sub(r"^\d+_\s*", "", item["title"])

            lines.append(f"```{{grid-item-card}} {display_title}")
            lines.append(f":link: {stem}")
            lines.append(":link-type: doc")
            lines.append("")
            lines.append(f"{_learn_summary(item['title'])}")
            lines.append("```")
        lines.append("````")
        lines.append("")

        # Toctree per category
        lines.append("```{toctree}")
        lines.append(":hidden:")
        lines.append("")
        for item in items:
            stem = Path(item["filename"]).stem
            lines.append(stem)
        lines.append("```")
        lines.append("")

    lines.append("```{toctree}")
    lines.append(":hidden:")
    lines.append("")
    lines.append("recipes-by-use-case")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MIGRATION GUIDE GENERATOR
# ---------------------------------------------------------------------------


def gen_migration_guide(specs: list[BuilderSpec], by_module: dict[str, list[BuilderSpec]]) -> str:
    """Generate a migration guide with class/field mapping tables,
    before/after code snippets, and cross-references to API pages."""
    lines: list[str] = []

    lines.append("# Migration Guide: Native ADK to adk-fluent")
    lines.append("")

    # --- Intro paragraph ---
    lines.append("This guide helps you migrate from the native Google ADK API to the")
    lines.append("adk-fluent builder pattern. The fluent API wraps every ADK class with a")
    lines.append("chainable builder that produces identical runtime objects. You can migrate")
    lines.append("incrementally -- fluent builders and native objects interoperate freely.")
    lines.append("")

    # --- Before/after code snippets for the 3 most common patterns ---
    lines.append("## Common Patterns: Before and After")
    lines.append("")

    # 1. Agent
    lines.append("### Agent")
    lines.append("")
    lines.append("::::{tab-set}")
    lines.append(":::{tab-item} Before (Native)")
    lines.append("```python")
    lines.append("from google.adk.agents.llm_agent import LlmAgent")
    lines.append("")
    lines.append("agent = LlmAgent(")
    lines.append('    name="helper",')
    lines.append('    model="gemini-2.5-flash",')
    lines.append('    instruction="You are a helpful assistant.",')
    lines.append('    description="A helper agent",')
    lines.append(")")
    lines.append("```")
    lines.append(":::")
    lines.append(":::{tab-item} After (Fluent)")
    lines.append("```python")
    lines.append("from adk_fluent import Agent")
    lines.append("")
    lines.append("agent = (")
    lines.append('    Agent("helper")')
    lines.append('    .model("gemini-2.5-flash")')
    lines.append('    .instruct("You are a helpful assistant.")')
    lines.append('    .describe("A helper agent")')
    lines.append("    .build()")
    lines.append(")")
    lines.append("```")
    lines.append(":::")
    lines.append("::::")
    lines.append("")

    # 2. Pipeline
    lines.append("### Pipeline (SequentialAgent)")
    lines.append("")
    lines.append("::::{tab-set}")
    lines.append(":::{tab-item} Before (Native)")
    lines.append("```python")
    lines.append("from google.adk.agents.sequential_agent import SequentialAgent")
    lines.append("from google.adk.agents.llm_agent import LlmAgent")
    lines.append("")
    lines.append("pipeline = SequentialAgent(")
    lines.append('    name="my_pipeline",')
    lines.append("    sub_agents=[")
    lines.append('        LlmAgent(name="step1", model="gemini-2.5-flash", instruction="Do step 1."),')
    lines.append('        LlmAgent(name="step2", model="gemini-2.5-flash", instruction="Do step 2."),')
    lines.append("    ],")
    lines.append(")")
    lines.append("```")
    lines.append(":::")
    lines.append(":::{tab-item} After (Fluent)")
    lines.append("```python")
    lines.append("from adk_fluent import Agent, Pipeline")
    lines.append("")
    lines.append("pipeline = (")
    lines.append('    Pipeline("my_pipeline")')
    lines.append('    .step(Agent("step1").model("gemini-2.5-flash").instruct("Do step 1."))')
    lines.append('    .step(Agent("step2").model("gemini-2.5-flash").instruct("Do step 2."))')
    lines.append("    .build()")
    lines.append(")")
    lines.append("```")
    lines.append(":::")
    lines.append("::::")
    lines.append("")

    # 3. FanOut
    lines.append("### FanOut (ParallelAgent)")
    lines.append("")
    lines.append("::::{tab-set}")
    lines.append(":::{tab-item} Before (Native)")
    lines.append("```python")
    lines.append("from google.adk.agents.parallel_agent import ParallelAgent")
    lines.append("from google.adk.agents.llm_agent import LlmAgent")
    lines.append("")
    lines.append("fanout = ParallelAgent(")
    lines.append('    name="parallel_search",')
    lines.append("    sub_agents=[")
    lines.append('        LlmAgent(name="web", model="gemini-2.5-flash", instruction="Search web."),')
    lines.append('        LlmAgent(name="db", model="gemini-2.5-flash", instruction="Search DB."),')
    lines.append("    ],")
    lines.append(")")
    lines.append("```")
    lines.append(":::")
    lines.append(":::{tab-item} After (Fluent)")
    lines.append("```python")
    lines.append("from adk_fluent import Agent, FanOut")
    lines.append("")
    lines.append("fanout = (")
    lines.append('    FanOut("parallel_search")')
    lines.append('    .branch(Agent("web").model("gemini-2.5-flash").instruct("Search web."))')
    lines.append('    .branch(Agent("db").model("gemini-2.5-flash").instruct("Search DB."))')
    lines.append("    .build()")
    lines.append(")")
    lines.append("```")
    lines.append(":::")
    lines.append("::::")
    lines.append("")

    # --- Class mapping table ---
    lines.append("## Class Mapping")
    lines.append("")
    lines.append("| Native ADK Class | adk-fluent Builder | Import |")
    lines.append("|------------------|-------------------|--------|")

    # Build a lookup: builder name -> module name for cross-refs
    builder_to_module: dict[str, str] = {}
    for module_name, module_specs in by_module.items():
        for s in module_specs:
            builder_to_module[s.name] = module_name

    for spec in sorted(specs, key=lambda s: s.name):
        # MyST target anchor for each row
        module_name = builder_to_module.get(spec.name, spec.output_module)
        builder_link = f"[{spec.name}](../api/{module_name}.md#builder-{spec.name})"

        if spec.is_composite or spec.is_standalone:
            lines.append(f"| _(composite)_ | {builder_link} | `from adk_fluent import {spec.name}` |")
        else:
            lines.append(f"| `{spec.source_class_short}` | {builder_link} | `from adk_fluent import {spec.name}` |")
    lines.append("")

    # --- Per-builder field mapping ---
    builders_with_aliases = [s for s in specs if s.aliases or s.callback_aliases]

    if builders_with_aliases:
        lines.append("## Field Mappings")
        lines.append("")
        lines.append("The tables below show fluent method names that differ from the native field names.")
        lines.append("")

        for spec in sorted(builders_with_aliases, key=lambda s: s.name):
            module_name = builder_to_module.get(spec.name, spec.output_module)
            lines.append(f"(migration-{_anchor_id(spec.name)})=")
            lines.append(f"### {spec.name}")
            lines.append("")
            lines.append("| Native Field | Fluent Method | Notes |")
            lines.append("|-------------|---------------|-------|")

            for fluent_name, field_name in sorted(spec.aliases.items()):
                lines.append(f"| `{field_name}` | `.{fluent_name}()` | alias |")

            for short_name, full_name in sorted(spec.callback_aliases.items()):
                lines.append(f"| `{full_name}` | `.{short_name}()` | callback, additive |")

            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------------------------


def generate_docs(
    seed_path: str,
    manifest_path: str,
    output_dir: str = "docs/generated",
    cookbook_dir: str = "examples/cookbook",
    api_only: bool = False,
    cookbook_only: bool = False,
    migration_only: bool = False,
) -> None:
    """Main documentation generation orchestrator."""
    seed = parse_seed(seed_path)
    manifest = parse_manifest(manifest_path)
    specs = resolve_builder_specs(seed, manifest)

    out = Path(output_dir)

    # Group specs by output_module
    by_module: dict[str, list[BuilderSpec]] = defaultdict(list)
    for spec in specs:
        by_module[spec.output_module].append(spec)

    # --- API Reference ---
    if not cookbook_only and not migration_only:
        api_dir = out / "api"
        api_dir.mkdir(parents=True, exist_ok=True)

        for module_name, module_specs in sorted(by_module.items()):
            md = gen_api_reference_module(module_specs, module_name)
            filepath = api_dir / f"{module_name}.md"
            filepath.write_text(md)
            print(f"  Generated: {filepath}")

        # --- Namespace Module References (P, C, S, A, M, T) ---
        namespace_stems: set[str] = set()
        ns_files: list[Path] = []
        for ns in NAMESPACE_MODULES:
            ns_methods = _introspect_namespace(ns)
            md = gen_namespace_reference(ns, ns_methods)
            filepath = api_dir / f"{ns.output_stem}.md"
            filepath.write_text(md)
            namespace_stems.add(ns.output_stem)
            ns_files.append(filepath)
            print(f"  Generated: {filepath}")

        # Post-process with mdformat for idempotency (table alignment,
        # bracket escaping, etc.)
        try:
            import subprocess

            subprocess.run(
                ["mdformat", *[str(f) for f in ns_files]],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            pass  # mdformat not installed; skip post-processing

        # Generate API index (includes namespace modules)
        index_md = gen_api_index(by_module, namespace_specs=NAMESPACE_MODULES)

        # Discover hand-written .md files in the api/ directory and append
        # them to the index (summary table + toctree).
        hand_written: list[tuple[str, str]] = []  # (stem, title)
        for md_file in sorted(api_dir.glob("*.md")):
            stem = md_file.stem
            if stem == "index" or stem in by_module or stem in namespace_stems:
                continue
            # Extract title from first markdown heading
            first_line = md_file.read_text().split("\n", 1)[0]
            title = first_line.lstrip("# ").strip() if first_line.startswith("#") else stem
            hand_written.append((stem, title))

        if hand_written:
            # Append hand-written modules to the summary table
            # Find the end of the table (blank line after last row) and insert rows
            table_rows = ""
            toctree_entries = ""
            for stem, _title in hand_written:
                table_rows += f"| `{stem}` | — | [{stem}]({stem}.md) |\n"
                toctree_entries += f"{stem}\n"

            # Insert table rows before the blank line after the table
            # and toctree entries before the closing ```
            lines = index_md.split("\n")
            new_lines: list[str] = []
            in_toctree = False
            table_done = False
            for line in lines:
                # Detect end of table: first blank line after table rows
                if not table_done and line == "" and new_lines and new_lines[-1].startswith("|"):
                    # Insert hand-written table rows before the blank line
                    for stem, _title in hand_written:
                        new_lines.append(f"| `{stem}` | — | [{stem}]({stem}.md) |")
                    table_done = True

                if line.startswith("```{toctree}"):
                    in_toctree = True

                # Insert hand-written entries before closing ```
                if in_toctree and line == "```":
                    for stem, _title in hand_written:
                        new_lines.append(stem)
                    in_toctree = False

                new_lines.append(line)

            index_md = "\n".join(new_lines)

        index_path = api_dir / "index.md"
        index_path.write_text(index_md)
        print(f"  Generated: {index_path}")

    # --- Cookbook ---
    if not api_only and not migration_only:
        cookbook_path = Path(cookbook_dir)
        if cookbook_path.exists():
            cookbook_out = out / "cookbook"
            cookbook_out.mkdir(parents=True, exist_ok=True)

            all_parsed: list[dict] = []
            generated_stems: set[str] = set()
            for py_file in sorted(cookbook_path.glob("*.py")):
                if py_file.name.startswith("conftest") or py_file.name.startswith("__"):
                    continue
                parsed = process_cookbook_file(str(py_file))
                all_parsed.append(parsed)
                generated_stems.add(py_file.stem)
                md = cookbook_to_markdown(parsed)
                md_file = cookbook_out / f"{py_file.stem}.md"
                md_file.write_text(md)
                print(f"  Generated: {md_file}")

            # Pick up hand-written .md files already in the output dir
            # (e.g. v4 feature docs with no .py source)
            for md_file in sorted(cookbook_out.glob("*.md")):
                stem = md_file.stem
                if stem == "index" or stem == "conftest" or stem in generated_stems:
                    continue
                # Extract title from first markdown heading
                first_line = md_file.read_text().split("\n", 1)[0]
                title = first_line.lstrip("# ").strip() if first_line.startswith("#") else stem
                all_parsed.append({"filename": md_file.name, "title": title})

            # Generate cookbook index
            index_md = gen_cookbook_index(all_parsed)
            index_path = cookbook_out / "index.md"
            index_path.write_text(index_md)
            print(f"  Generated: {index_path}")
        else:
            print(f"  Cookbook directory {cookbook_dir} not found, skipping.")

    # --- Migration Guide ---
    if not api_only and not cookbook_only:
        migration_dir = out / "migration"
        migration_dir.mkdir(parents=True, exist_ok=True)

        md = gen_migration_guide(specs, by_module)
        filepath = migration_dir / "from-native-adk.md"
        filepath.write_text(md)
        print(f"  Generated: {filepath}")

    # --- Summary ---
    print(f"\n  Documentation generated in {out}/")
    print(f"    Builders:  {len(specs)}")
    print(f"    Modules:   {len(by_module)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Generate adk-fluent documentation from seed + manifest")
    parser.add_argument("seed", help="Path to seed.toml")
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument("--output-dir", default="docs/generated", help="Output directory (default: docs/generated)")
    parser.add_argument(
        "--cookbook-dir", default="examples/cookbook", help="Cookbook examples directory (default: examples/cookbook)"
    )
    parser.add_argument("--api-only", action="store_true", help="Generate API reference only")
    parser.add_argument("--cookbook-only", action="store_true", help="Generate cookbook only")
    parser.add_argument("--migration-only", action="store_true", help="Generate migration guide only")
    args = parser.parse_args()

    generate_docs(
        seed_path=args.seed,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        cookbook_dir=args.cookbook_dir,
        api_only=args.api_only,
        cookbook_only=args.cookbook_only,
        migration_only=args.migration_only,
    )


if __name__ == "__main__":
    main()
