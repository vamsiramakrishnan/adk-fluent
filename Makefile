# ============================================================================
# ADK-FLUENT DEVELOPMENT WORKFLOW
# ============================================================================
#
#   make all        → Full pipeline: scan → seed → generate
#   make scan       → Introspect installed ADK, produce manifest.json
#   make seed       → Generate seed.toml from manifest.json
#   make generate   → Combine seed.toml + manifest.json → code + stubs + tests
#   make test       → Run all tests
#   make typecheck  → Run pyright on generated stubs
#   make diff       → Show what changed since last scan
#   make clean      → Remove generated files
#
# First-time setup:
#   uv venv .venv && source .venv/bin/activate
#   uv pip install google-adk pytest pyright
#   make all
#

SEED          := seeds/seed.toml
MANIFEST      := manifest.json
PREV_MANIFEST := manifest.previous.json
OUTPUT_DIR    := src/adk_fluent
TEST_DIR      := tests/generated
SCANNER       := scripts/scanner.py
SEED_GEN      := scripts/seed_generator.py
GENERATOR     := scripts/generator.py

.PHONY: all scan seed generate test typecheck diff clean summary help build publish publish-test

# --- Full pipeline ---
all: scan seed generate
	@echo "\nPipeline complete. Generated code in $(OUTPUT_DIR)/"

# --- Scan ADK ---
scan:
	@echo "Scanning installed google-adk..."
	@python $(SCANNER) -o $(MANIFEST)
	@python $(SCANNER) --summary

# --- Generate seed.toml from manifest ---
seed: $(MANIFEST)
	@echo "Generating seed.toml from manifest..."
	@python $(SEED_GEN) $(MANIFEST) -o $(SEED)

# --- Generate code ---
generate: $(MANIFEST) $(SEED)
	@echo "Generating code from seed + manifest..."
	@python $(GENERATOR) $(SEED) $(MANIFEST) \
		--output-dir $(OUTPUT_DIR) \
		--test-dir $(TEST_DIR)

# --- Stubs only (fast regeneration) ---
stubs: $(MANIFEST) $(SEED)
	@echo "Regenerating .pyi stubs only..."
	@python $(GENERATOR) $(SEED) $(MANIFEST) \
		--output-dir $(OUTPUT_DIR) \
		--stubs-only

# --- Tests ---
test:
	@echo "Running tests..."
	@pytest tests/ -v --tb=short

# --- Type checking ---
typecheck:
	@echo "Type-checking generated stubs..."
	@pyright $(OUTPUT_DIR)/ --pythonversion 3.12

# --- Diff against previous ---
diff:
	@if [ -f $(PREV_MANIFEST) ]; then \
		echo "Changes since last scan:"; \
		python $(SCANNER) --diff $(PREV_MANIFEST); \
	else \
		echo "No previous manifest found. Run 'make scan' first."; \
	fi

# --- Summary ---
summary:
	@python $(SCANNER) --summary

# --- Archive current manifest ---
archive:
	@cp $(MANIFEST) $(PREV_MANIFEST)
	@echo "Archived $(MANIFEST) -> $(PREV_MANIFEST)"

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
	@rm -rf $(OUTPUT_DIR)/*.py $(OUTPUT_DIR)/*.pyi
	@rm -rf $(TEST_DIR)/
	@rm -f $(MANIFEST)
	@echo "Done."

# --- Help ---
help:
	@echo "ADK-FLUENT Development Commands:"
	@echo ""
	@echo "  make all        Full pipeline: scan -> seed -> generate"
	@echo "  make scan       Introspect ADK -> manifest.json"
	@echo "  make seed       manifest.json -> seed.toml"
	@echo "  make generate   seed.toml + manifest.json -> code"
	@echo "  make stubs      Regenerate .pyi stubs only"
	@echo "  make test       Run pytest suite"
	@echo "  make typecheck  Run pyright type-check"
	@echo "  make diff       Show changes since last scan"
	@echo "  make build      Build pip package"
	@echo "  make publish    Publish to PyPI"
	@echo "  make clean      Remove generated files"
	@echo ""
	@echo "Workflow: make all -> make test -> commit"
