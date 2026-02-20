# Contributing to adk-fluent

Thanks for your interest in contributing! This guide covers everything you need to get started.

## Development Setup

```bash
# Clone and install
git clone https://github.com/vamsiramakrishnan/adk-fluent.git
cd adk-fluent
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev,docs,yaml,examples]"

# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run the full codegen pipeline
just all

# Run tests
just test
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
| `examples/cookbook/`            | 43 runnable examples              | Hand-written                      |
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

## Code Style

- We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Run `ruff check .` and `ruff format .` before committing
- Pre-commit hooks handle this automatically

## Testing

```bash
# All tests
just test

# Specific test file
pytest tests/manual/test_operators.py -v

# Cookbook examples (each is a runnable test)
pytest examples/cookbook/ -v

# Type checking
just typecheck
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
