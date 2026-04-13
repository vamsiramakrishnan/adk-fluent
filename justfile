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
#   just fmt        → Auto-format hand-written files (ruff)
#   just fmt-changed → Auto-format only changed hand-written files (fast)
#   just check-gen  → Verify generated files are up-to-date (idempotency)
#   just docs       → Generate all documentation (includes llms.txt + editor rules)
#   just llms       → Generate llms.txt + editor rules only
#   just test       → Run all tests
#   just typecheck  → Run pyright on generated stubs
#   just diff       → Show what changed since last scan
#   just clean      → Remove generated files
#
#   --- CI PARITY ---
#   just preflight  → Run pre-commit hooks (mirrors CI lint exactly)
#   just ci         → Full local CI: preflight + check-gen + test
#
#   --- RELEASE ENGINEERING ---
#   just version    → Show current version
#   just bump patch → Bump version in _version.py
#   just release    → Full preflight: bump → test → build → next steps
#   just release-tag → Create + push tag → triggers CI publish + docs
#
#   --- 100x DX COMMANDS ---
#   just watch      → Auto-run generate+test on changes
#   just repl       → Pre-loaded IPython playground
#   just worktree N → Create isolated worktree + install deps
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
    @echo "Installing Python dependencies (python/)..."
    @cd {{PYTHON_DIR}} && uv sync --all-extras
    @echo "Installing pre-commit hooks..."
    @{{PYTOOL}} pre-commit install
    @echo "Installing TypeScript dependencies (ts/)..."
    @cd {{TS_DIR}} && npm install
    @echo ""
    @echo "Setup complete. Pre-commit hooks will auto-format on every commit."
    @echo "Run 'just all' to generate code, or 'just fmt' to format existing files."

# --- Monorepo layout ---
PYTHON_DIR    := "python"
TS_DIR        := "ts"
SHARED_DIR    := "shared"

SEED          := SHARED_DIR / "seeds/seed.toml"
MANIFEST      := SHARED_DIR / "manifest.json"
PREV_MANIFEST := SHARED_DIR / "manifest.previous.json"
OUTPUT_DIR    := PYTHON_DIR / "src/adk_fluent"
TEST_DIR      := PYTHON_DIR / "tests/generated"
# All Python scripts in shared/ are invoked through the python uv project so
# they pick up google-adk and the rest of the runtime dependencies.
PY            := "uv run --project " + PYTHON_DIR + " python"
PYTOOL        := "uv run --project " + PYTHON_DIR
SCANNER       := SHARED_DIR / "scripts/scanner.py"
SEED_GEN      := SHARED_DIR / "scripts/seed_generator.py"
GENERATOR     := SHARED_DIR / "scripts/generator.py"
A2UI_SPEC_DIR := "specification/v0_10/json"
A2UI_MANIFEST := SHARED_DIR / "a2ui_manifest.json"
A2UI_SEED     := SHARED_DIR / "seeds/a2ui_seed.toml"
A2UI_MANUAL   := SHARED_DIR / "seeds/a2ui_seed.manual.toml"
IR_GEN        := SHARED_DIR / "scripts/ir_generator.py"
DOC_GEN       := SHARED_DIR / "scripts/doc_generator.py"
LLMS_GEN      := SHARED_DIR / "scripts/llms_generator.py"
COOKBOOK_GEN   := SHARED_DIR / "scripts/cookbook_generator.py"
SKILL_GEN     := SHARED_DIR / "scripts/skill_generator.py"
DOC_DIR       := "docs/generated"
SPHINX_OUT    := "docs/_build/html"
COOKBOOK_DIR   := PYTHON_DIR / "examples/cookbook"

# Generated files — owned by `just generate`, not by formatters or pre-commit.
# This is the single source of truth; .pre-commit-config.yaml and .gitattributes mirror it.
GENERATED_PY  := PYTHON_DIR / "src/adk_fluent/agent.py" + " " + PYTHON_DIR / "src/adk_fluent/config.py" + " " + PYTHON_DIR / "src/adk_fluent/executor.py" + " " + PYTHON_DIR / "src/adk_fluent/planner.py" + " " + PYTHON_DIR / "src/adk_fluent/plugin.py" + " " + PYTHON_DIR / "src/adk_fluent/runtime.py" + " " + PYTHON_DIR / "src/adk_fluent/service.py" + " " + PYTHON_DIR / "src/adk_fluent/tool.py" + " " + PYTHON_DIR / "src/adk_fluent/workflow.py" + " " + PYTHON_DIR / "src/adk_fluent/_ir_generated.py"

