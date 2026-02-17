# Documentation Publishing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Sphinx + MyST-Parser documentation site hosted on Read the Docs, with a major overhaul of `doc_generator.py` to produce rich, cross-linked documentation.

**Architecture:** Sphinx builds a static HTML site from hand-written guide pages (MyST Markdown) + auto-generated API/cookbook/migration pages (produced by `doc_generator.py`). Read the Docs auto-builds on push via `.readthedocs.yaml`. GitLab CI validates the docs build in a `docs` stage.

**Tech Stack:** Sphinx, MyST-Parser, sphinx-design (tabs/cards), Furo theme, sphinx-copybutton, Read the Docs hosting.

---

### Task 1: Add docs dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml:34-41`

**Step 1: Add docs optional dependency group**

Add `docs` to `[project.optional-dependencies]` after the `dev` group, and update the Documentation URL:

```toml
[project.optional-dependencies]
examples = [
    "python-dotenv>=1.0",
]
dev = [
    "pytest>=7.0",
    "pyright>=1.1",
]
docs = [
    "sphinx>=7.0",
    "myst-parser>=3.0",
    "sphinx-design>=0.6",
    "furo>=2024.0",
    "sphinx-copybutton>=0.5",
]
```

Also update `[project.urls]` Documentation value from the GitLab tree URL to the future RTD URL:
```toml
Documentation = "https://adk-fluent.readthedocs.io/"
```

**Step 2: Install the docs dependencies locally**

Run: `cd /home/user/adk-fluent && pip install -e ".[docs]"`
Expected: all sphinx packages install successfully.

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add docs optional dependencies (sphinx, myst-parser, furo, sphinx-design)"
```

---

### Task 2: Create Sphinx conf.py

**Files:**
- Create: `docs/conf.py`

**Step 1: Write conf.py**

```python
"""Sphinx configuration for adk-fluent documentation."""

project = "adk-fluent"
copyright = "2025, adk-fluent contributors"
author = "adk-fluent contributors"

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
    "sphinx.ext.intersphinx",
]

# MyST settings
myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
    "deflist",
    "attrs_block",
]
myst_heading_anchors = 3

# Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Theme
html_theme = "furo"
html_title = "adk-fluent"
html_theme_options = {
    "source_repository": "https://gitlab.com/google-cloud-ce/googlers/vamramak/adk-fluent",
    "source_branch": "master",
    "source_directory": "docs/",
}

# Source settings
source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}
exclude_patterns = ["_build", "plans", "generated/cookbook/conftest.md"]

# Suppress warnings for missing toctree references in auto-generated files
suppress_warnings = ["myst.header"]
```

**Step 2: Validate Sphinx can find the config**

Run: `cd /home/user/adk-fluent && python -c "import sphinx; print(sphinx.__version__)"`
Expected: prints Sphinx version without error.

**Step 3: Commit**

```bash
git add docs/conf.py
git commit -m "feat: add Sphinx conf.py with MyST, Furo, sphinx-design"
```

---

### Task 3: Create hand-written documentation pages

**Files:**
- Create: `docs/index.md`
- Create: `docs/getting-started.md`
- Create: `docs/changelog.md`
- Create: `docs/user-guide/index.md`
- Create: `docs/user-guide/builders.md`
- Create: `docs/user-guide/expression-language.md`
- Create: `docs/user-guide/prompts.md`
- Create: `docs/user-guide/execution.md`
- Create: `docs/user-guide/callbacks.md`
- Create: `docs/user-guide/presets.md`
- Create: `docs/user-guide/state-transforms.md`
- Create: `docs/contributing/index.md`
- Create: `docs/contributing/codegen-pipeline.md`
- Create: `docs/contributing/adding-builders.md`

**Step 1: Create docs/index.md (landing page with toctree)**

The index page serves as the root toctree and landing page. It must include toctrees for all sections so Sphinx discovers every page. Content should be extracted/adapted from the existing README.md — the project description, install command, quick start code, and feature highlights.

```markdown
# adk-fluent

Fluent builder API for Google's [Agent Development Kit (ADK)](https://google.github.io/adk-docs/).
Reduces agent creation from 22+ lines to 1-3 lines while producing identical native ADK objects.

## Install

