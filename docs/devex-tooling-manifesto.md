---
orphan: true
---

# DevEx Tooling Manifesto

> The definitive guide to every automation script, agent skill, and development command in adk-fluent.

adk-fluent is not just a library — it's a **tooling-first** project. Every repetitive task is automated. Every AI coding agent gets domain-specific knowledge. Every generated file traces back to a single source of truth.

This document is the map.

---

## The code generation pipeline

Everything in adk-fluent flows from one pipeline. Understanding this pipeline is the key to understanding the entire project.

```
google-adk (installed package)
  │
  ▼
scanner.py ──► manifest.json (451 classes, 795 fields, 25 callbacks)
                  │
                  ▼
seed_generator.py + seed.manual.toml ──► seed.toml (builder specifications)
                                            │
                  ┌─────────────────────────┤
                  │                         │
                  ▼                         ▼
generator.py ──► src/adk_fluent/*.py    ir_generator.py ──► _ir_generated.py
                  │
                  ├──► *.pyi stubs
                  └──► tests/generated/

                  │ (same manifest + seed)
                  ▼
doc_generator.py ──► docs/generated/api/ + docs/generated/cookbook/
llms_generator.py ──► CLAUDE.md + .cursor/rules/ + .clinerules/ + .windsurfrules
skill_generator.py ──► .claude/skills/_shared/ + .gemini/skills/_shared/ + skills/
readme_generator.py ──► README.md
concepts_generator.py ──► docs/concepts/
```

### One command to rule them all

```bash
just all    # scan → seed → generate → docs → skills → docs-build
```

**Expected output:**
```
Scanning installed google-adk...
  451 classes, 795 fields, 25 callbacks
Generating seed.toml from manifest...
Generating code from seed + manifest...
Generating documentation...
Generating agent skill references...
Building Sphinx documentation...

Pipeline complete. Generated code in src/adk_fluent/ and docs in docs/generated/
```

---

## Scripts reference

Every script in `scripts/` serves exactly one purpose. Here's what each does, how to run it, and what to expect.

### scanner.py — ADK introspection

**Why:** Discovers every class, field, validator, and callback in the installed `google-adk` package. Produces the machine-truth manifest that drives all code generation.

**How:**
```bash
just scan
# or directly:
uv run python scripts/scanner.py -o manifest.json
```

**Expected output:**
```
Scanning installed google-adk...
  451 classes, 795 fields, 25 callbacks
```

**Escape hatch:** If scanning fails with `ImportError`, ensure `google-adk` is installed: `uv pip install google-adk`.

---

### seed_generator.py — Builder specification

**Why:** Converts the raw manifest into actionable builder specifications, merging in hand-written overrides from `seed.manual.toml` (custom aliases, docstrings, field policies).

**How:**
```bash
just seed
# or directly:
uv run python scripts/seed_generator.py manifest.json -o seeds/seed.toml --merge seeds/seed.manual.toml
```

**Expected output:** Writes `seeds/seed.toml` (2500+ lines) silently.

**Escape hatch:** If seed generation fails, check that `manifest.json` exists (`just scan`) and that `seeds/seed.manual.toml` has valid TOML syntax.

---

### generator.py — Code generation

**Why:** The core engine. Transforms seed + manifest into Python builder classes, type stubs, and generated tests. This is what creates `Agent()`, `Pipeline()`, `FanOut()`, `Loop()`, and 131 other builders.

**How:**
```bash
just generate
# or directly:
uv run python scripts/generator.py seeds/seed.toml manifest.json \
    --output-dir src/adk_fluent/ --test-dir tests/generated/
```

**Expected output:**
```
Generating code from seed + manifest...
  9 modules, 135 builders
  Type stubs: 9 .pyi files
  Tests: tests/generated/
```

**Escape hatch:** If generation produces lint errors, run `just generate` again (it auto-formats with ruff). If the error persists, check `seeds/seed.manual.toml` for invalid field overrides.

---

### ir_generator.py — Intermediate representation

**Why:** Generates frozen dataclass nodes (`AgentNode`, `SequenceNode`, `ParallelNode`, `LoopNode`) used by `.to_ir()` and `.show("diagnose")` introspection methods.

**How:**
```bash
# Included in `just generate`, or:
uv run python scripts/ir_generator.py manifest.json --output src/adk_fluent/_ir_generated.py
```

---

### doc_generator.py — Documentation

