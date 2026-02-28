# ============================================================================
# ADK-FLUENT DEVELOPMENT WORKFLOW
# ============================================================================
#
#   just setup      → First-time setup: install deps + pre-commit hooks
#   just all        → Full pipeline: scan → seed → generate → docs
#   just scan       → Introspect installed ADK, produce manifest.json
#   just seed       → Generate seed.toml from manifest.json
#   just generate   → Combine seed.toml + manifest.json → code + stubs + tests + lint
#   just lint       → Run ruff check + format check (hand-written files only)
#   just fmt        → Auto-format hand-written files (ruff + mdformat)
#   just fmt-changed → Auto-format only changed hand-written files (fast)
#   just check-gen  → Verify generated files are up-to-date (idempotency)
#   just docs       → Generate all documentation
#   just test       → Run all tests
#   just typecheck  → Run pyright on generated stubs
#   just diff       → Show what changed since last scan
#   just clean      → Remove generated files
#
#   --- 100x DX COMMANDS ---
#   just watch      → Auto-run generate+test on changes
#   just repl       → Pre-loaded IPython playground
#   just add-cookbook "Name" → Scaffold new example
#
# First-time setup:
#   just setup
#
# Architecture note:
#   Generated files (agent.py, workflow.py, etc.) are owned by `just generate`.
#   Hand-written files (_base.py, _context.py, etc.) are owned by developers.
#   Formatters and pre-commit ONLY touch hand-written files.
#   `just generate` formats its own output as part of the generation pipeline.
#   See .gitattributes for the full generated file list.
#

# --- First-time setup ---
setup:
    @echo "Installing dependencies..."
    @uv sync --all-extras
    @echo "Installing pre-commit hooks..."
    @uv run pre-commit install
    @echo ""
    @echo "Setup complete. Pre-commit hooks will auto-format on every commit."
    @echo "Run 'just all' to generate code, or 'just fmt' to format existing files."

SEED          := "seeds/seed.toml"
MANIFEST      := "manifest.json"
PREV_MANIFEST := "manifest.previous.json"
OUTPUT_DIR    := "src/adk_fluent"
TEST_DIR      := "tests/generated"
SCANNER       := "scripts/scanner.py"
SEED_GEN      := "scripts/seed_generator.py"
GENERATOR     := "scripts/generator.py"
IR_GEN        := "scripts/ir_generator.py"
DOC_GEN       := "scripts/doc_generator.py"
COOKBOOK_GEN   := "scripts/cookbook_generator.py"
DOC_DIR       := "docs/generated"
SPHINX_OUT    := "docs/_build/html"
COOKBOOK_DIR   := "examples/cookbook"

# Generated files — owned by `just generate`, not by formatters or pre-commit.
# This is the single source of truth; .pre-commit-config.yaml and .gitattributes mirror it.
GENERATED_PY  := "src/adk_fluent/agent.py src/adk_fluent/config.py src/adk_fluent/executor.py src/adk_fluent/planner.py src/adk_fluent/plugin.py src/adk_fluent/runtime.py src/adk_fluent/service.py src/adk_fluent/tool.py src/adk_fluent/workflow.py src/adk_fluent/_ir_generated.py"

# Hand-written files that live inside OUTPUT_DIR but must stay writable.
HANDWRITTEN   := "src/adk_fluent/__init__.py src/adk_fluent/_base.py src/adk_fluent/_routing.py src/adk_fluent/_transforms.py src/adk_fluent/_prompt.py src/adk_fluent/_helpers.py src/adk_fluent/_context.py src/adk_fluent/_visibility.py src/adk_fluent/cli.py"

# --- Full pipeline ---
all: scan seed generate docs docs-build
    @echo "\nPipeline complete. Generated code in {{OUTPUT_DIR}}/ and docs in {{DOC_DIR}}/"

# --- Scan ADK ---
scan:
    @echo "Scanning installed google-adk..."
    @uv run python {{SCANNER}} -o {{MANIFEST}}
    @uv run python {{SCANNER}} --summary

# --- Generate seed.toml from manifest ---
seed: _require-manifest
    @echo "Generating seed.toml from manifest..."
    @uv run python {{SEED_GEN}} {{MANIFEST}} -o {{SEED}} --merge seeds/seed.manual.toml

