---
name: codegen-pipeline
description: Run the adk-fluent code generation pipeline (scan, seed, generate). Use when the user wants to regenerate builders from ADK, update generated code, or sync with a new ADK version. Also use when generated files appear stale or out of sync.
allowed-tools: Bash, Read, Glob, Grep
---

# adk-fluent Code Generation Pipeline

You are operating the adk-fluent code generation pipeline. This pipeline introspects
google-adk and produces Python builder classes, type stubs, and test scaffolds.

## Pipeline stages

Run stages in order. Each stage depends on the previous one.

### 1. Scan (ADK introspection)

```bash
python scripts/scanner.py
```

Produces `manifest.json` — a machine-truth snapshot of every ADK class, field, type,
default, callback, and inheritance chain.

### 2. Seed (builder specification)

```bash
python scripts/seed_generator.py manifest.json
```

Produces `seeds/seed.toml` by:
- Classifying ADK classes (agent, tool, config, service, etc.)
- Filtering for builder-worthy classes
- Generating method aliases and extras
- Merging manual overrides from `seeds/seed.manual.toml`

### 3. Generate (code emission)

```bash
python scripts/generator.py seeds/seed.toml manifest.json
```

Produces in `src/adk_fluent/`:
- `.py` builder modules (agent.py, workflow.py, tool.py, config.py, etc.)
- `.pyi` type stubs for IDE autocomplete
- `__init__.py` with re-exports

### 4. Docs & LLM context

```bash
python scripts/llms_generator.py manifest.json seeds/seed.toml
python scripts/doc_generator.py manifest.json seeds/seed.toml
```

Regenerates CLAUDE.md, .cursorrules, API docs, and cookbook pages.

## One-command pipeline

If `just` is available:

```bash
just all    # scan -> seed -> generate -> docs -> docs-build
```

If not, run each stage manually in order.

## Verification

After generation, always run:

```bash
uv run pytest tests/ -x -q --tb=short
uv run pyright src/adk_fluent/
```

## Key rules

- **NEVER edit generated files directly** — they will be overwritten
- Generated files are marked in `.gitattributes` with `linguist-generated=true`
- Hand-written files: `_base.py`, `_context.py`, `_prompt.py`, `_transforms.py`, `_routing.py`, `_guards.py`, `_eval.py`, `_helpers.py`, `_middleware.py`, `_tools.py`, `_artifacts.py`, `_primitives.py`
- To customize generated output, edit `seeds/seed.manual.toml` or `scripts/generator/`
