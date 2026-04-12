# Contributing to adk-fluent

Thanks for your interest in contributing! This guide covers everything you need to get started.

## Development Setup

```bash
# Clone and install
git clone https://github.com/vamsiramakrishnan/adk-fluent.git
cd adk-fluent

# One-command setup: installs all deps + pre-commit hooks
just setup

# Run the full codegen pipeline
just all

# Run tests
just test
```

**Expected output** from `just setup`:
```
Installing dependencies...
Installing pre-commit hooks...
Setup complete. Pre-commit hooks will auto-format on every commit.
Run 'just all' to generate code, or 'just fmt' to format existing files.
```

### Prerequisites

- Python 3.11+
- Node.js 20+ (only if you're touching the TypeScript package under `ts/`)
- [just](https://github.com/casey/just) command runner
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## How the Codebase Works

adk-fluent is a **dual-language monorepo**: the Python package (`adk-fluent`) lives under `python/`, the TypeScript package (`adk-fluent-ts`) lives under `ts/`, and a single shared pipeline under `shared/` drives code generation for both from one ADK scan.

```
shared/scripts/scanner.py ─► shared/manifest.json ─► shared/scripts/seed_generator.py
                                                                │
                                                     shared/seeds/seed.toml
                                                                │
                                  ┌─────────────────────────────┴─────────────────────────────┐
                                  ▼                                                           ▼
                    shared/scripts/generator.py                                shared/scripts/generator.py
                      --target python                                            --target typescript
                                  ▼                                                           ▼
                    python/src/adk_fluent/*.py (+ .pyi stubs)                     ts/src/builders/*.ts
```

### Key directories

| Path                                    | What it is                        | Hand-written?                     |
| --------------------------------------- | --------------------------------- | --------------------------------- |
| `python/src/adk_fluent/agent.py`        | Agent builder (Python)            | Auto-generated                    |
| `python/src/adk_fluent/workflow.py`     | Pipeline/FanOut/Loop (Python)     | Auto-generated                    |
| `python/src/adk_fluent/_base.py`        | Operators, primitives             | Hand-written                      |
| `python/src/adk_fluent/_routing.py`     | Route builder                     | Hand-written                      |
| `python/src/adk_fluent/_transforms.py`  | S.\* state transforms             | Hand-written                      |
| `python/src/adk_fluent/_prompt.py`      | Prompt builder                    | Hand-written                      |
| `python/examples/cookbook/`             | Python runnable examples          | Hand-written                      |
| `python/tests/generated/`               | Auto-generated Python tests       | Auto-generated                    |
| `python/tests/manual/`                  | Hand-written Python tests         | Hand-written                      |
| `ts/src/builders/`                      | Agent/workflow builders (TS)      | Auto-generated                    |
| `ts/src/core/`                          | TS builder base, types, runtime   | Hand-written                      |
| `ts/src/namespaces/`                    | S/C/P/T/G/M/A/E/UI for TS         | Hand-written                      |
| `ts/src/patterns/`, `primitives/`, etc. | Hand-written TS extras            | Hand-written                      |
| `ts/examples/cookbook/`                 | TS runnable examples              | Hand-written                      |
| `ts/tests/`                             | TS test suites (vitest)           | Hand-written                      |
| `shared/scripts/`                       | Codegen pipeline (scan/seed/gen)  | Hand-written                      |
| `shared/manifest.json`                  | ADK scan (canonical source)       | Auto-generated                    |
| `shared/seeds/seed.toml`                | Generator configuration           | Auto-generated + manual overrides |
| `shared/seeds/seed.manual.toml`         | Manual overrides merged into seed | Hand-written                      |
| `docs/`                                 | Sphinx docs site                  | Hand-written + `docs/generated/`  |

### Important: editing generated files

Files listed as "Auto-generated" above will be **overwritten** when the generator runs. To make persistent changes:

1. Update `shared/scripts/seed_generator.py` (for extras, aliases, docstrings)
1. Update `shared/seeds/seed.toml` or `shared/seeds/seed.manual.toml` (for config)
1. Update `shared/scripts/generator.py` (for new behavior types)
1. Regenerate Python: `just generate` — or regenerate both languages: `just generate-all`
1. Verify the generated output matches your intent: `git diff python/src/adk_fluent ts/src/builders`

## Making Changes

### Bug fixes and small improvements

1. Fork the repo and create a branch: `git checkout -b fix/description`
1. Make your changes
1. Run tests: `just test`
1. Commit with a descriptive message
1. Open a PR

### New features

1. Open an issue first to discuss the approach
1. Fork and branch: `git checkout -b feat/description`
1. Add tests in `python/tests/manual/` (and/or `ts/tests/` if the feature touches TypeScript)
1. Add a cookbook example in `python/examples/cookbook/` — and the mirrored TS version in `ts/examples/cookbook/` when applicable
1. Run the full suite: `just test` (Python) and `just ts-test` (TypeScript), or `just test-all` for both
1. Open a PR

### Adding a new primitive or operator

1. Implement in `python/src/adk_fluent/_base.py` (Python) and `ts/src/core/builder-base.ts` + `ts/src/primitives/` (TypeScript)
1. Export from `python/src/adk_fluent/__init__.py` and `ts/src/index.ts`
1. Add tests in `python/tests/manual/` and `ts/tests/`
1. Add matching cookbook examples in both `python/examples/cookbook/` and `ts/examples/cookbook/`
1. Update the README expression language tables **and** the operator mapping in `docs/user-guide/typescript.md`

### When Google releases a new ADK version

The adk-fluent pipeline automatically stays in sync with `google-adk` via a weekly CI workflow ([sync-adk.yml](.github/workflows/sync-adk.yml)). When new ADK classes are detected, it auto-generates a PR with updated builders.

For manual upgrades or to prepare a PR yourself:

```bash
just archive                              # Save current manifest state
cd python && uv pip install --upgrade google-adk && cd ..   # Install new ADK version
just scan                                 # Introspect new ADK → shared/manifest.json
just diff                                 # Review what changed (JSON diff)
# Edit shared/seeds/seed.manual.toml if needed   # e.g. new aliases, custom extras
just all                                  # Regenerate Python code, stubs, tests, docs
just ts-generate                          # Regenerate TypeScript builders from the same manifest
just test-all && just typecheck           # Verify Python + TypeScript pass
git diff --stat                           # Review generated diff
```

For a detailed breakdown of what happens for each type of upstream change (new classes, renamed fields, removed APIs, etc.), see the [Upstream ADK Impact Analysis](docs/contributing/upstream-impact-analysis.md).

### Version Support Policy (N-5 Guarantee)

adk-fluent maintains backward compatibility with the **current and previous 5 releases** of `google-adk`. The CI pipeline enforces this via a compatibility matrix that runs the full test suite against each supported version.

**When updating the N-5 window** (e.g., when a new ADK version is released):

1. Add the new version to the top of the `compat` matrix in `.github/workflows/ci.yml`
2. Remove the oldest version from the bottom of the matrix
3. Update the compatibility table in `README.md`
4. The `pyproject.toml` floor (`google-adk>=1.20.0`) should only change if an ADK version introduces breaking changes that fundamentally prevent the builders from functioning

**Architecture note:** Code is *generated* against the latest ADK but must *execute* against older runtimes. The generated builders use `_safe_build()` which passes all config kwargs directly to ADK's Pydantic constructors. If a field doesn't exist in an older ADK, Pydantic rejects it with a clear error — there is no silent swallowing of unknown fields. This is by design: it's better to fail loudly than to silently ignore configuration.

## Agent Skills for Contributors

If you use an AI coding agent (Claude Code, Gemini CLI, Cursor, etc.), adk-fluent ships 14 agent skills that automate common contributor workflows. Skills activate automatically based on context:

| Task | Skill | What it does for you |
|------|-------|---------------------|
| Implement a new feature | `/develop-feature` | Classifies change type, provides implementation path, file locations |
| Write tests | `/write-tests` | Patterns for mock-based testing, contract checking, namespace verification |
| Add a cookbook example | `/add-cookbook` | Scaffolds runnable example with `.mock()` for CI compatibility |
| Debug a builder | `/debug-builder` | Systematic inspect → diagnose → fix workflow |
| Review a PR | `/review-pr` | 12-point automated checklist with helper scripts |
| Regenerate code | `/codegen-pipeline` | Step-by-step pipeline guidance |
| Upgrade ADK | `/upgrade-adk` | Impact analysis, regeneration, and rollback procedures |

Skills are already installed in `.claude/skills/` and `.gemini/skills/`. See [Agent Skills documentation](docs/editor-setup/agent-skills.md) for details.

## Code Style

- **Python:** we use [ruff](https://docs.astral.sh/ruff/) for linting and formatting. Run `just lint` / `just fmt` before committing (both operate inside `python/`). Pre-commit hooks handle formatting automatically on hand-written files only — generated files are owned by `just generate`.
- **TypeScript:** we use [eslint](https://eslint.org/) and [prettier](https://prettier.io/). Run `just ts-lint` / `cd ts && npm run format` before committing. Generated TS files under `ts/src/builders/` are owned by `just ts-generate` and should never be hand-edited.

### Dual-language documentation

The docs site (`docs/`) is Python-first but ships dual-language code samples for almost everything. When you add or update a code block in `docs/`, use synced `sphinx-design` tabs so readers see their chosen language across the entire site:

````md
::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("...").build()
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const agent = new Agent("helper", "gemini-2.5-flash").instruct("...").build();
```
:::
::::
````

**Rules:**

1. Use the sync keys **`python`** and **`ts`** exactly — anything else breaks the site-wide toggle.
2. Pair every `:sync: python` block with a `:sync: ts` block in the same `tab-set`. Never leave a tab-set with only one language.
3. If a feature exists only in Python, put a short callout in the TypeScript tab (e.g. "Not yet available in `adk-fluent-ts` — track in [`ts/README.md`](../../ts/README.md).") instead of omitting the tab.
4. Shared prose lives outside the tab-set. Only *code* and language-specific callouts go inside tabs.
5. Auto-generated pages (`docs/generated/**`) are emitted by `shared/scripts/` and don't need manual tab-set conversion — the generator will grow dual-language support separately.

## Testing

```bash
# Python — everything
just test

# Python — specific test file
cd python && uv run pytest tests/manual/test_operators.py -v

# Python — cookbook examples (each is a runnable test)
cd python && uv run pytest examples/cookbook/ -v

# TypeScript — everything
just ts-test

# Type checking (Python stubs + hand-written)
just typecheck && just typecheck-core

# Type checking (TypeScript)
just ts-typecheck

# Full local CI (mirrors GitHub Actions exactly — Python side)
just ci

# Both languages at once
just test-all
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `chore:` maintenance (CI, deps, tooling)
- `refactor:` code change that doesn't fix a bug or add a feature
- `test:` adding or updating tests

## Pull Request Process

1. Update the CHANGELOG.md with your changes under `[Unreleased]`
1. Ensure all tests pass and pre-commit hooks are clean
1. The PR will be reviewed and merged by a maintainer

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
