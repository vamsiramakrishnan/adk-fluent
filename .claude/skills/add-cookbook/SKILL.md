---
name: add-cookbook
description: Create a new cookbook example for adk-fluent. Use when the user wants to add a new example, demonstrate a feature, or create a tutorial. Each cookbook is a runnable pytest file.
allowed-tools: Bash, Read, Glob, Grep, Write, Edit
---

# Add a New Cookbook Example

Cookbook examples live in `examples/cookbook/` and serve as both documentation and tests.
They run in CI via pytest across all supported ADK versions.

## Step 1: Determine the next number

```bash
ls examples/cookbook/*.py | sort | tail -5
```

Use the next sequential number.

## Step 2: Choose the right pattern

### Simple agent (most common)

```python
"""Cookbook NN: Descriptive Title

Demonstrates [what this example shows].
"""

from adk_fluent import Agent


def test_descriptive_name():
    """One-line description of what this test verifies."""
    agent = (
        Agent("example", "gemini-2.5-flash")
        .instruct("Your instruction here.")
        .mock(["Expected response text"])
    )

    result = agent.ask("User prompt")
    assert "Expected" in result
```

### Pipeline with data flow

```python
from adk_fluent import Agent, Pipeline

def test_pipeline_with_data_flow():
    pipeline = (
        Pipeline("flow")
        .step(Agent("researcher").instruct("Research.").writes("research").mock(["Findings"]))
        .step(Agent("writer").instruct("Write using {research}.").reads("research").mock(["Summary"]))
    )
    result = pipeline.build()
    assert result is not None
```

### Expression operators

```python
a = Agent("a").mock(["A"])
b = Agent("b").mock(["B"])
pipeline = a >> b       # Sequential
fanout = a | b          # Parallel
loop = (a >> b) * 3     # Loop
```

### Namespace modules

```python
from adk_fluent import Agent, P, C

agent = Agent("analyst").instruct(
    P.role("Data analyst.") + P.task("Analyze data.") + P.constraint("Be concise")
).context(C.window(n=5))
```

### Routing

```python
from adk_fluent import Agent, Route

router = Route("tier").eq("VIP", vip_agent).otherwise(standard_agent)
```

## Rules

1. **Always use `.mock()`** — cookbook examples must run without API keys in CI
2. **One concept per file** — keep examples focused on a single feature
3. **Use descriptive test function names** — they appear in test output
4. **Import from `adk_fluent`** — never from internal modules
5. **Use current API** — for deprecated method mappings, read [`../_shared/references/deprecated-methods.md`](../_shared/references/deprecated-methods.md)
6. **Keep it short** — under 100 lines, ideally under 50
7. **Use `gemini-2.5-flash`** — as the default model in examples

## Anti-patterns to avoid

- **Don't test the mock** — test that the builder wires things correctly
- **Don't import from internals** — `from adk_fluent._base import ...` will break
- **Don't call `.build()` on sub-builders** — inside Pipeline/FanOut/Loop, sub-builders auto-build
- **Don't use LLM routing when Route works** — use deterministic `Route()` for rule-based decisions

## Step 3: Verify it runs

```bash
uv run pytest examples/cookbook/NN_descriptive_name.py -v
```

## Step 4: Update the cookbook index

If a cookbook index or README exists in `examples/`, update it with the new entry.

## Available features

For the complete API surface and available features to demonstrate, read:
- [`../_shared/references/api-surface.md`](../_shared/references/api-surface.md) — all builder methods
- [`../_shared/references/patterns-and-primitives.md`](../_shared/references/patterns-and-primitives.md) — operators, primitives, patterns
- [`../_shared/references/namespace-methods.md`](../_shared/references/namespace-methods.md) — S, C, P, A, M, T, E, G methods