# --- Full pipeline ---
all: scan seed generate a2ui docs skills docs-build
    @echo "\nPipeline complete. Generated code in {{OUTPUT_DIR}}/ and docs in {{DOC_DIR}}/"

# --- A2UI pipeline ---
a2ui: a2ui-scan a2ui-seed a2ui-generate
    @echo "\nA2UI pipeline complete."

a2ui-scan:
    @echo "Scanning A2UI spec..."
    @{{PY}} -m shared.scripts.a2ui scan {{A2UI_SPEC_DIR}} -o {{A2UI_MANIFEST}}

a2ui-seed: _require-a2ui-manifest
    @echo "Generating A2UI seed..."
    @{{PY}} -m shared.scripts.a2ui seed {{A2UI_MANIFEST}} -o {{A2UI_SEED}} --json --merge {{A2UI_MANUAL}}

a2ui-generate: _require-a2ui-seed
    @echo "Generating A2UI UI factories..."
    @{{PY}} -m shared.scripts.a2ui generate {{A2UI_SEED}} --output-dir {{OUTPUT_DIR}} --test-dir {{TEST_DIR}}
    @{{PYTOOL}} ruff check --fix {{OUTPUT_DIR}}/_ui_generated.py {{TEST_DIR}}/test_ui_generated.py || true
    @{{PYTOOL}} ruff format {{OUTPUT_DIR}}/_ui_generated.py {{TEST_DIR}}/test_ui_generated.py

# --- Scan ADK ---
scan:
    @echo "Scanning installed google-adk..."
    @{{PY}} {{SCANNER}} -o {{MANIFEST}}
    @{{PY}} {{SCANNER}} --summary

# --- Generate seed.toml from manifest ---
seed: _require-manifest
    @echo "Generating seed.toml from manifest..."
    @{{PY}} {{SEED_GEN}} {{MANIFEST}} -o {{SEED}} --merge {{SHARED_DIR}}/seeds/seed.manual.toml

# --- Generate code ---
# The generator owns its output files end-to-end: emit → ruff-format → write.
# ruff is integrated into the emitter (code_ir), so output is already canonical.
# The safety-net ruff check below should be a no-op — if it changes anything,
# the emitter's _ruff_format() is out of sync and should be investigated.
generate: _require-manifest _require-seed
    @echo "Generating code from seed + manifest..."
    @{{PY}} {{GENERATOR}} {{SEED}} {{MANIFEST}} \
        --output-dir {{OUTPUT_DIR}} \
        --test-dir {{TEST_DIR}}
    @{{PY}} {{IR_GEN}} {{MANIFEST}} --output {{OUTPUT_DIR}}/_ir_generated.py
    @# Safety net: verify generated output is already ruff-clean
    @{{PYTOOL}} ruff check --fix {{GENERATED_PY}} {{TEST_DIR}} || true
    @{{PYTOOL}} ruff format {{GENERATED_PY}} {{TEST_DIR}}
    @{{PYTOOL}} ruff check {{GENERATED_PY}} {{TEST_DIR}}

# --- Stubs only (fast regeneration) ---
stubs: _require-manifest _require-seed
    @echo "Regenerating .pyi stubs only..."
    @{{PY}} {{GENERATOR}} {{SEED}} {{MANIFEST}} \
        --output-dir {{OUTPUT_DIR}} \
        --stubs-only

# --- Lint (Python hand-written files; ts target lints TypeScript) ---
# Generated builders are self-formatting via the generator; pyproject.toml's
# per-file-ignores tell ruff not to nag on them. We just run ruff over python/.
lint:
    @echo "Running ruff checks (python/)..."
    @cd {{PYTHON_DIR}} && uv run ruff check .
    @cd {{PYTHON_DIR}} && uv run ruff format --check .

