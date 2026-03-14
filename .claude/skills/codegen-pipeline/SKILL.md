---
name: codegen-pipeline
description: Run the adk-fluent code generation pipeline (scan, seed, generate). Use when the user wants to regenerate builders from ADK, update generated code, or sync with a new ADK version. Also use when generated files appear stale or out of sync.
allowed-tools: Bash, Read, Glob, Grep
---

# adk-fluent Code Generation Pipeline

You are operating the adk-fluent code generation pipeline. This pipeline introspects
google-adk and produces Python builder classes, type stubs, and test scaffolds.

## Architecture overview

```
google-adk (installed package)
  ↓ scanner.py
manifest.json (machine-truth snapshot of ADK API)
  ↓ seed_generator.py + seed.manual.toml
seeds/seed.toml (builder specifications)
  ↓ generator.py + code_ir/
src/adk_fluent/ (generated builders, stubs, tests)
  ↓ llms_generator.py + doc_generator.py
CLAUDE.md, docs/ (LLM context + documentation)
```

## Pipeline stages

Run stages in order. Each stage depends on the previous one.

### 1. Scan (ADK introspection)

```bash
uv run python scripts/scanner.py -o manifest.json
```

Produces `manifest.json` — a machine-truth snapshot of every ADK class, field, type,
default, callback, and inheritance chain. This is the single source of truth for
what ADK exposes.

### 2. Seed (builder specification)

```bash
uv run python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
```

Produces `seeds/seed.toml` by:
- Classifying ADK classes (agent, tool, config, service, etc.)
- Filtering for builder-worthy classes
- Generating method aliases and extras
- Merging manual overrides from `seeds/seed.manual.toml`

### 3. Generate (code emission)

```bash
uv run python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
uv run python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py
```

Produces in `src/adk_fluent/`:
- `.py` builder modules (agent.py, workflow.py, tool.py, config.py, etc.)
- `.pyi` type stubs for IDE autocomplete
- `__init__.py` with re-exports
- `tests/generated/test_*_builder.py` — test scaffolds

### 4. Docs & LLM context

```bash
uv run python scripts/llms_generator.py manifest.json seeds/seed.toml
uv run python scripts/doc_generator.py seeds/seed.toml manifest.json --output-dir docs/generated --cookbook-dir examples/cookbook
```

Regenerates CLAUDE.md, .cursorrules, API docs, and cookbook pages.

## One-command pipeline

If `just` is available (preferred):

```bash
just all    # scan -> seed -> generate -> docs -> docs-build
```

If not, run each stage manually in order.

## Partial regeneration

Not everything needs the full pipeline. Use these shortcuts:

| What changed | Command | Why |
|---|---|---|
| ADK version upgraded | `just all` | Full rescan needed |
| `seed.manual.toml` edited | `just seed && just generate` | Scan unchanged |
| Generator script edited | `just generate` | Manifest + seed unchanged |
| Docs template edited | `just docs` | Only docs need refresh |
| LLM context stale | `uv run python scripts/llms_generator.py manifest.json seeds/seed.toml` | Just context files |
| Stubs only | `uv run python scripts/generator.py seeds/seed.toml manifest.json --stubs-only` | Quick IDE refresh |

## Verification

After generation, always run:

```bash
uv run pytest tests/ -x -q --tb=short
uv run pyright src/adk_fluent/
```

To verify generated files match canonical output (used in CI):

```bash
just check-gen
```

## Key rules

- **NEVER edit generated files directly** — they will be overwritten on next `just generate`
- Generated files are marked in `.gitattributes` with `linguist-generated=true`
- Hand-written core files (safe to edit):
  `_base.py`, `_context.py`, `_prompt.py`, `_transforms.py`, `_routing.py`,
  `_guards.py`, `_eval.py`, `_helpers.py`, `_middleware.py`, `_tools.py`,
  `_artifacts.py`, `_primitives.py`, `patterns.py`, `middleware.py`,
  `decorators.py`, `viz.py`, `di.py`, `prelude.py`
- To customize generated output, edit `seeds/seed.manual.toml` or `scripts/code_ir/`
- All generated code is auto-formatted by ruff (integrated into emitter)

## Troubleshooting

### Generated files out of sync

```bash
just check-gen  # Will show diff if files are stale
just generate   # Regenerate
```

### Scanner fails on new ADK version

Common causes:
- **New base class not recognized**: Update classifier in `scripts/seed_generator.py`
- **New parameter type not handled**: Update type mapping in `scripts/code_ir/ir_builders.py`
- **Import path changed**: Check `scripts/scanner.py` import resolution

### Generator produces invalid Python

1. Check `seeds/seed.toml` for malformed entries
2. Check `seeds/seed.manual.toml` for typos in class/field names
3. Run `uv run ruff check src/adk_fluent/` to see syntax issues
4. Look at `scripts/code_ir/emitters.py` for emission bugs

### Type stubs don't match implementation

Stubs are generated from the same seed — if they diverge:
1. Run `just generate` to regenerate both
2. If still wrong, check `scripts/code_ir/stubs.py` for stub emission logic

### Missing builder method

If an ADK field exists but no builder method appears:
1. Check `manifest.json` — is the field captured by scanner?
2. Check `seeds/seed.toml` — is the class included and the field listed?
3. If it's a new field: `just scan && just seed && just generate`
4. If it should be excluded: add to skip list in `seeds/seed.manual.toml`

## File ownership reference

| Path | Owner | Edit? |
|---|---|---|
| `manifest.json` | `scanner.py` | Never — regenerate |
| `seeds/seed.toml` | `seed_generator.py` | Never — regenerate |
| `seeds/seed.manual.toml` | Human | Yes — this is your config |
| `src/adk_fluent/agent.py` | `generator.py` | Never — regenerate |
| `src/adk_fluent/_base.py` | Human | Yes — core builder logic |
| `tests/generated/*.py` | `generator.py` | Never — regenerate |
| `tests/manual/*.py` | Human | Yes — hand-written tests |
| `CLAUDE.md` | `llms_generator.py` | Never — regenerate |