**Why:** Generates API reference pages (one per module), cookbook documentation (one per example), and migration guides from manifest + seed.

**How:**
```bash
just docs
# API reference only:
just docs-api
# Cookbook only:
just docs-cookbook
# Migration guide only:
just docs-migration
```

**Expected output:**
```
Generating documentation...
  API reference: 16 pages
  Cookbook: 68 examples
  Migration guide: 1 page
```

---

### llms_generator.py — LLM context files

**Why:** Generates the rules files that teach AI coding agents about adk-fluent's API. One source, many targets.

**How:**
```bash
just llms
# or directly:
uv run python scripts/llms_generator.py manifest.json seeds/seed.toml
```

**Generates:**
| File | Target |
|------|--------|
| `CLAUDE.md` | Claude Code |
| `.cursor/rules/adk-fluent.mdc` | Cursor |
| `.clinerules/adk-fluent.md` | Cline |
| `.github/instructions/adk-fluent.instructions.md` | VS Code Copilot |
| `.windsurfrules` | Windsurf |
| `.zed/settings.json` | Zed |
| `docs/llms.txt` | Any agent via `#fetch` |

---

### skill_generator.py — Agent skill references

**Why:** Generates the shared reference files and scripts that agent skills use on-demand. Keeps skill knowledge synchronized with the actual API.

**How:**
```bash
just skills
# or directly:
uv run python scripts/skill_generator.py manifest.json seeds/seed.toml
```

**Generates:** 7 reference files + 4 scripts in `.claude/skills/_shared/`, `.gemini/skills/_shared/`, and `skills/`.

---

### Other scripts

| Script | Why | How |
|--------|-----|-----|
| `readme_generator.py` | Renders README.md from template with dynamic examples | `just docs` (included) |
| `concepts_generator.py` | Generates concepts documentation | `just docs` (included) |
| `cookbook_generator.py` | Generates cookbook example stubs from seed | `just cookbook-gen` |
| `cookbook_to_agents.py` | Converts cookbook examples to `adk web` agent folders | `just agents` |
| `add_cookbook.py` | Scaffolds a new cookbook example | `just add-cookbook "Name"` |
| `benchmark.py` | Benchmarks codegen pipeline performance | `uv run python scripts/benchmark.py` |
| `update_html_refs.py` | Updates HTML documentation cross-references | `uv run python scripts/update_html_refs.py` |

---

## Development commands (justfile)

The `justfile` is the single entry point for all development workflows. Here's every command, organized by when you'd use it.

### First time

| Command | What it does | When to use |
|---------|-------------|-------------|
| `just setup` | Install all deps + pre-commit hooks | Once, after cloning |
| `just all` | Full pipeline: scan → seed → generate → docs → skills | Once, to bootstrap |

### Inner development loop

| Command | What it does | When to use |
|---------|-------------|-------------|
| `just generate` | Regenerate code from seed + manifest | After changing `seed.manual.toml` or generator scripts |
| `just stubs` | Regenerate `.pyi` stubs only (fast) | After changing type annotations |
| `just test` | Run all tests | After any code change |
| `just test-pipeline` | Run pipeline tests only (~5s) | Quick validation of generator changes |
| `just fmt` | Auto-format hand-written files | Before committing |
| `just fmt-changed` | Format only changed files (fast) | Incremental formatting |
| `just lint` | Lint hand-written files | Check for issues without fixing |
| `just typecheck` | Type-check generated stubs | After changing builder signatures |
| `just watch` | Auto-run generate+test on file changes | Leave running during development |
| `just repl` | IPython with adk-fluent pre-loaded | Interactive exploration |

### Before pushing

| Command | What it does | When to use |
|---------|-------------|-------------|
| `just preflight` | Run pre-commit hooks (mirrors CI) | Before pushing |
| `just ci` | Full local CI: preflight + check-gen + test | Final validation |
| `just check-gen` | Verify generated files are up-to-date | Catch stale generated code |

### Documentation

| Command | What it does | When to use |
|---------|-------------|-------------|
| `just docs` | Generate all docs + llms.txt + editor rules | After API changes |
| `just docs-api` | API reference only | Quick doc regeneration |
| `just docs-cookbook` | Cookbook docs only | After adding examples |
| `just docs-build` | Build Sphinx HTML | Full HTML output |
| `just docs-serve` | Live preview at localhost:8000 | Reviewing docs locally |
| `just llms` | LLM context files only | After API changes |
| `just skills` | Agent skill references only | After API changes |

