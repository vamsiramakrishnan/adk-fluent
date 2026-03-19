# Contributing

Thanks for your interest in contributing to adk-fluent! This guide covers the development workflow, code standards, and how to get your changes merged.

## Quick Start

```bash
# Clone and install in dev mode
git clone https://github.com/vamsiramakrishnan/adk-fluent.git
cd adk-fluent
pip install -e ".[dev,docs]"

# Run tests
uv run pytest tests/ -v --tb=short

# Lint and format
uv run ruff check .
uv run ruff format .
```

## Development Workflow

1. **Fork and branch** — Create a feature branch from `master`
2. **Write code** — Follow the existing patterns in `src/adk_fluent/`
3. **Add tests** — Tests live in `tests/` and use pytest
4. **Lint** — Run `uv run ruff check . && uv run ruff format .`
5. **Open a PR** — Target `master`, describe what and why

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `src/adk_fluent/` | Library source code |
| `src/adk_fluent/*.pyi` | Type stubs for IDE autocomplete |
| `tests/` | Test suite (pytest) |
| `docs/` | Sphinx documentation |
| `scripts/` | Code generation and build tools |
| `examples/` | Runnable example agents |

## Code Standards

- **Python 3.11+** — Use modern syntax (`match`, `|` union types in annotations)
- **Ruff** — Linting and formatting (config in `pyproject.toml`)
- **Type hints** — All public APIs must have type annotations
- **No breaking changes** to public API without discussion in an issue first

## Generated Code

Many builder modules (`agent.py`, `tool.py`, `config.py`, etc.) and their `.pyi` stubs are **auto-generated** from `manifest.json`. Do not edit these files directly — your changes will be overwritten. Instead:

1. Modify the generation templates in `scripts/`
2. Run the codegen pipeline to regenerate

See the guides below for details.

## Detailed Guides

```{toctree}
---
maxdepth: 2
---
codegen-pipeline
upstream-impact-analysis
namespace-robustness
adding-builders
```