\`\`\`bash
pip install adk-fluent
\`\`\`

## Quick Example

\`\`\`python
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are helpful.").build()
\`\`\`

Every `.build()` returns a real ADK object — fully compatible with `adk web`, `adk run`, and `adk deploy`.

\`\`\`{toctree}
:maxdepth: 2
:caption: Getting Started

getting-started
\`\`\`

\`\`\`{toctree}
:maxdepth: 2
:caption: User Guide

user-guide/index
\`\`\`

\`\`\`{toctree}
:maxdepth: 2
:caption: API Reference

generated/api/index
\`\`\`

\`\`\`{toctree}
:maxdepth: 2
:caption: Cookbook

generated/cookbook/index
\`\`\`

\`\`\`{toctree}
:maxdepth: 1
:caption: Migration

generated/migration/from-native-adk
\`\`\`

\`\`\`{toctree}
:maxdepth: 2
:caption: Contributing

contributing/index
\`\`\`

\`\`\`{toctree}
:maxdepth: 1
:caption: Project

changelog
\`\`\`
```

**Step 2: Create docs/getting-started.md**

Content adapted from README.md sections: Install, IDE Setup, Discover the API, Quick Start, Two Styles. Include installation, IDE setup (VS Code, PyCharm, Neovim), the discover-the-API snippet, and the quick start examples (Agent, Pipeline, FanOut, Loop).

**Step 3: Create docs/changelog.md**

A stub changelog:
```markdown
# Changelog

## v0.2.2

- Fix: exclude `.pip-cache` from sdist

## v0.2.1

- Internal improvements

## v0.2.0

- Expression algebra release (>>, |, *, @, //, Route, S operators)
- Prompt builder
- State transforms
```

**Step 4: Create user guide pages**

Each page should be extracted from the relevant README sections. The user-guide/index.md has a toctree listing all sub-pages:

```markdown
# User Guide

\`\`\`{toctree}
:maxdepth: 2

builders
expression-language
prompts
execution
callbacks
presets
state-transforms
\`\`\`
```

Create each sub-page with content from README.md:
- `builders.md` — How the builder pattern works, constructor args, method chaining, .build()
- `expression-language.md` — All operators: >>, |, *, @, //, Route, S
- `prompts.md` — Prompt builder with sections (role, context, task, constraints, format, examples)
- `execution.md` — .ask(), .ask_async(), .stream(), .session(), .map(), .events(), .test()
- `callbacks.md` — Callback system, additive semantics, conditional callbacks
- `presets.md` — Preset bundles
- `state-transforms.md` — S.pick(), S.drop(), S.rename(), S.merge(), S.compute(), S.guard(), S.log()

**Step 5: Create contributing pages**

`contributing/index.md`:
```markdown
# Contributing

\`\`\`{toctree}
:maxdepth: 2

codegen-pipeline
adding-builders
\`\`\`
```

- `codegen-pipeline.md` — Explain the 5-stage pipeline: scanner → seed_generator → generator → doc_generator → cookbook_generator. Reference exact scripts and their CLIs.
- `adding-builders.md` — How to add or customize builders via seed.manual.toml, how to add extras, how to regenerate.

**Step 6: Verify Sphinx builds**

Run: `cd /home/user/adk-fluent && sphinx-build -b html docs/ docs/_build/html 2>&1 | tail -20`
Expected: Build succeeds (warnings about missing generated/ files are OK at this stage).

**Step 7: Commit**

```bash
git add docs/index.md docs/getting-started.md docs/changelog.md docs/user-guide/ docs/contributing/
git commit -m "feat: add hand-written documentation pages (guide, contributing, changelog)"
```

---

### Task 4: Overhaul doc_generator.py — API reference

**Files:**
- Modify: `scripts/doc_generator.py`

This is the major overhaul. The new doc_generator.py produces MyST-flavored Markdown with cross-references, admonitions, inline examples, and auto-generated index pages.

**Step 1: Rewrite gen_api_reference_for_builder()**

Changes from current:
- Add inline usage example (2-3 lines) at top of each builder section showing basic construction
- Use MyST admonitions (`:::{note}`, `:::{tip}`) for important notes like additive semantics
- Add MyST target anchors (`(builder-Name)=`) for cross-referencing
- Better type rendering in method signatures
- Add "See also" links to related builders (e.g., Agent → Pipeline, FanOut)

**Step 2: Rewrite gen_api_reference_module()**

Changes:
- Add module-level description
- Add a table of contents at the top listing all builders in the module

**Step 3: Add gen_api_index()**

New function that generates `docs/generated/api/index.md`:
- Module summary table: module name, builder count, link to page
- Total builder count
- Toctree listing all module pages

