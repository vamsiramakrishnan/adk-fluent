---
name: develop-feature
description: Implement a new feature for adk-fluent. Use when adding new builder methods, namespace functions, patterns, operators, or other capabilities to the library.
allowed-tools: Bash, Read, Glob, Grep, Write, Edit
---

# Develop a New Feature for adk-fluent

Guide for implementing new features with correct architecture, testing, and documentation.

## Step 1: Classify the change

Before writing code, determine what kind of change this is:

| Change type | Where to edit | Regenerate? |
|------------|---------------|-------------|
| New builder method on Agent/Pipeline/etc. | `seeds/seed.manual.toml` (extras section) + `_base.py` (implementation) | Yes — `just generate` |
| New namespace function (S.xxx, C.xxx, etc.) | Corresponding `_*.py` module | No |
| New operator overload | `_base.py` | No |
| New primitive (tap, gate, etc.) | `_primitives.py` + `_base.py` (re-export) | No |
| New composition pattern | `patterns.py` | No |
| New middleware | `middleware.py` | No |
| New generated builder (wrapping ADK class) | `seeds/seed.manual.toml` | Yes — `just all` |
| Bug fix in builder behavior | `_base.py` or relevant module | Maybe |
| New decorator | `decorators.py` | No |
| New CLI command | `cli.py` | No |

## Step 2: Understand the architecture

### Hand-written core (safe to edit directly)

```
src/adk_fluent/
├── _base.py          # BuilderBase mixin — ALL builder methods live here
├── _context.py       # C namespace — context engineering specs
├── _prompt.py        # P namespace — prompt composition
├── _transforms.py    # S namespace — state transforms
├── _routing.py       # Route() and Fallback() — deterministic routing
├── _primitives.py    # Runtime agents for primitives (tap, gate, race, etc.)
├── _middleware.py     # M namespace — middleware composition
├── _tools.py         # T namespace — tool composition
├── _guards.py        # G namespace — guard composition
├── _artifacts.py     # A namespace — artifact operations
├── _eval.py          # E namespace — evaluation builders
├── _visibility.py    # Topology visibility modes
├── patterns.py       # Higher-order patterns (review_loop, map_reduce, etc.)
├── middleware.py      # Built-in middleware implementations
├── decorators.py     # @agent, @tool decorators
├── viz.py            # Visualization and explanation helpers
├── di.py             # Dependency injection
├── prelude.py        # Minimal entry point
└── cli.py            # CLI interface
```

### Generated code (NEVER edit directly)

```
src/adk_fluent/
├── agent.py          # Agent builder (from LlmAgent)
├── workflow.py       # Pipeline, FanOut, Loop builders
├── tool.py           # 51+ tool builders
├── config.py         # 38+ config builders
├── runtime.py        # App, Runner builders
├── service.py        # Session/artifact/memory service builders
├── plugin.py         # Plugin builders
├── executor.py       # Code executor builders
├── planner.py        # Planner builders
├── _ir_generated.py  # IR node classes
└── *.pyi             # Type stubs
```

## Step 3: Implement the feature

### Adding a new builder method

1. **Add to `_base.py`** — implement the method on `BuilderBase`:

```python
def my_method(self, value: str) -> Self:
    """One-line description of what this does."""
    self._config["my_field"] = value
    return self
```

2. **Register in `seed.manual.toml`** — add an extras entry so codegen knows about it:

```toml
[[builders.Agent.extras]]
method = "my_method"
sig = "(self, value: str) -> Self"
doc = "One-line description."
```

3. **Handle in backend** — if the method sets data that needs to reach ADK, update `backends/adk.py`.

4. **Regenerate** — `just generate` to update stubs and `__init__.py`.

### Adding a namespace function (e.g., S.new_transform)

1. **Add to the namespace module** (e.g., `_transforms.py`):

```python
@staticmethod
def new_transform(key: str) -> "STransform":
    """One-line description."""
    def _apply(state: dict) -> dict:
        # transform logic
        return state
    return STransform(_apply, repr=f"S.new_transform({key!r})")
```

2. **Export from `__init__.py`** — the function is already available via `S.new_transform()`.

3. **No regeneration needed** — namespace modules are hand-written.

### Adding a new primitive

1. **Create runtime agent** in `_primitives.py`:

```python
class MyPrimitiveAgent(BaseAgent):
    """Runtime agent for my_primitive."""
    # ...implementation...
```

2. **Create factory function** in `_base.py` or `_primitives.py`:

```python
def my_primitive(arg) -> "BuilderBase":
    """One-line description."""
    # ...
```

3. **Export** from `__init__.py`.

### Adding a composition pattern

1. **Add to `patterns.py`**:

```python
def my_pattern(agent1, agent2, *, key="result") -> "BuilderBase":
    """One-line description.

    Args:
        agent1: First agent (builder or built).
        agent2: Second agent.
        key: State key for intermediate data.
    """
    return (
        agent1.writes(key)
        >> agent2.reads(key)
    )
```

2. **Export** from `__init__.py`.

## Step 4: Write tests

Tests go in `tests/manual/`. Follow these rules:

- **Use `.mock()`** for all tests — no real API calls
- **Test the builder wiring**, not the mock responses
- **Cover edge cases**: empty state, missing keys, None values
- **Test operators** if your feature interacts with `>>`, `|`, `*`, `//`, `@`
- **Test immutability**: verify original builder is unchanged after operator use

```python
"""Tests for my_feature."""

import pytest
from adk_fluent import Agent


def test_my_feature_basic():
    agent = Agent("test", "gemini-2.5-flash").my_method("value").mock(["ok"])
    result = agent.ask("test")
    assert result is not None


def test_my_feature_with_pipeline():
    a = Agent("a").my_method("x").mock(["a"])
    b = Agent("b").mock(["b"])
    pipeline = a >> b
    assert pipeline is not None


def test_my_feature_validates():
    agent = Agent("test").my_method("value")
    issues = agent.validate()
    assert not issues
```

## Step 5: Update documentation

1. **Add a cookbook example** if the feature is user-facing (see add-cookbook skill)
2. **Update `seeds/seed.manual.toml`** with method docs
3. **Regenerate docs**: `uv run python scripts/llms_generator.py manifest.json seeds/seed.toml`

## Step 6: Verify

```bash
uv run pytest tests/ -x -q --tb=short     # All tests pass
uv run pyright src/adk_fluent/              # Type checking
uv run ruff check .                         # Linting
just check-gen                              # Generated files canonical
```

## Best practices

- **Fluent return**: Every config method returns `Self` for chaining
- **Immutability**: Operators create new instances (copy-on-write)
- **No side effects**: Config methods only store state; `.build()` does the work
- **Verb naming**: `.instruct()`, `.writes()`, `.guard()` — not nouns
- **Accept both simple and composed**: e.g., `.instruct(str | PTransform)`
- **Fail early**: Use `.validate()` to catch config errors before `.build()`
- **Backward compat**: New methods should work or raise `BuilderError` on older ADK versions