# --- Generate code ---
# The generator owns its output files end-to-end: emit → format → read-only.
# Formatting is scoped to generated files only — never touches hand-written code.
generate: _require-manifest _require-seed
    @echo "Generating code from seed + manifest..."
    @# Make files writable for generation
    @chmod -R +w {{OUTPUT_DIR}} {{TEST_DIR}} || true
    @uv run python {{GENERATOR}} {{SEED}} {{MANIFEST}} \
        --output-dir {{OUTPUT_DIR}} \
        --test-dir {{TEST_DIR}}
    @uv run python {{IR_GEN}} {{MANIFEST}} --output {{OUTPUT_DIR}}/_ir_generated.py
    @# Format ONLY generated files — the generator owns formatting for its output
    @uv run ruff check --fix {{GENERATED_PY}} {{TEST_DIR}} || true
    @uv run ruff format {{GENERATED_PY}} {{TEST_DIR}}
    @uv run ruff check {{GENERATED_PY}} {{TEST_DIR}}
    @# Re-apply read-only trap on generated files
    @chmod -R -w {{OUTPUT_DIR}} {{TEST_DIR}} || true
    @# Restore write permission on hand-written files
    @chmod +w {{HANDWRITTEN}} || true

# --- Stubs only (fast regeneration) ---
stubs: _require-manifest _require-seed
    @echo "Regenerating .pyi stubs only..."
    @uv run python {{GENERATOR}} {{SEED}} {{MANIFEST}} \
        --output-dir {{OUTPUT_DIR}} \
        --stubs-only

# --- Lint (hand-written files only — generated files are the generator's responsibility) ---
lint:
    @echo "Running lint checks (hand-written files)..."
    @uv run ruff check --exclude {{OUTPUT_DIR}}/agent.py --exclude {{OUTPUT_DIR}}/config.py --exclude {{OUTPUT_DIR}}/executor.py --exclude {{OUTPUT_DIR}}/planner.py --exclude {{OUTPUT_DIR}}/plugin.py --exclude {{OUTPUT_DIR}}/runtime.py --exclude {{OUTPUT_DIR}}/service.py --exclude {{OUTPUT_DIR}}/tool.py --exclude {{OUTPUT_DIR}}/workflow.py --exclude {{OUTPUT_DIR}}/_ir_generated.py --exclude {{TEST_DIR}} .
    @uv run ruff format --check --exclude {{OUTPUT_DIR}}/agent.py --exclude {{OUTPUT_DIR}}/config.py --exclude {{OUTPUT_DIR}}/executor.py --exclude {{OUTPUT_DIR}}/planner.py --exclude {{OUTPUT_DIR}}/plugin.py --exclude {{OUTPUT_DIR}}/runtime.py --exclude {{OUTPUT_DIR}}/service.py --exclude {{OUTPUT_DIR}}/tool.py --exclude {{OUTPUT_DIR}}/workflow.py --exclude {{OUTPUT_DIR}}/_ir_generated.py --exclude {{TEST_DIR}} .
    @uv run mdformat --check .

# --- Format (hand-written files only — generated files are the generator's responsibility) ---
format:
    @echo "Formatting hand-written files..."
    @uv run ruff check --fix --exclude {{OUTPUT_DIR}}/agent.py --exclude {{OUTPUT_DIR}}/config.py --exclude {{OUTPUT_DIR}}/executor.py --exclude {{OUTPUT_DIR}}/planner.py --exclude {{OUTPUT_DIR}}/plugin.py --exclude {{OUTPUT_DIR}}/runtime.py --exclude {{OUTPUT_DIR}}/service.py --exclude {{OUTPUT_DIR}}/tool.py --exclude {{OUTPUT_DIR}}/workflow.py --exclude {{OUTPUT_DIR}}/_ir_generated.py --exclude {{TEST_DIR}} . || true
    @uv run ruff format --exclude {{OUTPUT_DIR}}/agent.py --exclude {{OUTPUT_DIR}}/config.py --exclude {{OUTPUT_DIR}}/executor.py --exclude {{OUTPUT_DIR}}/planner.py --exclude {{OUTPUT_DIR}}/plugin.py --exclude {{OUTPUT_DIR}}/runtime.py --exclude {{OUTPUT_DIR}}/service.py --exclude {{OUTPUT_DIR}}/tool.py --exclude {{OUTPUT_DIR}}/workflow.py --exclude {{OUTPUT_DIR}}/_ir_generated.py --exclude {{TEST_DIR}} .
    @uv run mdformat .

# --- Format (alias) ---
alias fmt := format

