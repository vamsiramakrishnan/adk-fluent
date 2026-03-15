---
name: develop-feature
description: Implement a new feature for adk-fluent. Use when adding new builder methods, namespace functions, patterns, operators, or other capabilities to the library.
allowed-tools: Bash, Read, Glob, Grep, Write, Edit
---

# Develop a New Feature for adk-fluent

Guide for implementing new features with correct architecture, testing, and documentation.

## Step 1: Classify the change

| Change type | Where to edit | Regenerate? |
|------------|---------------|-------------|
| New builder method | `_base.py` + `seed.manual.toml` (extras) | Yes — `just generate` |
| New namespace function (S.xxx, C.xxx) | Corresponding `_*.py` module | No |
| New operator overload | `_base.py` | No |
| New primitive (tap, gate, etc.) | `_primitives.py` + `_base.py` | No |
| New composition pattern | `patterns.py` | No |
| New middleware | `middleware.py` | No |
| New generated builder | `seed.manual.toml` | Yes — `just all` |
| New decorator | `decorators.py` | No |

For the complete file classification, read
[`../_shared/references/generated-files.md`](../_shared/references/generated-files.md).

## Step 2: Implement

### Adding a builder method

1. Implement in `_base.py`:

```python
def my_method(self, value: str) -> Self:
    """One-line description."""
    self._config["my_field"] = value
    return self
```

2. Register in `seed.manual.toml`:

```toml
[[builders.Agent.extras]]
method = "my_method"
sig = "(self, value: str) -> Self"
doc = "One-line description."
```

3. Handle in `backends/adk.py` if the method sets ADK-bound data.
4. Regenerate: `just generate`

### Adding a namespace function

Add to the relevant module (e.g., `_transforms.py` for S):

```python
@staticmethod
def new_transform(key: str) -> "STransform":
    """One-line description."""
    def _apply(state: dict) -> dict:
        return state
    return STransform(_apply, repr=f"S.new_transform({key!r})")
```

No regeneration needed.

### Adding a composition pattern

Add to `patterns.py`:

```python
def my_pattern(agent1, agent2, *, key="result") -> "BuilderBase":
    """One-line description."""
    return agent1.writes(key) >> agent2.reads(key)
```

## Step 3: Write tests

Tests go in `tests/manual/`. Use `.mock()` for all tests.
For detailed testing guidance, see the write-tests skill.

```python
def test_my_feature_basic():
    agent = Agent("test").my_method("value").mock(["ok"])
    result = agent.ask("test")
    assert result is not None

def test_my_feature_validates():
    agent = Agent("test").my_method("value")
    assert not agent.validate()
```

## Step 4: Update documentation

1. Add a cookbook example if user-facing (see add-cookbook skill)
2. Update `seeds/seed.manual.toml` with method docs
3. Regenerate: `uv run python scripts/llms_generator.py manifest.json seeds/seed.toml`
4. Regenerate skill references: `just skills`

## Step 5: Verify

```bash
uv run pytest tests/ -x -q --tb=short     # Tests pass
uv run pyright src/adk_fluent/              # Type checking
uv run ruff check .                         # Linting
just check-gen                              # Generated files canonical
```

## Best practices

- **Fluent return**: Every config method returns `Self`
- **Immutability**: Operators create new instances (copy-on-write)
- **No side effects**: Config methods only store state; `.build()` does the work
- **Verb naming**: `.instruct()`, `.writes()`, `.guard()` — not nouns
- **Accept both simple and composed**: e.g., `.instruct(str | PTransform)`
- **Fail early**: Use `.validate()` to catch config errors before `.build()`

## References

- [`../_shared/references/api-surface.md`](../_shared/references/api-surface.md) — existing methods and signatures
- [`../_shared/references/builder-inventory.md`](../_shared/references/builder-inventory.md) — all builders by module
- [`../_shared/references/generated-files.md`](../_shared/references/generated-files.md) — what's generated vs hand-written
