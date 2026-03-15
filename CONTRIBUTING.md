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
- [just](https://github.com/casey/just) command runner
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## How the Codebase Works

adk-fluent is **auto-generated** from the installed `google-adk` package:

```
scanner.py --> manifest.json --> seed_generator.py --> seed.toml --> generator.py --> Python code
```

### Key directories

| Path                            | What it is                        | Hand-written?                     |
| ------------------------------- | --------------------------------- | --------------------------------- |
| `src/adk_fluent/agent.py`       | Agent builder                     | Auto-generated                    |
| `src/adk_fluent/workflow.py`    | Pipeline/FanOut/Loop builders     | Auto-generated                    |
| `src/adk_fluent/_base.py`       | Operators, primitives             | Hand-written                      |
| `src/adk_fluent/_routing.py`    | Route builder                     | Hand-written                      |
| `src/adk_fluent/_transforms.py` | S.\* state transforms             | Hand-written                      |
| `src/adk_fluent/_prompt.py`     | Prompt builder                    | Hand-written                      |
| `scripts/`                      | Codegen pipeline                  | Hand-written                      |
| `seeds/seed.toml`               | Generator configuration           | Auto-generated + manual overrides |
| `seeds/seed.manual.toml`        | Manual overrides merged into seed | Hand-written                      |
| `examples/cookbook/`            | 68 runnable examples              | Hand-written                      |
| `tests/generated/`              | Auto-generated tests              | Auto-generated                    |
| `tests/manual/`                 | Hand-written tests                | Hand-written                      |

### Important: editing generated files

Files in `src/adk_fluent/agent.py`, `workflow.py`, and other generated modules will be **overwritten** when the generator runs. To make persistent changes:

1. Update `scripts/seed_generator.py` (for extras, aliases, docstrings)
1. Update `seeds/seed.toml` or `seeds/seed.manual.toml` (for config)
1. Update `scripts/generator.py` (for new behavior types)
1. Regenerate: `just generate`
1. Verify the generated output matches your intent

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
1. Add tests in `tests/manual/` for hand-written code
1. Add a cookbook example in `examples/cookbook/` if applicable
1. Run the full suite: `just test`
1. Open a PR

### Adding a new primitive or operator

1. Implement in `src/adk_fluent/_base.py`
1. Export from `src/adk_fluent/__init__.py`
1. Add tests in `tests/manual/`
1. Add a cookbook example
1. Update the README expression language tables

### When Google releases a new ADK version

The adk-fluent pipeline automatically stays in sync with `google-adk` via a weekly CI workflow ([sync-adk.yml](.github/workflows/sync-adk.yml)). When new ADK classes are detected, it auto-generates a PR with updated builders.

For manual upgrades or to prepare a PR yourself:

```bash
just archive                              # Save current manifest state
uv pip install --upgrade google-adk       # Install new ADK version
just scan                                 # Introspect new ADK → manifest.json
just diff                                 # Review what changed (JSON diff)
# Edit seeds/seed.manual.toml if needed   # e.g. new aliases, custom extras
just all                                  # Regenerate code, stubs, tests, docs
just test && just typecheck               # Verify everything passes
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

- We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Run `uv run ruff check .` and `uv run ruff format .` before committing
- Pre-commit hooks handle this automatically

## Testing

```bash
# All tests
just test

# Specific test file
uv run pytest tests/manual/test_operators.py -v

# Cookbook examples (each is a runnable test)
uv run pytest examples/cookbook/ -v

# Type checking
just typecheck

# Full local CI (mirrors GitHub Actions exactly)
just ci
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
