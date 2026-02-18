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
import re
import sys
from collections import defaultdict
from pathlib import Path

with contextlib.suppress(ImportError):
    import tomllib  # noqa: F401

# Import BuilderSpec resolution from generator (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from generator import BuilderSpec, parse_manifest, parse_seed, resolve_builder_specs

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


def gen_api_reference_for_builder(spec: BuilderSpec) -> str:
    """Generate MyST-flavored Markdown API reference for a single builder.

    Sections:
      - MyST target anchor for cross-referencing
      - Header with description and inline usage example
      - Constructor args table
      - Alias methods with full type hints
      - Callback methods with MyST admonitions
      - Extra methods
      - Terminal methods
      - Forwarded fields table
    """
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
            lines.append(f"| `{arg}` | `{arg_type}` |")
        lines.append("")

    # --- Alias Methods ---
    if spec.aliases:
        lines.append("### Methods")
        lines.append("")
        for fluent_name, field_name in spec.aliases.items():
            field_info = next((f for f in spec.fields if f["name"] == field_name), None)
            type_hint = field_info["type_str"] if field_info else "Any"
            doc = spec.field_docs.get(field_name, "")
            if not doc and field_info:
                doc = field_info.get("description", "")
            if not doc:
                doc = f"Set the `{field_name}` field."

            lines.append(f"#### `.{fluent_name}(value: {type_hint}) -> Self`")
            lines.append("")
            lines.append(f"- **Maps to:** `{field_name}`")
            lines.append(f"- {doc}")
            lines.append("")

    # --- Callback Methods ---
    if spec.callback_aliases:
        lines.append("### Callbacks")
        lines.append("")
        for short_name, full_name in spec.callback_aliases.items():
            lines.append(f"#### `.{short_name}(*fns: Callable) -> Self`")
            lines.append("")
            lines.append(f"Append callback(s) to `{full_name}`.")
            lines.append("")
            lines.append(":::{note}")
            lines.append("Multiple calls accumulate. Each invocation appends to the callback list")
            lines.append("rather than replacing previous callbacks.")
            lines.append(":::")
            lines.append("")

            lines.append(f"#### `.{short_name}_if(condition: bool, fn: Callable) -> Self`")
            lines.append("")
            lines.append(f"Append callback to `{full_name}` only if `condition` is `True`.")
            lines.append("")

    # --- Extra Methods ---
    if spec.extras:
        lines.append("### Extra Methods")
        lines.append("")
        for extra in spec.extras:
            name = extra["name"]
            sig = extra.get("signature", "(self) -> Self")
            doc = extra.get("doc", "")
            # Clean up signature for display — show full type hints
            display_sig = sig.replace("(self, ", "(").replace("(self)", "()")
            lines.append(f"#### `.{name}{display_sig}`")
            lines.append("")
            if doc:
                lines.append(doc)
                lines.append("")

    # --- Terminal Methods ---
    if spec.terminals:
        lines.append("### Terminal Methods")
        lines.append("")
        for terminal in spec.terminals:
            t_name = terminal["name"]
            if "signature" in terminal:
                display_sig = terminal["signature"].replace("(self, ", "(").replace("(self)", "()")
                lines.append(f"#### `.{t_name}{display_sig}`")
            elif "returns" in terminal:
                lines.append(f"#### `.{t_name}() -> {terminal['returns']}`")
            else:
                lines.append(f"#### `.{t_name}()`")
            lines.append("")
            t_doc = terminal.get("doc", "")
            if t_doc:
                lines.append(t_doc)
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
                lines.append(f"| `.{fname}(value)` | `{ftype}` |")
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


def gen_api_index(by_module: dict[str, list[BuilderSpec]]) -> str:
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
    lines.append("")

    # --- Toctree ---
    lines.append("```{toctree}")
    lines.append(":hidden:")
    lines.append("")
    for module_name in sorted(by_module.keys()):
        lines.append(module_name)
    lines.append("```")
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


def cookbook_to_markdown(parsed: dict) -> str:
    """Convert parsed cookbook data to MyST Markdown with sphinx-design tabs."""
    lines: list[str] = []

    lines.append(f"# {parsed['title']}")
    lines.append("")

    # --- "What you'll learn" one-liner ---
    learn = _learn_summary(parsed["title"])
    lines.append(f"*{learn}*")
    lines.append("")

    lines.append(f"_Source: `{parsed['filename']}`_")
    lines.append("")

    # --- Tabbed side-by-side comparison ---
    if parsed["native"] or parsed["fluent"]:
        lines.append("::::{tab-set}")
        if parsed["native"]:
            lines.append(":::{tab-item} Native ADK")
            lines.append("```python")
            lines.append(parsed["native"])
            lines.append("```")
            lines.append(":::")
        if parsed["fluent"]:
            lines.append(":::{tab-item} adk-fluent")
            lines.append("```python")
            lines.append(parsed["fluent"])
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
    else:
        return "Patterns"


def gen_cookbook_index(cookbook_files: list[dict]) -> str:
    """Generate docs/generated/cookbook/index.md with categorized toctree."""
    lines: list[str] = []

    lines.append("# Cookbook")
    lines.append("")
    lines.append("Side-by-side examples comparing native ADK code with the adk-fluent")
    lines.append("equivalent. Each recipe demonstrates a specific pattern or feature.")
    lines.append("")

    # Group by category
    categories: dict[str, list[dict]] = defaultdict(list)
    for cb in cookbook_files:
        cat = _categorize_cookbook(cb["filename"])
        categories[cat].append(cb)

    # Defined order
    cat_order = ["Basics", "Execution", "Advanced", "Patterns", "Other"]
    cat_descriptions = {
        "Basics": "Foundational patterns: creating agents, adding tools, callbacks, and simple workflows.",
        "Execution": "Running agents: one-shot, streaming, cloning, testing, and sessions.",
        "Advanced": "Advanced composition: dynamic forwarding, operators, routing, and conditional logic.",
        "Patterns": "Real-world patterns: state management, presets, decorators, serialization, and more.",
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
        for item in items:
            stem = Path(item["filename"]).stem
            lines.append(f"- [{item['title']}]({stem}.md)")
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

        # Generate API index
        index_md = gen_api_index(by_module)
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
            for py_file in sorted(cookbook_path.glob("*.py")):
                if py_file.name.startswith("conftest") or py_file.name.startswith("__"):
                    continue
                parsed = process_cookbook_file(str(py_file))
                all_parsed.append(parsed)
                md = cookbook_to_markdown(parsed)
                md_file = cookbook_out / f"{py_file.stem}.md"
                md_file.write_text(md)
                print(f"  Generated: {md_file}")

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
