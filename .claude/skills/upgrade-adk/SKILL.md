---
name: upgrade-adk
description: Upgrade adk-fluent to a new version of google-adk. Use when a new ADK version is released, when the user asks to sync with upstream, or when google-adk has been updated in the environment.
disable-model-invocation: true
allowed-tools: Bash, Read, Glob, Grep, Edit, Write
---

# Upgrade adk-fluent to a New ADK Version

Follow these steps exactly in order. Do not skip steps.

## Step 1: Archive current state

```bash
cp manifest.json manifest.json.bak
```

## Step 2: Install the new ADK version

```bash
pip install --upgrade google-adk
python -c "import google.adk; print(google.adk.__version__)"
```

Record the new version number.

## Step 3: Scan the new ADK

```bash
python scripts/scanner.py
```

This produces an updated `manifest.json`.

## Step 4: Review changes

Compare the old and new manifests:

```bash
diff <(python -m json.tool manifest.json.bak) <(python -m json.tool manifest.json) | head -100
```

Classify changes into categories:
- **New classes**: Automatic — scanner discovers them
- **New fields on existing classes**: Automatic — `__getattr__` fallback handles them
- **Removed fields**: May need `seed.manual.toml` cleanup
- **Renamed fields**: Need `seed.manual.toml` alias updates
- **Changed inheritance**: Usually automatic
- **Breaking API changes**: Significant manual work

For detailed impact analysis, read `docs/contributing/upstream-impact-analysis.md`.

## Step 5: Update manual overrides (if needed)

If the diff shows renamed or removed classes/fields, update `seeds/seed.manual.toml`.

## Step 6: Regenerate everything

```bash
python scripts/seed_generator.py manifest.json
python scripts/generator.py seeds/seed.toml manifest.json
python scripts/llms_generator.py manifest.json seeds/seed.toml
```

Or if `just` is available: `just all`

## Step 7: Verify

```bash
uv run pytest tests/ -x -q --tb=short
uv run pyright src/adk_fluent/
```

Fix any failures before proceeding.

## Step 8: Update metadata

- Update `pyproject.toml` if the minimum ADK version changed
- Update the ADK badge in `README.md` and `README.template.md`
- Add a CHANGELOG entry under `[Unreleased]`

## Step 9: Cleanup

```bash
rm manifest.json.bak
```

## Reference

For the full 9-category impact analysis, see:
`docs/contributing/upstream-impact-analysis.md`
