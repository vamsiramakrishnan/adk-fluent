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

Use the next sequential number (e.g., if the last is `67_g_module_guards.py`, use `68`).

## Step 2: Choose the right pattern

Pick a template based on complexity:

### Simple agent (most common)

```python
"""Cookbook NN: Descriptive Title

Demonstrates [what this example shows].
"""

import pytest
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
    """Demonstrates state passing between pipeline steps."""
    pipeline = (
        Pipeline("flow")
        .step(
            Agent("researcher", "gemini-2.5-flash")
            .instruct("Research the topic.")
            .writes("research")
            .mock(["Research findings here"])
        )
        .step(
            Agent("writer", "gemini-2.5-flash")
            .instruct("Write a summary using {research}.")
            .reads("research")
            .mock(["Summary of findings"])
        )
    )
    result = pipeline.build()
    assert result is not None
```

### Expression operators

```python
from adk_fluent import Agent


def test_operator_composition():
    """Demonstrates >> and | operators."""
    a = Agent("a", "gemini-2.5-flash").instruct("Step A.").mock(["A done"])
    b = Agent("b", "gemini-2.5-flash").instruct("Step B.").mock(["B done"])
    c = Agent("c", "gemini-2.5-flash").instruct("Step C.").mock(["C done"])

    # Sequential
    pipeline = a >> b >> c

    # Parallel
    fanout = a | b | c

    assert pipeline is not None
    assert fanout is not None
```

### Namespace modules (S, C, P, M, T, G)

```python
from adk_fluent import Agent, S, C, P


def test_namespace_composition():
    """Demonstrates composing namespace modules."""
    agent = (
        Agent("analyzer", "gemini-2.5-flash")
        .instruct(
            P.role("You are a data analyst.")
            + P.task("Analyze the provided data.")
            + P.constraint("Be concise", "Use bullet points")
        )
        .context(C.window(n=5) + C.from_state("data"))
        .mock(["Analysis complete"])
    )
    result = agent.ask("Analyze this")
    assert result is not None
```

### Routing patterns

```python
from adk_fluent import Agent, Route


def test_deterministic_routing():
    """Demonstrates Route for rule-based agent selection."""
    vip = Agent("vip", "gemini-2.5-flash").instruct("VIP handler.").mock(["VIP"])
    std = Agent("std", "gemini-2.5-flash").instruct("Standard handler.").mock(["Std"])

    router = Route("tier").eq("VIP", vip).otherwise(std)
    assert router is not None
```

### Composition patterns

```python
from adk_fluent import Agent
from adk_fluent.patterns import review_loop, map_reduce


def test_review_loop_pattern():
    """Demonstrates the built-in review loop pattern."""
    writer = Agent("writer", "gemini-2.5-flash").instruct("Write.").mock(["Draft"])
    reviewer = Agent("reviewer", "gemini-2.5-flash").instruct("Review.").mock(["LGTM"])

    loop = review_loop(writer, reviewer, quality_key="review", target="LGTM", max_rounds=3)
    assert loop is not None
```

## Rules

1. **Always use `.mock()`** — cookbook examples must run without API keys in CI
2. **One concept per file** — keep examples focused on a single feature or pattern
3. **Use descriptive test function names** — they appear in test output
4. **Import from `adk_fluent`** — never from internal modules like `adk_fluent._base`
5. **Use current API** — see deprecated methods table below
6. **Keep it short** — under 100 lines, ideally under 50
7. **Include docstrings** — module docstring with title, test docstring with description
8. **Use `gemini-2.5-flash`** — as the default model in examples
9. **No bare assertions** — always assert something meaningful about the result

## Deprecated methods (never use in cookbooks)

| Deprecated | Use instead |
|-----------|-------------|
| `.save_as()` | `.writes()` |
| `.delegate()` | `.agent_tool()` |
| `.guardrail()` | `.guard()` |
| `.retry_if()` | `.loop_while()` |
| `.inject_context()` | `.prepend()` |
| `.output_schema()` | `.returns()` |
| `.history()` / `.include_history()` | `.context()` |
| `.output_key()` / `.outputs()` | `.writes()` |

## Anti-patterns to avoid

- **Don't test the mock** — test that the builder wires things correctly, not the mock response
- **Don't import from internals** — `from adk_fluent._base import ...` will break
- **Don't call `.build()` on sub-builders** — inside Pipeline/FanOut/Loop, sub-builders are auto-built
- **Don't use LLM routing when Route works** — use deterministic `Route()` for rule-based decisions
- **Don't create unnecessary abstractions** — three similar lines > premature helper function
- **Don't put retry logic in tools** — use `M.retry()` middleware instead

## Step 3: Verify it runs

```bash
uv run pytest examples/cookbook/NN_descriptive_name.py -v
```

## Step 4: Update the cookbook index

If a cookbook index or README exists in `examples/`, update it with the new entry.

## Available features to demonstrate

- Agent basics: `.instruct()`, `.model()`, `.describe()`, `.static()`
- Data flow: `.writes()`, `.reads()`, `.returns()`, `.accepts()`, `.produces()`, `.consumes()`
- Operators: `>>` (sequential), `|` (parallel), `*` (loop), `//` (fallback), `@` (structured output)
- Workflows: Pipeline, FanOut, Loop
- Primitives: `tap`, `gate`, `race`, `map_over`, `dispatch`, `join`, `until`, `expect`
- Namespaces: S (state), C (context), P (prompt), A (artifacts), M (middleware), T (tools), E (eval), G (guards)
- Patterns: `review_loop`, `map_reduce`, `cascade`, `fan_out_merge`, `chain`, `conditional`, `supervised`
- Routing: `Route().eq()`, `.contains()`, `.gt()`, `.when()`, `.otherwise()`
- Testing: `.mock()`, `.test()`, `.eval()`, `.eval_suite()`
- Introspection: `.explain()`, `.diagnose()`, `.doctor()`, `.data_flow()`, `.llm_anatomy()`
- Transfer: `.isolate()`, `.stay()`, `.no_peers()`
- Flow control: `.loop_until()`, `.loop_while()`, `.proceed_if()`, `.timeout()`
- Memory: `.memory()`, `.memory_auto_save()`
- Callbacks: `.before_agent()`, `.after_agent()`, `.before_model()`, `.after_model()`, `.guard()`