# --- Format (Python hand-written files only) ---
format:
    @echo "Formatting Python files..."
    @cd {{PYTHON_DIR}} && uv run ruff check --fix . || true
    @cd {{PYTHON_DIR}} && uv run ruff format .

# --- Format (alias) ---
alias fmt := format

# --- Format changed Python files only (fast, excludes generated files) ---
fmt-changed:
    #!/usr/bin/env bash
    set -euo pipefail
    generated_re='(agent|config|executor|planner|plugin|runtime|service|tool|workflow)\.(py|pyi)$|_ir_generated\.py$|^python/tests/generated/'
    py_files=$(git diff --name-only --diff-filter=d HEAD -- 'python/**/*.py' | grep -Ev "$generated_re" || true)
    if [ -n "$py_files" ]; then
        echo "Formatting $(echo "$py_files" | wc -w) Python files..."
        echo "$py_files" | xargs {{PYTOOL}} ruff check --fix || true
        echo "$py_files" | xargs {{PYTOOL}} ruff format
    else
        echo "No changed hand-written .py files to format."
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
    @cd {{PYTHON_DIR}} && uv run pytest tests/ -v --tb=short

# --- Pipeline tests only (fast inner loop) ---
test-pipeline:
    @echo "Running pipeline tests (generator/seed_generator/code_ir)..."
    @cd {{PYTHON_DIR}} && uv run pytest tests/test_code_ir.py tests/test_seed_generator.py tests/test_generator_golden.py tests/test_property_based.py -v --tb=short

# --- Update golden files ---
update-golden:
    @echo "Updating golden files..."
    @cd {{PYTHON_DIR}} && uv run pytest tests/test_generator_golden.py --update-golden -v

# --- Preflight: run pre-commit hooks (mirrors CI lint exactly) ---
preflight:
    @echo "Running pre-commit hooks (same as CI lint)..."
    @{{PYTOOL}} pre-commit run --all-files --show-diff-on-failure

# --- Local CI: full pipeline matching GitHub Actions ---
ci: preflight check-gen test
    @echo "\nLocal CI passed. Safe to push."