# --- Format changed files only (fast, excludes generated files) ---
fmt-changed:
    #!/usr/bin/env bash
    set -euo pipefail
    # Generated files that formatters must never touch
    generated_re='(agent|config|executor|planner|plugin|runtime|service|tool|workflow)\.(py|pyi)$|_ir_generated\.py$|^tests/generated/'
    py_files=$(git diff --name-only --diff-filter=d HEAD -- '*.py' | grep -Ev "$generated_re" || true)
    md_files=$(git diff --name-only --diff-filter=d HEAD -- '*.md' || true)
    if [ -n "$py_files" ]; then
        echo "Formatting $(echo "$py_files" | wc -w) Python files..."
        echo "$py_files" | xargs uv run ruff check --fix || true
        echo "$py_files" | xargs uv run ruff format
    fi
    if [ -n "$md_files" ]; then
        echo "Formatting $(echo "$md_files" | wc -w) Markdown files..."
        echo "$md_files" | xargs uv run mdformat
    fi
    if [ -z "$py_files" ] && [ -z "$md_files" ]; then
        echo "No changed hand-written .py or .md files to format."
    fi

# --- Verify generated files are up-to-date (idempotency gate) ---
check-gen: _require-manifest _require-seed
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Verifying generated files are up-to-date..."
    # Stash any uncommitted hand-written changes
    just generate
    if git diff --quiet -- {{GENERATED_PY}} {{TEST_DIR}}; then
        echo "Generated files are up-to-date."
    else
        echo "ERROR: Generated files are stale. Run 'just generate' and commit the result."
        git diff --stat -- {{GENERATED_PY}} {{TEST_DIR}}
        exit 1
    fi

# --- Tests ---
test:
    @echo "Running tests..."
    @uv run pytest tests/ -v --tb=short

# --- Pipeline tests only (fast inner loop) ---
test-pipeline:
    @echo "Running pipeline tests (generator/seed_generator/code_ir)..."
    @uv run pytest tests/test_code_ir.py tests/test_seed_generator.py tests/test_generator_golden.py tests/test_property_based.py -v --tb=short

# --- Update golden files ---
update-golden:
    @echo "Updating golden files..."
    @uv run pytest tests/test_generator_golden.py --update-golden -v

