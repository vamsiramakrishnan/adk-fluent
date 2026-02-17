# ============================================================================
# ADK-FLUENT DEVELOPMENT WORKFLOW
# ============================================================================
#
#   make scan       → Introspect installed ADK, produce manifest.json
#   make generate   → Combine seed.toml + manifest.json → code + stubs + tests
#   make all        → scan + generate (the full pipeline)
#   make test       → Run all tests
#   make typecheck  → Run pyright on generated stubs
#   make diff       → Show what changed since last scan
#   make clean      → Remove generated files
#
# First-time setup:
#   pip install google-adk tomli pyright pytest
#   make all
#

SEED          := seeds/seed.toml
MANIFEST      := manifest.json
PREV_MANIFEST := manifest.previous.json
OUTPUT_DIR    := src/adk_fluent
TEST_DIR      := tests/generated
SCANNER       := scripts/scanner.py
GENERATOR     := scripts/generator.py

.PHONY: all scan generate test typecheck diff clean summary

# --- Full pipeline ---
all: scan generate
	@echo "\n✅ Pipeline complete. Generated code in $(OUTPUT_DIR)/"

# --- Scan ADK ---
scan:
	@echo "🔍 Scanning installed google-adk..."
	@python $(SCANNER) -o $(MANIFEST)
	@python $(SCANNER) --summary

# --- Generate code ---
generate: $(MANIFEST) $(SEED)
	@echo "\n⚙️  Generating code from seed + manifest..."
	@python $(GENERATOR) $(SEED) $(MANIFEST) \
		--output-dir $(OUTPUT_DIR) \
		--test-dir $(TEST_DIR)

# --- Stubs only (fast regeneration) ---
stubs: $(MANIFEST) $(SEED)
	@echo "📝 Regenerating .pyi stubs only..."
	@python $(GENERATOR) $(SEED) $(MANIFEST) \
		--output-dir $(OUTPUT_DIR) \
		--stubs-only

# --- Tests ---
test:
	@echo "🧪 Running tests..."
	@pytest tests/ -v --tb=short

# --- Type checking ---
typecheck:
	@echo "🔎 Type-checking generated stubs..."
	@pyright $(OUTPUT_DIR)/ --pythonversion 3.12

# --- Diff against previous ---
diff:
	@if [ -f $(PREV_MANIFEST) ]; then \
		echo "📊 Changes since last scan:"; \
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
	@echo "Archived $(MANIFEST) → $(PREV_MANIFEST)"

# --- Clean ---
clean:
	@echo "🧹 Cleaning generated files..."
	@rm -rf $(OUTPUT_DIR)/*.py $(OUTPUT_DIR)/*.pyi
	@rm -rf $(TEST_DIR)/
	@rm -f $(MANIFEST)
	@echo "Done."

# --- Help ---
help:
	@echo "ADK-FLUENT Development Commands:"
	@echo ""
	@echo "  make all        Full pipeline: scan → generate"
	@echo "  make scan       Introspect ADK → manifest.json"
	@echo "  make generate   seed.toml + manifest.json → code"
	@echo "  make stubs      Regenerate .pyi stubs only"
	@echo "  make test       Run pytest suite"
	@echo "  make typecheck  Run pyright type-check"
	@echo "  make diff       Show changes since last scan"
	@echo "  make clean      Remove generated files"
	@echo ""
	@echo "Workflow: edit seed.toml → make all → make test → commit"
