---
name: add-cookbook
description: Create a new cookbook example for adk-fluent. Use when the user wants to add a new example, demonstrate a feature, or create a tutorial. Each cookbook is a runnable pytest file.
allowed-tools: Bash, Read, Glob, Grep, Write, Edit
---

# Add a New Cookbook Example

Cookbook examples live in `examples/cookbook/` and serve as both documentation and tests.
They run in CI via pytest.

## Step 1: Determine the next number

```bash
ls examples/cookbook/*.py | sort | tail -5
```

Use the next sequential number (e.g., if the last is `43_primitives_showcase.py`, use `44`).

## Step 2: Create the file

Create `examples/cookbook/NN_descriptive_name.py` following this template:

```python
"""Cookbook NN: Descriptive Title

Demonstrates [what this example shows].
"""

import pytest
from unittest.mock import patch

from adk_fluent import Agent  # Import only what you need


def test_descriptive_name():
    """One-line description of what this test verifies."""
    # Use .mock() for examples that don't need a real LLM
    agent = (
        Agent("example", "gemini-2.5-flash")
        .instruct("Your instruction here.")
        .mock(["Expected response text"])
    )

    result = agent.ask("User prompt")
    assert "Expected" in result
```

## Rules

1. **Always use `.mock()`** — cookbook examples must run without API keys in CI
2. **One concept per file** — keep examples focused
3. **Use descriptive test function names** — they appear in test output
4. **Import from `adk_fluent`** — never from internal modules
5. **Use current API** — use `.writes()` not `.save_as()`, `.guard()` not `.guardrail()`
6. **Keep it short** — under 100 lines, ideally under 50

## Step 3: Verify it runs

```bash
uv run pytest examples/cookbook/NN_descriptive_name.py -v
```

## Step 4: Update the cookbook index

If a cookbook index or README exists in `examples/`, update it with the new entry.

## Available features to demonstrate

- Agent basics: `.instruct()`, `.model()`, `.describe()`
- Data flow: `.writes()`, `.reads()`, `.returns()`
- Operators: `>>`, `|`, `*`, `//`, `@`
- Workflows: Pipeline, FanOut, Loop
- Primitives: `tap`, `gate`, `race`, `map_over`, `dispatch`, `join`
- Namespaces: S, C, P, A, M, T, E, G
- Patterns: `review_loop`, `map_reduce`, `cascade`, `fan_out_merge`, `chain`
- Testing: `.mock()`, `.test()`, `.eval()`
- Introspection: `.explain()`, `.diagnose()`, `.data_flow()`
