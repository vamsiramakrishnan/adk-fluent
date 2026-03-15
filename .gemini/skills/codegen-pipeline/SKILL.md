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
  ↓ llms_generator.py + doc_generator.py + skill_generator.py
CLAUDE.md, docs/, .gemini/skills/_shared/ (context + documentation)
```

## Pipeline stages

Run stages in order. Each stage depends on the previous one.

### 1. Scan (ADK introspection)

```bash
uv run python scripts/scanner.py -o manifest.json
```

### 2. Seed (builder specification)

```bash
uv run python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
```

### 3. Generate (code emission)

```bash
uv run python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
uv run python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py
```

### 4. Docs, LLM context, and skill references

```bash
uv run python scripts/llms_generator.py manifest.json seeds/seed.toml
uv run python scripts/doc_generator.py seeds/seed.toml manifest.json --output-dir docs/generated --cookbook-dir examples/cookbook
uv run python scripts/skill_generator.py manifest.json seeds/seed.toml
```

## One-command pipeline

```bash
just all    # scan -> seed -> generate -> docs -> skills -> docs-build
```

## Partial regeneration

| What changed | Command | Why |
|---|---|---|
| ADK version upgraded | `just all` | Full rescan needed |
| `seed.manual.toml` edited | `just seed && just generate` | Scan unchanged |
| Generator script edited | `just generate` | Manifest + seed unchanged |
| Docs template edited | `just docs` | Only docs need refresh |
| Skill references stale | `just skills` | Only skill refs need refresh |
| Stubs only | `just stubs` | Quick IDE refresh |

For the full list of development commands, read
[`../_shared/references/development-commands.md`](../_shared/references/development-commands.md).

## Verification

```bash
uv run pytest tests/ -x -q --tb=short
uv run pyright src/adk_fluent/
just check-gen    # Verify generated files are canonical
```

## Key rules

- **NEVER edit generated files directly** — they will be overwritten on next `just generate`
- To customize generated output, edit `seeds/seed.manual.toml` or `scripts/code_ir/`

For the complete list of generated vs hand-written files, read
[`../_shared/references/generated-files.md`](../_shared/references/generated-files.md)
or run `uv run .gemini/skills/_shared/scripts/list-generated-files.py`.

## Troubleshooting

### Generated files out of sync

```bash
just check-gen  # Will show diff if files are stale
just generate   # Regenerate
```

### Scanner fails on new ADK version

- **New base class not recognized**: Update classifier in `scripts/seed_generator.py`
- **New parameter type not handled**: Update type mapping in `scripts/code_ir/ir_builders.py`
- **Import path changed**: Check `scripts/scanner.py` import resolution

### Generator produces invalid Python

1. Check `seeds/seed.toml` for malformed entries
2. Check `seeds/seed.manual.toml` for typos
3. Run `uv run ruff check src/adk_fluent/` to see syntax issues

### Missing builder method

1. Check `manifest.json` — is the field captured by scanner?
2. Check `seeds/seed.toml` — is the class included?
3. If new field: `just scan && just seed && just generate`
4. If should be excluded: add to skip list in `seeds/seed.manual.toml`
