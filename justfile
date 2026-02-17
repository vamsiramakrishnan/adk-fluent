# ============================================================================
# ADK-FLUENT DEVELOPMENT WORKFLOW
# ============================================================================
#
#   just all        → Full pipeline: scan → seed → generate
#   just scan       → Introspect installed ADK, produce manifest.json
#   just seed       → Generate seed.toml from manifest.json
#   just generate   → Combine seed.toml + manifest.json → code + stubs + tests
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

# --- Full pipeline ---
all: scan seed generate
    @echo "\nPipeline complete. Generated code in {{OUTPUT_DIR}}/"

# --- Scan ADK ---
scan:
    @echo "Scanning installed google-adk..."
    @python {{SCANNER}} -o {{MANIFEST}}
    @python {{SCANNER}} --summary

# --- Generate seed.toml from manifest ---
seed: _require-manifest
    @echo "Generating seed.toml from manifest..."
    @python {{SEED_GEN}} {{MANIFEST}} -o {{SEED}}

# --- Generate code ---
generate: _require-manifest _require-seed
    @echo "Generating code from seed + manifest..."
    @python {{GENERATOR}} {{SEED}} {{MANIFEST}} \
        --output-dir {{OUTPUT_DIR}} \
        --test-dir {{TEST_DIR}}

# --- Stubs only (fast regeneration) ---
stubs: _require-manifest _require-seed
    @echo "Regenerating .pyi stubs only..."
    @python {{GENERATOR}} {{SEED}} {{MANIFEST}} \
        --output-dir {{OUTPUT_DIR}} \
        --stubs-only

# --- Tests ---
test:
    @echo "Running tests..."
    @pytest tests/ -v --tb=short

# --- Type checking ---
typecheck:
    @echo "Type-checking generated stubs..."
    @pyright {{OUTPUT_DIR}}/ --pythonversion 3.12

# --- Diff against previous ---
diff:
    #!/usr/bin/env bash
    if [ -f {{PREV_MANIFEST}} ]; then
        echo "Changes since last scan:"
        python {{SCANNER}} --diff {{PREV_MANIFEST}}
    else
        echo "No previous manifest found. Run 'just scan' first."
    fi

# --- Summary ---
summary:
    @python {{SCANNER}} --summary

# --- Archive current manifest ---
archive:
    @cp {{MANIFEST}} {{PREV_MANIFEST}}
    @echo "Archived {{MANIFEST}} -> {{PREV_MANIFEST}}"

# --- Package build ---
build: all
    @echo "Building package..."
    @hatch build

# --- Publish to TestPyPI ---
publish-test: build
    @echo "Publishing to TestPyPI..."
    @hatch publish -r test

# --- Publish to PyPI ---
publish: build
    @echo "Publishing to PyPI..."
    @hatch publish

# --- Clean ---
clean:
    @echo "Cleaning generated files..."
    @rm -rf {{OUTPUT_DIR}}/*.py {{OUTPUT_DIR}}/*.pyi
    @rm -rf {{TEST_DIR}}/
    @rm -f {{MANIFEST}}
    @echo "Done."

# --- Help ---
help:
    @echo "ADK-FLUENT Development Commands:"
    @echo ""
    @echo "  just all        Full pipeline: scan -> seed -> generate"
    @echo "  just scan       Introspect ADK -> manifest.json"
    @echo "  just seed       manifest.json -> seed.toml"
    @echo "  just generate   seed.toml + manifest.json -> code"
    @echo "  just stubs      Regenerate .pyi stubs only"
    @echo "  just test       Run pytest suite"
    @echo "  just typecheck  Run pyright type-check"
    @echo "  just diff       Show changes since last scan"
    @echo "  just build      Build pip package"
    @echo "  just publish    Publish to PyPI"
    @echo "  just clean      Remove generated files"
    @echo ""
    @echo "Workflow: just all -> just test -> commit"

# --- Internal: prerequisite checks ---
[private]
_require-manifest:
    @test -f {{MANIFEST}} || (echo "ERROR: {{MANIFEST}} not found. Run 'just scan' first." && exit 1)

[private]
_require-seed:
    @test -f {{SEED}} || (echo "ERROR: {{SEED}} not found. Run 'just seed' first." && exit 1)