# --- Type checking ---
typecheck:
    @echo "Type-checking generated stubs..."
    @uv run pyright {{OUTPUT_DIR}}/*.pyi --pythonversion 3.12

# --- Type checking hand-written code ---
typecheck-core:
    @echo "Type-checking hand-written code..."
    @uv run pyright

# --- Watch mode ---
watch:
    @echo "Watching for changes..."
    @uv run watchfiles "just generate test typecheck" scripts/ seeds/ src/ tests/ manual/

# --- Documentation ---
docs: _require-manifest _require-seed
    @echo "Generating documentation..."
    @uv run python {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --cookbook-dir {{COOKBOOK_DIR}}
    @echo "Updating README.md from template..."
    @uv run python scripts/readme_generator.py
    @echo "Generating concepts documentation..."
    @uv run python scripts/concepts_generator.py

docs-api: _require-manifest _require-seed
    @echo "Generating API reference..."
    @uv run python {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --api-only

docs-cookbook: _require-manifest _require-seed
    @echo "Generating cookbook..."
    @uv run python {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --cookbook-dir {{COOKBOOK_DIR}} \
        --cookbook-only

docs-migration: _require-manifest _require-seed
    @echo "Generating migration guide..."
    @uv run python {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --migration-only

# --- Sphinx build ---
docs-build: docs
    @echo "Building Sphinx documentation..."
    @uv run sphinx-build -W --keep-going -b html docs/ {{SPHINX_OUT}}

# --- Sphinx live preview ---
docs-serve: docs
    @echo "Serving docs with live reload at http://localhost:8000..."
    @uv run sphinx-autobuild docs/ {{SPHINX_OUT}} --watch {{DOC_DIR}} --watch src/ --port 8000

# --- REPL ---
repl:
    @echo "Starting ADK-Fluent playground..."
    @uv run ipython -i -c "from adk_fluent import *; print('\nADK-Fluent playground loaded! (Agent, Pipeline, S, C available)')"

# --- Add Cookbook ---
add-cookbook name:
    @uv run python scripts/add_cookbook.py "{{name}}"

# --- Cookbook generation ---
cookbook-gen: _require-manifest _require-seed
    @echo "Generating cookbook example stubs..."
    @uv run python {{COOKBOOK_GEN}} {{SEED}} {{MANIFEST}} \
        --cookbook-dir {{COOKBOOK_DIR}}

cookbook-gen-dry: _require-manifest _require-seed
    @echo "Previewing cookbook example stubs..."
    @uv run python {{COOKBOOK_GEN}} {{SEED}} {{MANIFEST}} \
        --cookbook-dir {{COOKBOOK_DIR}} --dry-run

# --- Convert cookbook to adk-web agent folders ---
agents:
    @echo "Converting cookbook examples to adk-web agent folders..."
    @uv run python scripts/cookbook_to_agents.py --force

# --- Diff against previous ---
diff:
    #!/usr/bin/env bash
    if [ -f {{PREV_MANIFEST}} ]; then
        echo "Changes since last scan:"
        uv run python {{SCANNER}} --diff {{PREV_MANIFEST}}
    else
        echo "No previous manifest found. Run 'just scan' first."
    fi

# --- Diff as publishable Markdown page ---
diff-md:
    #!/usr/bin/env bash
    if [ -f {{PREV_MANIFEST}} ]; then
        echo "Generating API diff Markdown..."
        uv run python {{SCANNER}} --diff {{PREV_MANIFEST}} \
            --diff-markdown {{DOC_DIR}}/api-diff.md
        echo "Written to {{DOC_DIR}}/api-diff.md"
    else
        echo "No previous manifest found. Run 'just archive' before scanning, then 'just diff-md'."
    fi

# --- Summary ---
summary:
    @uv run python {{SCANNER}} --summary

# --- Archive current manifest ---
archive:
    @cp {{MANIFEST}} {{PREV_MANIFEST}}
    @echo "Archived {{MANIFEST}} -> {{PREV_MANIFEST}}"

# --- Package build ---
build: all
    @echo "Building package..."
    @uv build

# --- Publish to TestPyPI ---
publish-test: build
    @echo "Publishing to TestPyPI..."
    @uv publish --index testpypi

# --- Publish to PyPI ---
publish: build
    @echo "Publishing to PyPI..."
    @uv publish

# --- Clean ---
clean:
    @echo "Cleaning generated files..."
    @rm -rf {{OUTPUT_DIR}}/*.py {{OUTPUT_DIR}}/*.pyi
    @rm -rf {{TEST_DIR}}/
    @rm -rf {{DOC_DIR}}/
    @rm -rf docs/_build/
    @rm -f {{MANIFEST}}
    @echo "Done."

# --- Help ---
help:
    @echo "ADK-FLUENT Development Commands:"
    @echo ""
    @echo "  just setup          First-time setup: install deps + pre-commit hooks"
    @echo "  just all            Full pipeline: scan -> seed -> generate -> docs"
    @echo "  just scan           Introspect ADK -> manifest.json"
    @echo "  just seed           manifest.json -> seed.toml"
    @echo "  just generate       seed.toml + manifest.json -> code (self-formatting)"
    @echo "  just stubs          Regenerate .pyi stubs only"
    @echo "  just lint           Lint hand-written files (ruff check + format check)"
    @echo "  just fmt            Auto-format hand-written files (ruff + mdformat)"
    @echo "  just fmt-changed    Auto-format only changed hand-written files (fast)"
    @echo "  just check-gen      Verify generated files are up-to-date"
    @echo "  just test           Run pytest suite"
    @echo "  just test-pipeline  Run pipeline tests only (fast <5s)"
    @echo "  just update-golden  Regenerate golden files"
    @echo "  just typecheck      Run pyright type-check"
    @echo "  just watch          Auto-run generate+test on changes"
    @echo "  just repl           Pre-loaded IPython playground"
    @echo "  just add-cookbook    Scaffold new example"
    @echo "  just docs           Generate all documentation"
    @echo "  just docs-api       Generate API reference only"
    @echo "  just docs-cookbook   Generate cookbook only"
    @echo "  just docs-migration Generate migration guide only"
    @echo "  just docs-build     Build Sphinx HTML documentation"
    @echo "  just docs-serve     Build and serve docs with live reload"
    @echo "  just cookbook-gen    Generate cookbook example stubs"
    @echo "  just cookbook-gen-dry Preview cookbook stubs (dry-run)"
    @echo "  just agents         Convert cookbook -> adk web folders"
    @echo "  just diff           Show changes since last scan (JSON)"
    @echo "  just diff-md        Generate API diff as docs/generated/api-diff.md"
    @echo "  just build          Build pip package"
    @echo "  just publish        Publish to PyPI"
    @echo "  just clean          Remove generated files"
    @echo ""
    @echo "Workflow: just setup -> just all -> just test -> commit"
    @echo ""
    @echo "Architecture: Generated files are owned by 'just generate'."
    @echo "              Formatters and pre-commit only touch hand-written files."
    @echo "              See .gitattributes for the generated file list."

# --- Internal: prerequisite checks ---
[private]
_require-manifest:
    @test -f {{MANIFEST}} || (echo "ERROR: {{MANIFEST}} not found. Run 'just scan' first." && exit 1)

[private]
_require-seed:
    @test -f {{SEED}} || (echo "ERROR: {{SEED}} not found. Run 'just seed' first." && exit 1)