```python
def gen_api_index(by_module: dict[str, list[BuilderSpec]]) -> str:
    lines = []
    lines.append("# API Reference")
    lines.append("")
    lines.append("Complete reference for all adk-fluent builders.")
    lines.append("")
    lines.append("| Module | Builders | Description |")
    lines.append("|--------|----------|-------------|")
    # ... table rows per module
    lines.append("")
    lines.append("```{toctree}")
    lines.append(":maxdepth: 2")
    lines.append(":hidden:")
    lines.append("")
    for module_name in sorted(by_module):
        lines.append(module_name)
    lines.append("```")
    return "\n".join(lines)
```

**Step 4: Run the doc generator and verify output**

Run: `cd /home/user/adk-fluent && python scripts/doc_generator.py seeds/seed.toml manifest.json --api-only`
Expected: generates files in docs/generated/api/ with MyST syntax.

**Step 5: Commit**

```bash
git add scripts/doc_generator.py
git commit -m "feat: overhaul doc_generator.py API reference with MyST cross-refs, examples, index"
```

---

### Task 5: Overhaul doc_generator.py — Cookbook

**Files:**
- Modify: `scripts/doc_generator.py`

**Step 1: Rewrite cookbook_to_markdown()**

Changes from current:
- Use sphinx-design tab-set for native/fluent side-by-side instead of sequential sections
- Add "What you'll learn" summary at top
- Add cross-links to relevant API reference pages
- Better title handling

New output format per cookbook page:
```markdown
# Simple Agent Creation

_Source: `01_simple_agent.py`_

**What you'll learn:** How to create a basic LLM agent using the fluent builder.

::::{tab-set}
:::{tab-item} Native ADK
\`\`\`python
# native code here
\`\`\`
:::
:::{tab-item} adk-fluent
\`\`\`python
# fluent code here
\`\`\`
:::
::::

## Equivalence Check
\`\`\`python
# assertions
\`\`\`

:::{seealso}
[Agent API Reference](../api/agent.md)
:::
```

**Step 2: Add gen_cookbook_index()**

New function that generates `docs/generated/cookbook/index.md`:
- Categorize cookbooks: Basics (01-07), Execution (08-13), Advanced (14-20), Patterns (21+)
- Category headers with toctree per category

**Step 3: Run and verify**

Run: `cd /home/user/adk-fluent && python scripts/doc_generator.py seeds/seed.toml manifest.json --cookbook-only`
Expected: cookbook files have tab-set syntax.

**Step 4: Commit**

```bash
git add scripts/doc_generator.py
git commit -m "feat: overhaul cookbook docs with tabbed code, categories, cross-links"
```

---

### Task 6: Overhaul doc_generator.py — Migration guide

**Files:**
- Modify: `scripts/doc_generator.py`

**Step 1: Enhance gen_migration_guide()**

Changes:
- Add before/after code snippets for the 3 most common patterns (Agent, Pipeline, FanOut)
- Add MyST target anchors for each builder row
- Add links from each builder name to its API reference page
- Add an intro section explaining the migration path

**Step 2: Run and verify**

Run: `cd /home/user/adk-fluent && python scripts/doc_generator.py seeds/seed.toml manifest.json --migration-only`

**Step 3: Commit**

```bash
git add scripts/doc_generator.py
git commit -m "feat: enrich migration guide with code snippets and cross-links"
```

---

### Task 7: Full Sphinx build validation

**Files:**
- Possibly modify: `docs/conf.py` (fix any warnings)

**Step 1: Run the full doc pipeline**

```bash
cd /home/user/adk-fluent
python scripts/doc_generator.py seeds/seed.toml manifest.json --output-dir docs/generated --cookbook-dir examples/cookbook
```

**Step 2: Build with Sphinx**

Run: `sphinx-build -W --keep-going -b html docs/ docs/_build/html 2>&1`
Expected: Build succeeds. Fix any warnings/errors by adjusting conf.py or generated output.

Note: Use `-W` (warnings as errors) with `--keep-going` to catch all issues. Some warnings about cross-references to external docs may need to be suppressed in conf.py.

**Step 3: Commit any fixes**

```bash
git add docs/ scripts/
git commit -m "fix: resolve Sphinx build warnings"
```

---

### Task 8: Add .readthedocs.yaml

**Files:**
- Create: `.readthedocs.yaml`

**Step 1: Write .readthedocs.yaml**