# --- Type checking ---
typecheck:
    @echo "Type-checking generated stubs..."
    @{{PYTOOL}} pyright {{OUTPUT_DIR}}/*.pyi --pythonversion 3.12

# --- Type checking hand-written code ---
typecheck-core:
    @echo "Type-checking hand-written code..."
    @cd {{PYTHON_DIR}} && uv run pyright

# --- Watch mode ---
watch:
    @echo "Watching for changes..."
    @{{PYTOOL}} watchfiles "just generate test typecheck" {{SHARED_DIR}}/scripts/ {{SHARED_DIR}}/seeds/ {{PYTHON_DIR}}/src/ {{PYTHON_DIR}}/tests/

# --- Documentation ---
docs: _require-manifest _require-seed
    @echo "Generating documentation..."
    @{{PY}} {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --cookbook-dir {{COOKBOOK_DIR}}
    @echo "Updating README.md from template..."
    @{{PY}} {{SHARED_DIR}}/scripts/readme_generator.py
    @echo "Generating concepts documentation..."
    @{{PY}} {{SHARED_DIR}}/scripts/concepts_generator.py
    @echo "Generating llms.txt and editor rules..."
    @{{PY}} {{LLMS_GEN}} {{MANIFEST}} {{SEED}}

# --- LLMs context files (editor rules, llms.txt) ---
llms: _require-manifest _require-seed
    @echo "Generating llms.txt and editor rules..."
    @{{PY}} {{LLMS_GEN}} {{MANIFEST}} {{SEED}}

# --- Agent Skills reference generation ---
skills: _require-manifest _require-seed
    @echo "Generating agent skill references..."
    @{{PY}} {{SKILL_GEN}} {{MANIFEST}} {{SEED}}

# --- Check skills for staleness (fails if out of date) ---
check-skills: _require-manifest _require-seed
    @echo "Checking skill freshness..."
    @{{PY}} {{SKILL_GEN}} {{MANIFEST}} {{SEED}} --check

docs-api: _require-manifest _require-seed
    @echo "Generating API reference..."
    @{{PY}} {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --api-only

docs-cookbook: _require-manifest _require-seed
    @echo "Generating cookbook..."
    @{{PY}} {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --cookbook-dir {{COOKBOOK_DIR}} \
        --cookbook-only

docs-migration: _require-manifest _require-seed
    @echo "Generating migration guide..."
    @{{PY}} {{DOC_GEN}} {{SEED}} {{MANIFEST}} \
        --output-dir {{DOC_DIR}} \
        --migration-only

# --- TypeScript: typedoc API reference ---
# Produces a fully-linked symbol reference for the TypeScript package.
# The output lives at ts/docs/api/ — docs-build copies it under the
# Sphinx HTML output so GH Pages serves it at /latest/ts-api/.
ts-docs:
    @echo "Generating TypeScript API reference (typedoc)..."
    @cd {{TS_DIR}} && (test -d node_modules || npm install --no-audit --no-fund) && npm run docs

# --- Sphinx build ---
# Depends on docs (markdown generation) + ts-docs (typedoc reference) so
# the TS API reference lands under docs/_build/html/ts-api/ and ships
# with the rest of the site to GitHub Pages.
docs-build: docs ts-docs
    @echo "Building Sphinx documentation..."
    @{{PYTOOL}} sphinx-build -W --keep-going -b html docs/ {{SPHINX_OUT}}
    @echo "Copying TypeScript API reference to {{SPHINX_OUT}}/ts-api/..."
    @rm -rf {{SPHINX_OUT}}/ts-api
    @mkdir -p {{SPHINX_OUT}}/ts-api
    @if [ -d {{TS_DIR}}/docs/api ]; then cp -a {{TS_DIR}}/docs/api/. {{SPHINX_OUT}}/ts-api/; else echo "  (ts/docs/api/ missing — run 'just ts-docs' first)"; fi

# --- Sphinx live preview ---
docs-serve: docs
    @echo "Serving docs with live reload at http://localhost:8000..."
    @{{PYTOOL}} sphinx-autobuild docs/ {{SPHINX_OUT}} --watch {{DOC_DIR}} --watch {{PYTHON_DIR}}/src/ --port 8000

# --- REPL ---
repl:
    @echo "Starting ADK-Fluent playground..."
    @cd {{PYTHON_DIR}} && uv run ipython -i -c "from adk_fluent import *; print('\nADK-Fluent playground loaded! (Agent, Pipeline, S, C available)')"

# --- Worktree: isolated workspace for feature work ---
worktree name:
    #!/usr/bin/env bash
    set -euo pipefail
    dir=".worktrees/{{name}}"
    branch="feature/{{name}}"
    if [ -d "$dir" ]; then
        echo "Worktree already exists at $dir"
        echo "cd $dir"
        exit 0
    fi
    echo "Creating worktree at $dir (branch: $branch)..."
    git worktree add "$dir" -b "$branch"
    echo "Installing dependencies..."
    cd "$dir/{{PYTHON_DIR}}" && uv sync --all-extras
    echo ""
    echo "Worktree ready: cd $dir"
    echo "When done: git worktree remove $dir"

# --- Add Cookbook ---
add-cookbook name:
    @{{PY}} {{SHARED_DIR}}/scripts/add_cookbook.py "{{name}}"

# --- Cookbook generation ---
cookbook-gen: _require-manifest _require-seed
    @echo "Generating cookbook example stubs..."
    @{{PY}} {{COOKBOOK_GEN}} {{SEED}} {{MANIFEST}} \
        --cookbook-dir {{COOKBOOK_DIR}}

cookbook-gen-dry: _require-manifest _require-seed
    @echo "Previewing cookbook example stubs..."
    @{{PY}} {{COOKBOOK_GEN}} {{SEED}} {{MANIFEST}} \
        --cookbook-dir {{COOKBOOK_DIR}} --dry-run

# --- Convert cookbook to adk-web agent folders ---
agents:
    @echo "Converting cookbook examples to adk-web agent folders..."
    @{{PY}} {{SHARED_DIR}}/scripts/cookbook_to_agents.py --force

# --- Visual: A2UI preview (static, no LLM, no server) ---
a2ui-preview:
    @echo "Exporting A2UI surfaces from cookbooks..."
    @{{PY}} {{SHARED_DIR}}/scripts/export_a2ui_surfaces.py
    @echo "Opening A2UI gallery in browser..."
    @python3 -c "import webbrowser; webbrowser.open('shared/visual/index.html')" 2>/dev/null || echo "Open shared/visual/index.html in your browser"

# --- Visual: Python cookbook runner (requires API key) ---
# Usage: just visual-py [port]  (default: 8098)
visual-py port="8098": a2ui-preview
    @echo "Starting Python visual runner at http://localhost:{{port}}..."
    @cd {{PYTHON_DIR}} && uv run uvicorn visual.server:app --host 0.0.0.0 --port {{port}} --reload

# --- Visual: TypeScript cookbook runner (requires API key) ---
# Usage: just visual-ts [port]  (default: 8099)
visual-ts port="8099":
    @echo "Starting TypeScript visual runner at http://localhost:{{port}}..."
    @cd {{TS_DIR}} && PORT={{port}} npx tsx visual/server.ts

# --- Visual: export surfaces only ---
visual-export:
    @echo "Exporting A2UI surfaces..."
    @{{PY}} {{SHARED_DIR}}/scripts/export_a2ui_surfaces.py

# --- Visual test suite (requires API key) ---
test-visual:
    @echo "Running visual test suite..."
    @cd {{PYTHON_DIR}} && uv run pytest tests/visual/ -v --tb=short -m visual

# --- Visual: legacy alias ---
visual: visual-py

# --- Diff against previous ---
diff:
    #!/usr/bin/env bash
    if [ -f {{PREV_MANIFEST}} ]; then
        echo "Changes since last scan:"
        {{PY}} {{SCANNER}} --diff {{PREV_MANIFEST}}
    else
        echo "No previous manifest found. Run 'just scan' first."
    fi

# --- Diff as publishable Markdown page ---
diff-md:
    #!/usr/bin/env bash
    if [ -f {{PREV_MANIFEST}} ]; then
        echo "Generating API diff Markdown..."
        {{PY}} {{SCANNER}} --diff {{PREV_MANIFEST}} \
            --diff-markdown {{DOC_DIR}}/api-diff.md
        echo "Written to {{DOC_DIR}}/api-diff.md"
    else
        echo "No previous manifest found. Run 'just archive' before scanning, then 'just diff-md'."
    fi

# --- Summary ---
summary:
    @{{PY}} {{SCANNER}} --summary

# --- Archive current manifest ---
archive:
    @cp {{MANIFEST}} {{PREV_MANIFEST}}
    @echo "Archived {{MANIFEST}} -> {{PREV_MANIFEST}}"

# --- Package build (Python) ---
build: all
    @echo "Building Python package..."
    @cd {{PYTHON_DIR}} && uv build

# --- Publish to TestPyPI ---
publish-test: build
    @echo "Publishing to TestPyPI..."
    @cd {{PYTHON_DIR}} && uv publish --index testpypi

# --- Publish to PyPI ---
publish: build
    @echo "Publishing to PyPI..."
    @cd {{PYTHON_DIR}} && uv publish

# ============================================================================
# RELEASE ENGINEERING
# ============================================================================
#
#   just bump patch|minor|major   → Bump version in _version.py
#   just release                  → Full release preflight (bump → test → build → tag)
#   just release-tag              → Create and push git tag from _version.py
#   just version                  → Show current version
#

VERSION_FILE  := PYTHON_DIR / "src/adk_fluent/_version.py"

# Show the current version from _version.py
version:
    @python3 -c "exec(open('{{VERSION_FILE}}').read()); print(__version__)"

# Bump the version in _version.py. Usage: just bump patch|minor|major
bump level:
    #!/usr/bin/env python3
    import re, sys
    from pathlib import Path

    level = "{{level}}"
    if level not in ("patch", "minor", "major"):
        print(f"ERROR: invalid level '{level}'. Use: just bump patch|minor|major")
        sys.exit(1)

    vf = Path("{{VERSION_FILE}}")
    text = vf.read_text()
    m = re.search(r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', text)
    if not m:
        print("ERROR: could not parse version from _version.py")
        sys.exit(1)

    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if level == "major":
        major, minor, patch = major + 1, 0, 0
    elif level == "minor":
        major, minor, patch = major, minor + 1, 0
    else:
        patch += 1

    new_version = f"{major}.{minor}.{patch}"
    vf.write_text(f'"""Single source of truth for adk-fluent version."""\n\n__version__ = "{new_version}"\n')
    print(f"Bumped: {m.group(1)}.{m.group(2)}.{m.group(3)} → {new_version}")
    print(f"  _version.py updated (docs/conf.py auto-syncs at build time)")

# Create and push a git tag from _version.py
release-tag:
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION=$(python3 -c "exec(open('{{VERSION_FILE}}').read()); print(__version__)")
    echo "Tagging v${VERSION}..."
    if git rev-parse "v${VERSION}" >/dev/null 2>&1; then
        echo "ERROR: Tag v${VERSION} already exists"
        exit 1
    fi
    git tag "v${VERSION}"
    git push origin "v${VERSION}"
    echo "✓ Tag v${VERSION} pushed — CI will publish to PyPI and rebuild docs"

# Full release preflight: bump, run tests, build, and show next steps
release level="patch": (bump level)
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION=$(python3 -c "exec(open('{{VERSION_FILE}}').read()); print(__version__)")
    echo ""
    echo "Running release preflight for v${VERSION}..."
    echo ""

    echo "── Running tests ──"
    cd {{PYTHON_DIR}} && uv run pytest tests/ -x -q --tb=short

    echo ""
    echo "── Running typecheck ──"
    cd {{PYTHON_DIR}} && uv run pyright src/adk_fluent/*.pyi --pythonversion 3.12 2>/dev/null || true

    echo ""
    echo "── Building package ──"
    cd {{PYTHON_DIR}} && uv build

    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  Release v${VERSION} ready!"
    echo ""
    echo "  Next steps:"
    echo "    1. Update CHANGELOG.md (move [Unreleased] → [${VERSION}])"
    echo "    2. git add -A && git commit -m 'release: v${VERSION}'"
    echo "    3. git push origin master"
    echo "    4. just release-tag      ← triggers PyPI publish + docs"
    echo ""
    echo "  What happens automatically:"
    echo "    ✓ CI validates tag matches _version.py"
    echo "    ✓ CI publishes to PyPI via Trusted Publishing"
    echo "    ✓ docs/conf.py auto-syncs version at build time"
    echo "    ✓ Announcement banner updates automatically"
    echo "    ✓ getting-started.md version note updates automatically"
    echo "    ✓ Versioned docs deploy to /v${VERSION}/"
    echo "    ✓ Version switcher dropdown updates"
    echo "    ✓ Release drafter creates GitHub Release draft"
    echo "════════════════════════════════════════════════════════════"

# --- Clean ---
clean:
    @echo "Cleaning generated files..."
    @rm -f {{OUTPUT_DIR}}/agent.py {{OUTPUT_DIR}}/config.py {{OUTPUT_DIR}}/executor.py {{OUTPUT_DIR}}/planner.py {{OUTPUT_DIR}}/plugin.py {{OUTPUT_DIR}}/runtime.py {{OUTPUT_DIR}}/service.py {{OUTPUT_DIR}}/tool.py {{OUTPUT_DIR}}/workflow.py {{OUTPUT_DIR}}/_ir_generated.py
    @rm -f {{OUTPUT_DIR}}/*.pyi
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
    @echo "  just fmt            Auto-format hand-written files (ruff)"
    @echo "  just fmt-changed    Auto-format only changed hand-written files (fast)"
    @echo "  just check-gen      Verify generated files are up-to-date"
    @echo "  just preflight      Run pre-commit hooks (mirrors CI lint)"
    @echo "  just ci             Full local CI: preflight + check-gen + test"
    @echo "  just test           Run pytest suite"
    @echo "  just test-pipeline  Run pipeline tests only (fast <5s)"
    @echo "  just update-golden  Regenerate golden files"
    @echo "  just typecheck      Run pyright type-check"
    @echo "  just watch          Auto-run generate+test on changes"
    @echo "  just repl           Pre-loaded IPython playground"
    @echo "  just worktree NAME  Create isolated worktree + install deps"
    @echo "  just add-cookbook    Scaffold new example"
    @echo "  just docs           Generate all documentation"
    @echo "  just docs-api       Generate API reference only"
    @echo "  just docs-cookbook   Generate cookbook only"
    @echo "  just docs-migration Generate migration guide only"
    @echo "  just docs-build     Build Sphinx HTML documentation"
    @echo "  just docs-serve     Build and serve docs with live reload"
    @echo "  just llms           Generate llms.txt + editor rules (CLAUDE.md, .cursorrules, etc.)"
    @echo "  just skills         Generate agent skill references (.claude/skills/ + .gemini/skills/ + skills/)"
    @echo "  just check-skills   Check if skills are up to date (fails if stale)"
    @echo "  just cookbook-gen    Generate cookbook example stubs"
    @echo "  just cookbook-gen-dry Preview cookbook stubs (dry-run)"
    @echo "  just agents         Convert cookbook -> adk web folders"
    @echo "  just a2ui-preview   Static A2UI gallery (no server, no LLM)"
    @echo "  just visual-py [P]  Python visual runner (default port 8098)"
    @echo "  just visual-ts [P]  TypeScript visual runner (default port 8099)"
    @echo "  just visual         Alias for visual-py"
    @echo "  just visual-export  Export A2UI surfaces to JSON"
    @echo "  just test-visual    Run visual regression tests"
    @echo "  just diff           Show changes since last scan (JSON)"
    @echo "  just diff-md        Generate API diff as docs/generated/api-diff.md"
    @echo "  just build          Build pip package"
    @echo "  just publish        Publish to PyPI"
    @echo "  just clean          Remove generated files"
    @echo ""
    @echo "Release Engineering:"
    @echo "  just version        Show current version"
    @echo "  just bump LEVEL     Bump version (patch|minor|major)"
    @echo "  just release LEVEL  Full preflight: bump + test + build"
    @echo "  just release-tag    Create and push git tag → triggers PyPI + docs"
    @echo ""
    @echo "Workflow: just setup -> just all -> just ci -> commit"
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

[private]
_require-a2ui-manifest:
    @test -f {{A2UI_MANIFEST}} || (echo "ERROR: {{A2UI_MANIFEST}} not found. Run 'just a2ui-scan' first." && exit 1)

[private]
_require-a2ui-seed:
    @test -f {{A2UI_SEED}} || (echo "ERROR: {{A2UI_SEED}} not found. Run 'just a2ui-seed' first." && exit 1)

# ============================================================================
# TYPESCRIPT (ts/ package)
# ============================================================================

# --- TypeScript: install dependencies ---
ts-setup:
    @echo "Installing TypeScript dependencies..."
    @cd {{TS_DIR}} && npm install

# --- TypeScript: regenerate builders from seed + manifest ---
ts-generate: _require-manifest _require-seed
    @echo "Generating TypeScript builders from seed + manifest..."
    @uv run python -m shared.scripts.generator {{SEED}} {{MANIFEST}} \
        --target typescript \
        --ts-output-dir {{TS_DIR}}/src/builders

# --- TypeScript: build ---
ts-build:
    @echo "Building TypeScript package..."
    @cd {{TS_DIR}} && npm run build

# --- TypeScript: test ---
ts-test:
    @echo "Running TypeScript tests..."
    @cd {{TS_DIR}} && npm test

# --- TypeScript: typecheck ---
ts-typecheck:
    @echo "Running TypeScript type checks..."
    @cd {{TS_DIR}} && npm run typecheck

# --- TypeScript: lint ---
ts-lint:
    @echo "Running TypeScript linter..."
    @cd {{TS_DIR}} && npm run lint

# --- Monorepo: run all tests ---
test-all: test ts-test
    @echo "\nAll Python and TypeScript tests passed."

# --- Monorepo: build everything ---
build-all: generate ts-generate ts-build
    @echo "\nAll packages built successfully."

# --- Monorepo: regenerate everything (Python + TypeScript) ---
generate-all: generate ts-generate
    @echo "\nRegenerated Python and TypeScript builders."
