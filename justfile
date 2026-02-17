# ============================================================================
# ADK-FLUENT DEVELOPMENT WORKFLOW
# ============================================================================
#
#   just all        → Full pipeline: scan → seed → generate → docs
#   just scan       → Introspect installed ADK, produce manifest.json
#   just seed       → Generate seed.toml from manifest.json
#   just generate   → Combine seed.toml + manifest.json → code + stubs + tests
#   just docs       → Generate all documentation
#   just test       → Run all tests
#   just typecheck  → Run pyright on generated stubs
#   just diff       → Show what changed since last scan
#   just clean      → Remove generated files
#
# First-time setup:
#   uv venv .venv && source .venv/bin/activate
#   uv pip install google-adk pytest pyright
#   just all
#

SEED          := "seeds/seed.toml"
MANIFEST      := "manifest.json"
PREV_MANIFEST := "manifest.previous.json"
OUTPUT_DIR    := "src/adk_fluent"
TEST_DIR      := "tests/generated"
SCANNER       := "scripts/scanner.py"
SEED_GEN      := "scripts/seed_generator.py"
GENERATOR     := "scripts/generator.py"
DOC_GEN       := "scripts/doc_generator.py"
COOKBOOK_GEN   := "scripts/cookbook_generator.py"
DOC_DIR       := "docs/generated"
SPHINX_OUT    := "docs/_build/html"
COOKBOOK_DIR   := "examples/cookbook"

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
generate: _require-manifest _require-seed
    @echo "Generating code from seed + manifest..."
    @uv run python {{GENERATOR}} {{SEED}} {{MANIFEST}} \
        --output-dir {{OUTPUT_DIR}} \
        --test-dir {{TEST_DIR}}

# --- Stubs only (fast regeneration) ---
stubs: _require-manifest _require-seed
    @echo "Regenerating .pyi stubs only..."
    @uv run python {{GENERATOR}} {{SEED}} {{MANIFEST}} \
        --output-dir {{OUTPUT_DIR}} \
        --stubs-only

# --- Tests ---
test:
    @echo "Running tests..."
    @uv run pytest tests/ -v --tb=short

# --- Type checking ---
typecheck:
    @echo "Type-checking generated stubs..."
    @uv run pyright {{OUTPUT_DIR}}/ --pythonversion 3.12

# --- Documentation ---
docs: _require-manifest _require-seed
    @echo "Generating documentation..."
    @uv run python {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --cookbook-dir {{COOKBOOK_DIR}}

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
    @echo "Building and serving docs at http://localhost:8000..."
    @uv run sphinx-build -b html docs/ {{SPHINX_OUT}}
    @cd {{SPHINX_OUT}} && python -m http.server 8000

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
    @uv run hatch build

# --- Publish to TestPyPI ---
publish-test: build
    @echo "Publishing to TestPyPI..."
    @uv run hatch publish -r test

# --- Publish to PyPI ---
publish: build
    @echo "Publishing to PyPI..."
    @uv run hatch publish

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
    @echo "  just all            Full pipeline: scan -> seed -> generate -> docs"
    @echo "  just scan           Introspect ADK -> manifest.json"
    @echo "  just seed           manifest.json -> seed.toml"
    @echo "  just generate       seed.toml + manifest.json -> code"
    @echo "  just stubs          Regenerate .pyi stubs only"
    @echo "  just test           Run pytest suite"
    @echo "  just typecheck      Run pyright type-check"
    @echo "  just docs           Generate all documentation"
    @echo "  just docs-api       Generate API reference only"
    @echo "  just docs-cookbook   Generate cookbook only"
    @echo "  just docs-migration Generate migration guide only"
    @echo "  just docs-build     Build Sphinx HTML documentation"
    @echo "  just docs-serve     Build and serve docs at localhost:8000"
    @echo "  just cookbook-gen    Generate cookbook example stubs"
    @echo "  just cookbook-gen-dry Preview cookbook stubs (dry-run)"
    @echo "  just agents         Convert cookbook -> adk web folders"
    @echo "  just diff           Show changes since last scan"
    @echo "  just build          Build pip package"
    @echo "  just publish        Publish to PyPI"
    @echo "  just clean          Remove generated files"
    @echo ""
    @echo "Workflow: just all -> just test -> commit"

# --- Internal: prerequisite checks ---
[private]
_require-manifest:
    @test -f {{MANIFEST}} || (echo "ERROR: {{MANIFEST}} not found. Run 'just scan' first." && exit 1)

[private]
_require-seed:
    @test -f {{SEED}} || (echo "ERROR: {{SEED}} not found. Run 'just seed' first." && exit 1)
