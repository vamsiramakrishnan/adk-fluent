# Plan: Markdown Auto-Formatting

## Context

The project has excellent code formatting via Ruff, but Markdown files were not being auto-formatted. To ensure high-quality and consistent documentation throughout the repository, we need to introduce a Markdown formatter, hook it up to the pre-commit configuration, and add it to our `justfile` workflow.

## [DONE] Phase 1: Tool Selection and Dependencies

- **Tool Selection**: Since this is a Python project managed by `uv`, using `mdformat` is optimal. It's an unopinionated formatter, fast, and easily installable via pip. It integrates nicely with the Sphinx/MyST parser ecosystem.
- **Dependencies**: Add `mdformat`, `mdformat-gfm` (for GitHub Flavored Markdown), and `mdformat-myst` (for MyST parsing compatible formatting) to the `dev` dependency group in `pyproject.toml`.
- **Install**: Run `uv sync --all-extras` to install the formatter and its extensions locally.

## [DONE] Phase 2: Workflow Integration

- **`justfile` Extension**:
  - Add a dedicated `just format` command that runs both `ruff` and `mdformat` fixing any issues.
  - Update `just lint` to include `mdformat --check .` to ensure CI will fail if Markdown isn't properly formatted.
  - Update the help documentation within `justfile` to showcase `just format`.

## [DONE] Phase 3: Pre-commit Integration

- **`.pre-commit-config.yaml`**: Add a hook for `mdformat` from `https://github.com/executablebooks/mdformat`.
- Include `additional_dependencies` for `mdformat-gfm` and `mdformat-myst` in the pre-commit hook so it resolves extensions during commit validation.

## [DONE] Phase 4: Full Codebase Formatting

- Run `just format` to format all existing Markdown files across the codebase, bringing the documentation to a consistent, high standard.

## Track Summary

We have successfully added `mdformat` to automatically format all Markdown files in the project. The formatter is fully integrated into the standard workflow commands (`just format`, `just lint`) and git hooks (`pre-commit`), bringing docs parity with Python's formatting infrastructure.