```yaml
version: 2

build:
  os: ubuntu-22.04
  tools:
    python: "3.12"
  jobs:
    pre_build:
      - pip install google-adk
      - pip install -e ".[docs]"
      - python scripts/scanner.py -o manifest.json
      - python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
      - python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
      - python scripts/doc_generator.py seeds/seed.toml manifest.json --output-dir docs/generated --cookbook-dir examples/cookbook

sphinx:
  configuration: docs/conf.py

python:
  install:
    - method: pip
      path: .
      extra_requirements:
        - docs
```

**Step 2: Commit**

```bash
git add .readthedocs.yaml
git commit -m "feat: add .readthedocs.yaml for automated doc builds"
```

---

### Task 9: Add docs stage to .gitlab-ci.yml

**Files:**
- Modify: `.gitlab-ci.yml:1-4` (add docs stage)
- Modify: `.gitlab-ci.yml` (add docs job)

**Step 1: Add docs stage and job**

Add `docs` to the stages list (after test, before build):

```yaml
stages:
  - test
  - docs
  - build
  - publish
```

Add the docs job after the test jobs and before the build job:

```yaml
# ---------------------------------------------------------------------------
# DOCS — build and validate documentation
# ---------------------------------------------------------------------------

docs:
  stage: docs
  image: python:3.12
  before_script:
    - pip install google-adk
    - pip install -e ".[docs,dev]"
  script:
    - python scripts/scanner.py -o manifest.json
    - python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
    - python scripts/generator.py seeds/seed.toml manifest.json
        --output-dir src/adk_fluent
        --test-dir tests/generated
    - python scripts/doc_generator.py seeds/seed.toml manifest.json
        --output-dir docs/generated
        --cookbook-dir examples/cookbook
    - sphinx-build -W --keep-going -b html docs/ docs/_build/html
  artifacts:
    paths:
      - docs/_build/html/
    expire_in: 1 week
  rules:
    - if: $CI_COMMIT_TAG =~ /^v/
    - if: $CI_PIPELINE_SOURCE == "web"
    - changes:
        - docs/**/*
        - scripts/doc_generator.py
        - seeds/**/*
```

**Step 2: Commit**

```bash
git add .gitlab-ci.yml
git commit -m "feat: add docs stage to CI pipeline for Sphinx build validation"
```

---

### Task 10: Update justfile with Sphinx commands

**Files:**
- Modify: `justfile`

**Step 1: Add docs-build and docs-serve commands**

Add after the existing `docs-migration` recipe:

```just
# --- Sphinx build ---
docs-build: docs
    @echo "Building Sphinx documentation..."
    @uv run sphinx-build -W --keep-going -b html docs/ docs/_build/html

# --- Sphinx live preview ---
docs-serve: docs
    @echo "Building and serving docs at http://localhost:8000..."
    @uv run sphinx-build -b html docs/ docs/_build/html
    @cd docs/_build/html && python -m http.server 8000
```

Update the `all` recipe to include docs-build:
```just
all: scan seed generate docs docs-build
```

Update `clean` to also remove `docs/_build`:
```just
clean:
    @echo "Cleaning generated files..."
    @rm -rf {{OUTPUT_DIR}}/*.py {{OUTPUT_DIR}}/*.pyi
    @rm -rf {{TEST_DIR}}/
    @rm -rf {{DOC_DIR}}/
    @rm -rf docs/_build/
    @rm -f {{MANIFEST}}
    @echo "Done."
```

Update `help` to list new commands.

**Step 2: Commit**

```bash
git add justfile
git commit -m "feat: add docs-build and docs-serve to justfile"
```

---

### Task 11: Final integration test

**Step 1: Run the full pipeline end-to-end**

```bash
cd /home/user/adk-fluent
python scripts/scanner.py -o manifest.json
python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
python scripts/generator.py seeds/seed.toml manifest.json --output-dir src/adk_fluent --test-dir tests/generated
python scripts/doc_generator.py seeds/seed.toml manifest.json --output-dir docs/generated --cookbook-dir examples/cookbook
sphinx-build -b html docs/ docs/_build/html
```

Expected: All commands succeed. HTML site generated in `docs/_build/html/`.

**Step 2: Run existing tests to ensure nothing broke**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass.

**Step 3: Verify the generated site structure**

Run: `find docs/_build/html -name "*.html" | head -30`
Expected: HTML files for index, getting-started, user-guide pages, api pages, cookbook pages, migration, contributing, changelog.

**Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "feat: complete documentation publishing system with Sphinx + RTD"
```
