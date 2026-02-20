# Codegen Pipeline

adk-fluent is **auto-generated** from the installed ADK package. The codegen pipeline introspects ADK at scan time and produces fluent builders, type stubs, tests, and documentation.

## Overview

```
scanner.py --> manifest.json --> seed_generator.py --> seed.toml --> generator.py --> Python code
                                       ^
                               seed.manual.toml
                               (hand-crafted extras)
```

## 5 Stages

### Stage 1: Scanner (`scripts/scanner.py`)

Introspects all installed `google-adk` modules and produces `manifest.json` -- a machine-truth description of every Pydantic BaseModel class, its fields, types, defaults, validators, callbacks, and inheritance hierarchy.

```bash
just scan
# Equivalent to:
# python scripts/scanner.py -o manifest.json
```

The manifest captures:

- Class names, module paths, and MRO chains
- Field names, types, defaults, and validators
- Callback fields and their signatures
- Inheritance relationships

### Stage 2: Seed Generator (`scripts/seed_generator.py`)

Reads `manifest.json` and generates `seeds/seed.toml` -- a classification of every ADK class with metadata that drives code generation. The seed generator:

- Classifies each class into a semantic tag (agent, tool, config, service, etc.)
- Extracts field information for builder method generation
- Merges with `seeds/seed.manual.toml` for hand-curated extras (renames, optional constructor args, extra methods)

```bash
just seed
# Equivalent to:
# python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
```

### Stage 3: Code Generator (`scripts/generator.py`)

Combines `seed.toml` and `manifest.json` to emit:

- Fluent builder classes (`.py` files in `src/adk_fluent/`)
- `.pyi` type stubs for IDE autocomplete
- Test scaffolds (in `tests/generated/`)

```bash
just generate
# Equivalent to:
# python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
```

### Stage 4: Documentation Generator (`scripts/doc_generator.py`)

Generates API reference docs, cookbook pages, and migration guides from the seed and manifest:

```bash
just docs
# Equivalent to:
# python scripts/doc_generator.py seeds/seed.toml manifest.json --output-dir docs/generated --cookbook-dir examples/cookbook
```

Sub-commands for targeted generation:

- `just docs-api` -- API reference only
- `just docs-cookbook` -- Cookbook only
- `just docs-migration` -- Migration guide only

### Stage 5: Cookbook Generator (`scripts/cookbook_generator.py`)

Generates example stubs in `examples/cookbook/` with side-by-side Native ADK vs Fluent comparisons:

```bash
just cookbook-gen
# Preview without writing:
just cookbook-gen-dry
```

## Full Pipeline

Run all stages in sequence:

```bash
just all
```

This executes: `scan` -> `seed` -> `generate` -> `docs`

## Staying in Sync with ADK

When Google releases a new version of ADK, regenerate everything:

```bash
pip install --upgrade google-adk
just all   # Regenerate everything
just test  # Verify
```

The scanner discovers new classes, the seed generator classifies them, and the code generator emits new builders -- all automatically.

## Other Commands

| Command             | Description                                     |
| ------------------- | ----------------------------------------------- |
| `just all`          | Full pipeline: scan -> seed -> generate -> docs |
| `just scan`         | Introspect ADK -> manifest.json                 |
| `just seed`         | manifest.json -> seed.toml                      |
| `just generate`     | seed.toml + manifest.json -> code               |
| `just stubs`        | Regenerate `.pyi` stubs only                    |
| `just test`         | Run pytest suite (780+ tests)                   |
| `just typecheck`    | Run pyright type-check                          |
| `just docs`         | Generate all documentation                      |
| `just cookbook-gen` | Generate cookbook example stubs                 |
| `just agents`       | Convert cookbook -> `adk web` agent folders     |
| `just diff`         | Show changes since last scan                    |
| `just clean`        | Remove generated files                          |
