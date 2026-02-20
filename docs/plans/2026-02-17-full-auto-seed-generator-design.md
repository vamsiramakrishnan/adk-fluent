# Full Auto-Pipeline Seed Generator

**Date:** 2026-02-17
**Status:** Approved
**Goal:** Build a mechanism that systematically parses ALL google-adk modules and generates a complete seed.toml — no human review step.

**Philosophy:** Trust mechanisms, not patchwork brilliance. Brute-force parse, brute-force generate.

______________________________________________________________________

## Pipeline

```
scanner.py (enhanced)          seed_generator.py              generator.py (existing)
       |                              |                              |
  Walk ALL modules              Read manifest.json             Read seed.toml + manifest
  Pydantic: model_fields        Classify each class            Generate .py, .pyi, tests
  Non-Pydantic: inspect()       Apply field policies
  Emit manifest.json            Generate aliases
                                Emit seed.toml
```

Command: `make all` runs all three in sequence.

______________________________________________________________________

## Scanner Enhancement (scripts/scanner.py)

### Current limitations

- Hardcoded `SCAN_TARGETS` list — only 12 specific classes
- Only handles Pydantic BaseModel subclasses
- Misses non-Pydantic classes (Runner, tools, services, planners, plugins)

### Changes

1. **Auto-discovery:** Walk `google.adk` package tree via `pkgutil.walk_packages`
1. **Dual-mode introspection:**
   - Pydantic classes: `model_fields` + `get_type_hints` (existing logic)
   - Non-Pydantic classes: `inspect.signature(cls.__init__)` to extract params
1. **Extended ClassInfo:** Add `inspection_mode` field (`"pydantic"` or `"init_signature"`)
1. **Extended manifest.json:** Add `init_params` list for non-Pydantic classes
1. **Graceful import handling:** Skip modules with missing optional deps (a2a, docker, kubernetes, etc.)

### Discovery rules

- Import every submodule of `google.adk`
- For each module, find all classes where `cls.__module__ == module.__name__` (avoid duplicates from re-exports)
- Check: is it a BaseModel subclass? → Pydantic mode
- Check: is it a concrete class (not ABC with no __init__)? → init_signature mode
- Skip: private classes (name starts with `_`), test classes, typing constructs

______________________________________________________________________

## Seed Generator (scripts/seed_generator.py) — NEW

### Input

- `manifest.json` (from enhanced scanner)

### Output

- `seeds/seed.toml` (complete, auto-generated)

### Step 1: Classification

Each class gets a tag based on mechanical rules:

| Rule (checked in order)                                | Tag        |
| ------------------------------------------------------ | ---------- |
| Subclass of BaseAgent                                  | `agent`    |
| Name ends with `Service`                               | `service`  |
| Name ends with `Config` AND module not in `evaluation` | `config`   |
| Name ends with `Tool` or name ends with `Toolset`      | `tool`     |
| Name ends with `Plugin`                                | `plugin`   |
| Name ends with `Planner`                               | `planner`  |
| Name ends with `Executor`                              | `executor` |
| Name is `App` or `Runner` or `InMemoryRunner`          | `runtime`  |
| Module contains `evaluation`                           | `eval`     |
| Module contains `auth`                                 | `auth`     |
| Otherwise                                              | `data`     |

**Builder-worthy tags:** `agent`, `config`, `runtime`, `executor`, `planner`
**Documented-only (no builder):** `eval`, `auth`, `data`, `service` (ABCs), `tool` (ABCs)

The service/tool concrete implementations that users construct (InMemorySessionService, etc.) DO get builders.

### Step 2: Constructor arg detection

For Pydantic classes:

- Required fields with no default → constructor args
- Cap at first 3 required fields (ergonomic limit)

For non-Pydantic classes:

- `inspect.signature(cls.__init__)` → positional params without defaults → constructor args
- Skip `self`

### Step 3: Field policies

Applied per-field, all mechanical:

| Condition                                                                   | Policy                        |
| --------------------------------------------------------------------------- | ----------------------------- |
| Name in `{parent_agent, model_config, model_fields, model_computed_fields}` | `skip`                        |
| Name starts with `_`                                                        | `skip`                        |
| Type contains `Callable` AND name contains `callback`                       | `additive` (append semantics) |
| Type is `list[...]` AND name in `{tools, sub_agents, plugins}`              | `list_extend`                 |

### Step 4: Alias generation

Lookup table, applied mechanically:

| Field name             | Alias                                             |
| ---------------------- | ------------------------------------------------- |
| `instruction`          | `instruct`                                        |
| `description`          | `describe`                                        |
| `global_instruction`   | `global_instruct`                                 |
| Any `*_callback` field | Strip `_callback` suffix (becomes callback_alias) |

No other aliases. Everything else uses its original name via `__getattr__`.

### Step 5: Terminal methods

All builders get `build()` returning the source class. That's it.
Runtime builders additionally get `build_runner()` and `build_app()`.

### Step 6: Extra methods

| Tag                                       | Extra methods                                             |
| ----------------------------------------- | --------------------------------------------------------- |
| `agent` (wrapping agents with sub_agents) | `.step()` / `.branch()` / `.member()` based on agent type |
| `agent` (LlmAgent)                        | `.tool()` for single-tool append                          |
| `agent` (LlmAgent)                        | `.apply(stack)` for middleware                            |

These are generated from patterns, not hand-written.

### Step 7: TOML emission

Emit a valid TOML file with proper sections. Use a TOML writer or string formatting.

### Step 8: Output module grouping

Classes are grouped into output modules by their tag:

- `agent` tag → `agent.py` module
- `config` tag → `config.py` module
- `runtime` tag → `runtime.py` module
- `executor` tag → `executor.py` module
- `planner` tag → `planner.py` module
- `workflow` tag → `workflow.py` module (SequentialAgent, ParallelAgent, LoopAgent)
- `multi` tag → `multi.py` module (Team/coordinator pattern)

______________________________________________________________________

## Generator Changes (scripts/generator.py)

### Existing behavior preserved

- Reads seed.toml + manifest.json
- Generates .py, .pyi, tests

### New: handle `init_signature` mode

- For non-Pydantic classes, `__getattr__` validates against `init_params` list instead of `model_fields`
- Build method constructs via `SourceClass(**config)` regardless of mode

______________________________________________________________________

## Makefile Update

```makefile
all: scan seed generate

scan:
    python scripts/scanner.py -o manifest.json

seed:
    python scripts/seed_generator.py manifest.json -o seeds/seed.toml

generate:
    python scripts/generator.py seeds/seed.toml manifest.json \
        --output-dir src/adk_fluent --test-dir tests/generated
```

______________________________________________________________________

## Files

| File                        | Action                                          |
| --------------------------- | ----------------------------------------------- |
| `scripts/scanner.py`        | Modify: auto-discovery, dual-mode introspection |
| `scripts/seed_generator.py` | Create: manifest → seed.toml                    |
| `scripts/generator.py`      | Modify: handle init_signature mode              |
| `Makefile`                  | Modify: add `seed` target                       |
| `seeds/seed.toml`           | Now auto-generated                              |

______________________________________________________________________

## What success looks like

1. `make scan` walks all 436 ADK modules, produces manifest.json with ~196 Pydantic + key non-Pydantic classes
1. `make seed` reads manifest.json, classifies all classes, emits seed.toml with ~30-50 builder sections
1. `make generate` produces .py + .pyi + test scaffolds for every builder
1. Zero manual editing required
1. When ADK updates, `make all` regenerates everything automatically
