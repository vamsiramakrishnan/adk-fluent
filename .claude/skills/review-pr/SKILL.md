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

## Checklist

### 1. Generated file protection

Check if any auto-generated files were edited directly:

```
agent.py, workflow.py, tool.py, config.py, runtime.py, service.py,
plugin.py, executor.py, planner.py, _ir_generated.py, __init__.py,
and their .pyi stubs
```

These files MUST NOT be edited directly. Changes should go through
`seeds/seed.manual.toml` or the generator scripts.

**How to verify**: Run `just check-gen` — if generated files differ after
regeneration, someone hand-edited them.

### 2. Deprecated method usage

Check for usage of deprecated methods in new/changed code:

| Deprecated | Use instead |
|-----------|-------------|
| `.save_as()` | `.writes()` |
| `.delegate()` | `.agent_tool()` |
| `.guardrail()` | `.guard()` |
| `.retry_if()` | `.loop_while()` |
| `.inject_context()` | `.prepend()` |
| `.output_schema()` | `.returns()` |
| `.output_key()` / `.outputs()` | `.writes()` |
| `.history()` / `.include_history()` | `.context()` |

### 3. Import hygiene

Verify imports are from `adk_fluent` top-level, not internal modules:
- Never: `from adk_fluent._base import ...`
- Never: `from adk_fluent.agent import ...`
- Never: `from adk_fluent._transforms import ...`
- Always: `from adk_fluent import Agent, Pipeline, S, C, P, ...`

Exception: Tests in `tests/` may import internals when specifically testing them.

### 4. Test coverage

- New features must have tests in `tests/manual/`
- Cookbook examples must use `.mock()` (no real API keys in CI)
- Tests must pass: `uv run pytest tests/ -x -q --tb=short`
- Look for edge cases: empty state, missing keys, None values

### 5. Tooling consistency

- All bash commands must use `uv run` (never bare `python` or `pip`)
- All dependency installs must use `uv pip install` or `uv sync` (never bare `pip install`)
- Scripts must be run via `uv run python scripts/...`

### 6. N-5 backward compatibility

If the PR changes any of these, verify the N-5 compat matrix is updated:
- `.github/workflows/ci.yml` — `compat` job `adk-version` matrix
- `.github/workflows/sync-adk.yml` — `test` job `adk-version` matrix
- `README.md` — ADK Compatibility table

If the PR adds new builder methods that use kwargs only available in newer
ADK versions, note that these will raise `BuilderError` on older runtimes
(which is the expected behavior, not a bug).

### 7. CHANGELOG

- Changes should be documented under `[Unreleased]` in `CHANGELOG.md`
- Follow Conventional Commits format (feat, fix, refactor, docs, etc.)

### 8. Type safety

- New public methods should have type annotations
- Fluent methods must return `Self` for chaining
- Run: `uv run pyright src/adk_fluent/`

### 9. API design consistency

Check that new builder methods follow established patterns:
- **Naming**: verb-based (`.instruct()`, `.writes()`, `.guard()`), not noun-based
- **Chaining**: Every config method returns `Self`
- **Immutability**: Operators (`>>`, `|`, `*`, `//`, `@`) create new instances
- **Overloading**: Methods accept both simple values and namespace objects (e.g., `.instruct(str | PTransform)`)
- **No side effects**: Config methods only store state; `.build()` does the work

### 10. Anti-patterns in application code

Flag these patterns in new code:
- **LLM routing when `Route()` works** — if the routing decision is deterministic, use `Route(key).eq()`
- **Retry logic in tool functions** — use `M.retry()` middleware instead
- **Manual state management** — use `.writes()` / `.reads()` / `S.*` transforms
- **Bare `BaseAgent` subclass** — use builder API or `tap()` for function steps
- **`.build()` on sub-builders** — inside Pipeline/FanOut/Loop, sub-builders auto-build
- **Exposing infra in tool schemas** — use `.inject()` for DB clients, API keys, etc.

### 11. Security considerations

- No API keys, tokens, or secrets in code or test fixtures
- `.inject()` used for infrastructure dependencies (not tool schemas)
- No `eval()` or `exec()` on user-provided strings
- File paths properly sanitized if used in tools

### 12. Performance patterns

- `C.window(n=)` or `C.budget(max_tokens=)` used for agents with long conversations
- `C.none()` used for background/utility agents that don't need history
- `.timeout()` used for agents that might hang
- `M.cache()` considered for expensive, repeated queries

## Output format

Provide findings as:
- **Blockers**: Must fix before merge
- **Suggestions**: Nice to have but not blocking
- **Questions**: Things that need clarification from the author
- **Praise**: What the PR does well