### Cookbook

| Command | What it does | When to use |
|---------|-------------|-------------|
| `just add-cookbook "Name"` | Scaffold new example | Adding a new example |
| `just cookbook-gen` | Generate cookbook stubs from seed | Bulk example generation |
| `just cookbook-gen-dry` | Preview without writing | Check what would be generated |
| `just agents` | Convert cookbook → adk web folders | Testing examples in adk web |

### ADK upgrades

| Command | What it does | When to use |
|---------|-------------|-------------|
| `just archive` | Save current manifest | Before upgrading ADK |
| `just scan` | Introspect installed ADK | After upgrading ADK |
| `just diff` | Show changes since last scan | Review what changed |
| `just diff-md` | Generate API diff page | Publishable changelog |
| `just summary` | Print manifest summary | Quick overview |

### Release

| Command | What it does | When to use |
|---------|-------------|-------------|
| `just build` | Build pip package | Preparing release |
| `just publish-test` | Publish to TestPyPI | Testing release |
| `just publish` | Publish to PyPI | Official release |

### Maintenance

| Command | What it does | When to use |
|---------|-------------|-------------|
| `just clean` | Remove all generated files | Fresh start |
| `just update-golden` | Update test golden files | After intentional output changes |
| `just worktree NAME` | Create isolated worktree | Parallel feature work |

---

## Agent skills inventory

### The 14 internal skills

Located in `.claude/skills/` and `.gemini/skills/`. Activate automatically based on context.

#### Always active

| Skill | File | Why it exists |
|-------|------|---------------|
| `/dev-guide` | `.claude/skills/dev-guide/SKILL.md` | Loaded at session start. Provides the complete agent development lifecycle: understand spec → design topology → build → test → evaluate → deploy. |

#### Agent development

| Skill | File | Why it exists |
|-------|------|---------------|
| `/cheatsheet` | `.claude/skills/cheatsheet/SKILL.md` | Instant API reference. Every builder method, operator, namespace function, and common gotcha in one place. |
| `/scaffold-project` | `.claude/skills/scaffold-project/SKILL.md` | Zero-to-running project in minutes. Generates `agent.py`, `tools.py`, tests, and eval cases. |
| `/architect-agents` | `.claude/skills/architect-agents/SKILL.md` | Topology selection guide. Helps choose between Pipeline, FanOut, Loop, Route, Race, and 10+ other patterns. |
| `/deploy-agent` | `.claude/skills/deploy-agent/SKILL.md` | Production deployment. Covers Agent Engine, Cloud Run, GKE, secrets management, and middleware configuration. |
| `/eval-agent` | `.claude/skills/eval-agent/SKILL.md` | Evaluation methodology. E namespace reference, eval-fix loops, criteria selection, ADK CLI integration. |
| `/observe-agent` | `.claude/skills/observe-agent/SKILL.md` | Observability layers. M namespace middleware for logging, tracing, metrics, cost tracking, and circuit breakers. |

#### Library development

| Skill | File | Why it exists |
|-------|------|---------------|
| `/develop-feature` | `.claude/skills/develop-feature/SKILL.md` | Change classification and implementation guide. Knows where every type of change belongs in the codebase. |
| `/write-tests` | `.claude/skills/write-tests/SKILL.md` | Test patterns. Mock-based testing, contract checking, namespace verification, golden file testing. |
| `/add-cookbook` | `.claude/skills/add-cookbook/SKILL.md` | Example scaffolding. Creates runnable pytest files that serve as both documentation and test. |
| `/debug-builder` | `.claude/skills/debug-builder/SKILL.md` | Systematic debugging. `.show()` → `.show("diagnose")` → `.show("doctor")` → fix. |

#### Skill maintenance

| Skill | File | Why it exists |
|-------|------|---------------|
| `/review-pr` | `.claude/skills/review-pr/SKILL.md` | 12-point automated review. Runs deprecated method scan, import validation, generated file protection, and 9 more checks. |
| `/codegen-pipeline` | `.claude/skills/codegen-pipeline/SKILL.md` | Pipeline operation guide. Explains scan → seed → generate and how to run partial regeneration. |
| `/upgrade-adk` | `.claude/skills/upgrade-adk/SKILL.md` | ADK version upgrade. 12-step process with impact analysis, regeneration, verification, and rollback. |

