---
name: upgrade-adk
description: Upgrade adk-fluent to a new version of google-adk. Use when a new ADK version is released, when the user asks to sync with upstream, or when google-adk has been updated in the environment.
disable-model-invocation: true
allowed-tools: Bash, Read, Glob, Grep, Edit, Write
---

# Upgrade adk-fluent to a New ADK Version

Follow these steps exactly in order. Do not skip steps.

## Pre-flight check

Before starting, ensure you're on a clean branch:

```bash
git status
git stash  # if needed
```

## Step 1: Archive current state

```bash
cp manifest.json manifest.json.bak
cp seeds/seed.toml seeds/seed.toml.bak
```

## Step 2: Install the new ADK version

```bash
uv pip install --upgrade google-adk
uv run python -c "from importlib.metadata import version; print(version('google-adk'))"
```

Record the new version number. If upgrading to a specific version:

```bash
uv pip install google-adk==X.Y.Z
```

## Step 3: Scan the new ADK

```bash
uv run python scripts/scanner.py -o manifest.json
```

This produces an updated `manifest.json`.

## Step 4: Review changes

Compare the old and new manifests:

```bash
diff <(python -m json.tool manifest.json.bak) <(python -m json.tool manifest.json) | head -200
```

Classify changes into categories:

| Category | Impact | Action needed |
|----------|--------|---------------|
| New classes | Low | Automatic — scanner discovers them |
| New fields on existing classes | Low | Automatic — `__getattr__` fallback handles them |
| Removed fields | Medium | May need `seed.manual.toml` cleanup |
| Renamed fields | Medium | Need `seed.manual.toml` alias updates |
| Changed inheritance | Low | Usually automatic |
| Changed field types | Medium | May need type mapping updates |
| Removed classes | High | Remove from seed.manual.toml, update tests |
| Breaking API changes | High | Manual work required |
| New callback signatures | Medium | Check callback builders in `_base.py` |

For detailed impact analysis, read `docs/contributing/upstream-impact-analysis.md`.

## Step 5: Update manual overrides (if needed)

If the diff shows renamed or removed classes/fields:

1. Edit `seeds/seed.manual.toml`
2. Update/remove affected entries
3. Add new aliases for renamed fields

## Step 6: Regenerate everything

```bash
just all    # scan -> seed -> generate -> docs -> docs-build
```

Or manually:

```bash
uv run python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
uv run python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
uv run python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py
uv run python scripts/llms_generator.py manifest.json seeds/seed.toml
```

## Step 7: Verify

```bash
uv run pytest tests/ -x -q --tb=short
uv run pyright src/adk_fluent/
```

Fix any failures before proceeding.

### Common verification failures

| Failure | Cause | Fix |
|---------|-------|-----|
| ImportError in generated code | ADK renamed/moved a class | Update import mapping in `scripts/scanner.py` |
| Test assertion failure | Builder produces different output | Update test expectations or `seed.manual.toml` |
| Pyright type error | Field type changed | Update type stubs or `seed.manual.toml` field_docs |
| Pydantic ValidationError | New required field without default | Add default in `seed.manual.toml` or `_base.py` |

## Step 8: Update the N-5 compatibility matrix

After upgrading, update the backward compatibility matrix:

1. Update `adk-version` lists in `.github/workflows/ci.yml` (the `compat` job) and `.github/workflows/sync-adk.yml` (the `test` job)
2. Add the new version at the top, drop the oldest version from the bottom (maintain 6 entries: latest + N-5)
3. Update the compatibility table in `README.md` under "ADK Compatibility"
4. Update `ADK_VERSION` env var in `.github/workflows/ci.yml` if the codegen pin changed

## Step 9: Update metadata

- Update `pyproject.toml` if the minimum ADK version changed (the `>=` lower bound)
- Update the ADK badge in `README.md` and `README.template.md`
- Add a CHANGELOG entry under `[Unreleased]`:
  ```
  ### Changed
  - Upgraded google-adk from X.Y.Z to A.B.C
  ```

## Step 10: Run full CI locally

```bash
just ci    # preflight + check-gen + test
```

This verifies everything passes before pushing.

## Step 11: Cleanup

```bash
rm manifest.json.bak seeds/seed.toml.bak
```

## Rollback procedure

If the upgrade introduces too many issues:

```bash
# Restore archived state
cp manifest.json.bak manifest.json
cp seeds/seed.toml.bak seeds/seed.toml

# Downgrade ADK
uv pip install google-adk==PREVIOUS_VERSION

# Regenerate from old manifest
just generate

# Verify
uv run pytest tests/ -x -q --tb=short
```

## References

- `docs/contributing/upstream-impact-analysis.md` — Full 9-category impact analysis
- [`../_shared/references/builder-inventory.md`](../_shared/references/builder-inventory.md) — Current builder inventory
- [`../_shared/references/development-commands.md`](../_shared/references/development-commands.md) — All justfile commands
- [`../_shared/references/generated-files.md`](../_shared/references/generated-files.md) — Generated vs hand-written files
