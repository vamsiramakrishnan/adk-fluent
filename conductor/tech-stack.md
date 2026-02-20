# Technology Stack - adk-fluent

## Core Language & Runtime
- **Python 3.11+:** Targeted for modern async/await support and advanced type hinting.
- **uv:** High-performance Python package installer and resolver.

## Main Frameworks
- **google-adk (≥1.20.0):** The underlying foundation for agent and pipeline execution.
- **Pydantic (≥2.0):** Used by ADK for configuration schemas and validation.

## Development & Build Tools
- **hatchling:** The build backend for producing standardized Python packages.
- **just:** Task runner for orchestrating the scanner/seed/generator pipeline and local workflows.

## Quality Assurance
- **ruff:** Blazing fast Python linter and formatter.
- **mdformat:** Unopinionated Markdown formatter for documentation consistency.
- **pyright:** Static type checker for validating generated stubs and core logic.
- **pytest:** Feature-rich testing framework with \`pytest-cov\` and \`pytest-asyncio\`.

## Documentation
- **sphinx:** Standard Python documentation engine.
- **myst-parser:** Enables rich Markdown support in Sphinx.
- **furo:** A clean, modern theme for Sphinx documentation.
- **sphinx-autobuild:** Provides a live-reloading preview during documentation development.
