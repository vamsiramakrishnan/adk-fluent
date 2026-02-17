# Documentation Publishing System Design

**Date:** 2026-02-17
**Status:** Approved

## Overview

Add a complete documentation publishing pipeline using Sphinx + MyST-Parser + Read the Docs, with a major overhaul of `doc_generator.py` to produce richer, cross-linked documentation.

## Audience

Both library users (API refs, cookbook, migration) and contributors (codegen pipeline, architecture).

## Architecture

### Hosting: Read the Docs

- Free for open source
- Auto-builds on every push via `.readthedocs.yaml`
- Versioned docs (per git tag)
- Full-text search, HTTPS, custom domain support

### Framework: Sphinx + MyST-Parser

- Sphinx for the build engine (mature, extensible)
- MyST-Parser for Markdown authorship (existing docs are Markdown)
- Furo theme (modern, dark mode, responsive)
- sphinx-design for tabs, cards, grids
- sphinx_copybutton for code block copy buttons
- intersphinx for linking to google-adk and Python stdlib docs

### Site Structure

```
docs/
  conf.py                          # Sphinx configuration
  index.md                         # Landing page with feature highlights
  getting-started.md               # Installation + first agent
  changelog.md                     # Release notes
  user-guide/
    index.md                       # User guide overview
    builders.md                    # How builders work
    expression-language.md         # >>, |, *, @, //, Route, S operators
    prompts.md                     # Prompt builder guide
    execution.md                   # ask/stream/session/map patterns
    callbacks.md                   # Callback system
    presets.md                     # Preset bundles
    state-transforms.md           # S.pick, S.drop, S.rename, etc.
  api/                             # AUTO-GENERATED
    index.md                       # Module listing with builder counts
    agent.md                       # Agent, BaseAgent
    workflow.md                    # Pipeline, FanOut, Loop
    tool.md                        # 40+ tool builders
    ... (one per module)
  cookbook/                         # AUTO-GENERATED
    index.md                       # Cookbook overview with categories
    01_simple_agent.md
    ...
  migration/                       # AUTO-GENERATED
    from-native-adk.md
  contributing/
    index.md                       # How to contribute
    codegen-pipeline.md           # How the build pipeline works
    adding-builders.md            # How to add/customize builders
```

## doc_generator.py Overhaul

### API Reference Enrichments

- MyST cross-references between builders
- Admonitions for important notes (additive semantics, etc.)
- Inline 2-3 line usage examples per builder
- Type links to ADK docs via intersphinx where possible
- Auto-generated `api/index.md` with module summary table
- Full type hints in method signatures

### Cookbook Enrichments

- Tabbed code blocks (sphinx-design `{tab-set}`) for native/fluent side-by-side
- Category grouping in index (Basics, Workflows, Advanced, Patterns)
- "What you'll learn" summary per page
- Cross-links to API reference pages

### Migration Guide Enrichments

- Before/after code snippets for common patterns
- Links from each row to full API reference
- Searchable tables with anchors

### New Outputs

- `docs/api/index.md` — auto-generated module overview
- `docs/cookbook/index.md` — auto-generated cookbook index with categories

## CI/CD Integration

### New `docs` stage in `.gitlab-ci.yml`

Runs after `test`, before `build`:
1. Runs codegen pipeline (scanner → seed → generator)
2. Runs `doc_generator.py` to produce enriched Markdown
3. Runs `sphinx-build` to validate the docs compile
4. Stores HTML artifacts

Triggered on: version tags, manual web runs, and changes to docs/scripts/seeds.

### `.readthedocs.yaml`

RTD config that:
1. Installs google-adk and project in editable mode
2. Runs the pre-build codegen pipeline (scanner → seed → generator → doc_generator)
3. Builds Sphinx from `docs/conf.py`

### `pyproject.toml`

New `docs` optional dependency group:
```
docs = ["sphinx", "myst-parser", "sphinx-design", "furo", "sphinx-copybutton"]
```

## Dependencies

- `sphinx` — documentation build engine
- `myst-parser` — Markdown support for Sphinx
- `sphinx-design` — tabs, cards, grids, dropdowns
- `furo` — modern Sphinx theme
- `sphinx-copybutton` — copy button on code blocks
