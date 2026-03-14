---
name: review-pr
description: Review a pull request for adk-fluent with project-specific checks. Use when reviewing PRs, checking code quality, or validating changes before merge.
context: fork
agent: Explore
allowed-tools: Bash, Read, Glob, Grep
---

# adk-fluent PR Review

Review this pull request with adk-fluent-specific quality checks.

## PR context

- Changed files: !`git diff --name-only HEAD~1`
- Diff stats: !`git diff --stat HEAD~1`

## Automated checks

Run these helper scripts for quick automated scanning:

```bash
# Check for deprecated method usage in changed files
uv run .claude/skills/_shared/scripts/check-deprecated.py src/ tests/ examples/

# Check for internal module imports
uv run .claude/skills/_shared/scripts/validate-imports.py src/ tests/ examples/

# Verify no generated files were hand-edited
just check-gen
```

## Checklist

### 1. Generated file protection

Check if any auto-generated files were edited directly.
Run `uv run .claude/skills/_shared/scripts/list-generated-files.py` to see the full list,
or read [`../_shared/references/generated-files.md`](../_shared/references/generated-files.md).

Changes to generated files should go through `seeds/seed.manual.toml` or the generator scripts.

### 2. Deprecated method usage

Run `uv run .claude/skills/_shared/scripts/check-deprecated.py` on changed files.
For the complete mapping table, read
[`../_shared/references/deprecated-methods.md`](../_shared/references/deprecated-methods.md).

### 3. Import hygiene

Run `uv run .claude/skills/_shared/scripts/validate-imports.py` on changed files.
- Always: `from adk_fluent import Agent, Pipeline, S, C, P, ...`
- Never: `from adk_fluent._base import ...` or `from adk_fluent.agent import ...`

Exception: Tests in `tests/` may import internals when specifically testing them.

### 4. Test coverage

- New features must have tests in `tests/manual/`
- Cookbook examples must use `.mock()` (no real API keys in CI)
- Tests must pass: `uv run pytest tests/ -x -q --tb=short`

### 5. Tooling consistency

- All bash commands must use `uv run` (never bare `python` or `pip`)
- Scripts must be run via `uv run python scripts/...`

### 6. N-5 backward compatibility

If the PR changes any of these, verify the N-5 compat matrix is updated:
- `.github/workflows/ci.yml` — `compat` job `adk-version` matrix
- `.github/workflows/sync-adk.yml` — `test` job `adk-version` matrix
- `README.md` — ADK Compatibility table

### 7. CHANGELOG

- Changes should be documented under `[Unreleased]` in `CHANGELOG.md`
- Follow Conventional Commits format (feat, fix, refactor, docs, etc.)

### 8. Type safety

- New public methods should have type annotations
- Fluent methods must return `Self` for chaining
- Run: `uv run pyright src/adk_fluent/`

### 9. API design consistency

- **Naming**: verb-based (`.instruct()`, `.writes()`), not noun-based
- **Chaining**: Every config method returns `Self`
- **Immutability**: Operators create new instances (copy-on-write)
- **No side effects**: Config methods only store state; `.build()` does the work

### 10. Anti-patterns

- **LLM routing when `Route()` works** — deterministic routing preferred
- **Retry logic in tools** — use `M.retry()` middleware
- **`.build()` on sub-builders** — auto-built inside Pipeline/FanOut/Loop
- **Exposing infra in tool schemas** — use `.inject()` for DB clients, API keys

### 11. Security

- No API keys, tokens, or secrets in code or test fixtures
- No `eval()` or `exec()` on user-provided strings

### 12. Performance

- `C.window(n=)` or `C.none()` for context management
- `.timeout()` for agents that might hang

## Output format

- **Blockers**: Must fix before merge
- **Suggestions**: Nice to have but not blocking
- **Questions**: Need clarification from the author
- **Praise**: What the PR does well