### The 6 published skills

Located in `skills/`. Distributed via `npx skills add vamsiramakrishnan/adk-fluent -y -g`.

| Published name | Maps to internal skill |
|---------------|----------------------|
| `adk-fluent-cheatsheet` | `/cheatsheet` |
| `adk-fluent-deploy-guide` | `/deploy-agent` |
| `adk-fluent-dev-guide` | `/dev-guide` |
| `adk-fluent-eval-guide` | `/eval-agent` |
| `adk-fluent-observe-guide` | `/observe-agent` |
| `adk-fluent-scaffold` | `/scaffold-project` |

---

## Helper scripts

Four utility scripts in `.claude/skills/_shared/scripts/` designed to be run by both humans and AI agents.

### check-deprecated.py

**Why:** Catches usage of deprecated builder methods before they break in a future release.

**How:**
```bash
uv run .claude/skills/_shared/scripts/check-deprecated.py src/ tests/ examples/
```

**Expected output (clean):**
```
No deprecated methods found.
```

**Expected output (violations):**
```
src/my_agent.py:15  .output_key("result")  →  Use .writes("result") instead
src/my_agent.py:23  .delegate(other)       →  Use .agent_tool(other) instead
Found 2 deprecated method calls.
```

**Escape hatch:** If the script reports false positives, check `seeds/seed.manual.toml` under `[deprecated]` for the mapping.

---

### validate-imports.py

**Why:** Ensures all imports use the public API (`from adk_fluent import ...`) and never reach into internal modules (`from adk_fluent._base import ...`).

**How:**
```bash
uv run .claude/skills/_shared/scripts/validate-imports.py src/ tests/ examples/
```

**Expected output (clean):**
```
All imports are valid.
```

**Expected output (violations):**
```
tests/test_foo.py:3  from adk_fluent._base import BuilderBase  →  Import from adk_fluent directly
Found 1 import violation.
```

---

### list-builders.py

**Why:** Prints the complete builder inventory from `manifest.json` — useful for verifying that a new ADK class has been picked up by the scanner.

**How:**
```bash
uv run .claude/skills/_shared/scripts/list-builders.py
```

**Expected output:**
```
agent module (3 builders)
  BaseAgent, Agent, RemoteA2aAgent

config module (39 builders)
  A2aAgentExecutorConfig, AgentConfig, ...

...

Total: 135 builders across 9 modules
```

---

### list-generated-files.py

**Why:** Classifies every file in the project as generated or hand-written — essential for knowing what you can safely edit.

**How:**
```bash
uv run .claude/skills/_shared/scripts/list-generated-files.py
```

**Expected output:**
```
GENERATED    src/adk_fluent/agent.py
GENERATED    src/adk_fluent/config.py
...
HAND-WRITTEN src/adk_fluent/_base.py
HAND-WRITTEN src/adk_fluent/_context.py
...
```

---

## Configuration files

| File | Purpose | Edited by |
|------|---------|-----------|
| `manifest.json` | Machine-truth ADK introspection (451 classes) | `just scan` (auto-generated) |
| `seeds/seed.toml` | Builder specifications (2500+ lines) | `just seed` (auto-generated) |
| `seeds/seed.manual.toml` | Hand-written overrides (aliases, docstrings, field policies) | Humans |
| `pyproject.toml` | Package metadata, dependencies, tool config | Humans |
| `.pre-commit-config.yaml` | Pre-commit hooks (ruff lint + format) | Humans |
| `.gitattributes` | Marks generated files for GitHub display | Humans |

---

## CI/CD workflows

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `ci.yml` | Push/PR to master | lint → typecheck → check-gen → test (ADK compatibility matrix) |
| `docs.yml` | Push to master | Build and publish Sphinx documentation |
| `sync-adk.yml` | Weekly schedule | Detect new ADK releases, auto-generate PR with updated builders |
| `release-drafter.yml` | Push to master | Auto-generate release notes |
| `codeql.yml` | Push/PR to master | Security scanning |

---

## The golden rule

> **Never edit a generated file.** If it's wrong, fix the generator.

Every file in this project is either:
- **Hand-written** — edit freely
- **Auto-generated** — trace the issue back to `manifest.json`, `seed.manual.toml`, or the generator script, and fix it there

Run `uv run .claude/skills/_shared/scripts/list-generated-files.py` if you're unsure.
