---
name: review-pr
description: Review a pull request for adk-fluent with project-specific checks. Use when reviewing PRs, checking code quality, or validating changes before merge.
---

# adk-fluent PR Review

Review this pull request with adk-fluent-specific quality checks.

## Checklist

### 1. Generated file protection

Check if any auto-generated files were edited directly:

```
agent.py, workflow.py, tool.py, config.py, runtime.py, service.py,
plugin.py, executor.py, planner.py, and their .pyi stubs
```

These files MUST NOT be edited directly. Changes should go through
`seeds/seed.manual.toml` or the generator scripts.

### 2. Deprecated method usage

Check for usage of deprecated methods in new/changed code:
- `.save_as()` -> use `.writes()`
- `.delegate()` -> use `.agent_tool()`
- `.guardrail()` -> use `.guard()`
- `.retry_if()` -> use `.loop_while()`
- `.inject_context()` -> use `.prepend()`
- `.output_schema()` -> use `.returns()`
- `.history()` / `.include_history()` -> use `.context()`

### 3. Import hygiene

Verify imports are from `adk_fluent` top-level, not internal modules:
- Never: `from adk_fluent._base import ...`
- Never: `from adk_fluent.agent import ...`
- Always: `from adk_fluent import Agent, Pipeline, ...`

### 4. Test coverage

- New features must have tests in `tests/manual/`
- Cookbook examples must use `.mock()` (no real API keys in CI)
- Run: `uv run pytest tests/ -x -q --tb=short`

### 5. Tooling consistency

- All bash commands must use `uv run` (never bare `python` or `pip`)
- All dependency installs must use `uv pip install` or `uv sync` (never bare `pip install`)

### 6. N-5 backward compatibility

If the PR changes any of these, verify the N-5 compat matrix is updated:
- `.github/workflows/ci.yml` — `compat` job `adk-version` matrix
- `.github/workflows/sync-adk.yml` — `test` job `adk-version` matrix
- `README.md` — ADK Compatibility table

If the PR adds new builder methods that use kwargs only available in newer ADK versions, note that these will raise `BuilderError` on older runtimes (which is the expected behavior, not a bug).

### 7. CHANGELOG

- Changes should be documented under `[Unreleased]` in `CHANGELOG.md`
- Follow Conventional Commits format

### 8. Type safety

- New public methods should have type annotations
- Fluent methods must return `Self` for chaining
- Run: `uv run pyright src/adk_fluent/`

## Output format

Provide findings as:
- **Blockers**: Must fix before merge
- **Suggestions**: Nice to have but not blocking
- **Praise**: What the PR does well
