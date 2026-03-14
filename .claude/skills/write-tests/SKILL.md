---
name: write-tests
description: Write tests for adk-fluent features. Use when adding test coverage for new or existing features, fixing test failures, or following TDD practices.
allowed-tools: Bash, Read, Glob, Grep, Write, Edit
---

# Write Tests for adk-fluent

Guide for writing effective tests for builders, operators, namespaces, and patterns.

## Test organization

- `tests/manual/` — Hand-written tests (**write here**)
- `tests/generated/` — Auto-generated scaffolds (NEVER edit)
- `tests/golden/` — Snapshot tests
- `examples/cookbook/` — Runnable examples (also serve as tests)

## Test structure

```python
"""Tests for [feature name]."""

import pytest
from adk_fluent import Agent, Pipeline, S, C, P


class TestFeatureName:

    def test_basic_usage(self):
        agent = Agent("test", "gemini-2.5-flash").instruct("Do something.").mock(["ok"])
        result = agent.ask("input")
        assert result is not None

    def test_with_pipeline(self):
        a = Agent("a").writes("x").mock(["A"])
        b = Agent("b").reads("x").mock(["B"])
        pipeline = a >> b
        assert pipeline.build() is not None

    def test_validates(self):
        agent = Agent("test").instruct("...")
        assert not agent.validate()

    def test_immutability(self):
        a = Agent("a").instruct("Original.")
        b = Agent("b")
        pipeline = a >> b
        assert a is not pipeline  # Original unchanged
```

## Key patterns

### Mock-based testing (required for CI)

```python
def test_agent_with_mock():
    agent = Agent("test").instruct("Summarize.").mock(["Summary here."])
    result = agent.ask("Some text")
    assert "Summary" in result
```

### Contract checking

```python
from adk_fluent import check_contracts

def test_pipeline_contracts():
    pipeline = Agent("a").writes("x") >> Agent("b").reads("x")
    assert not check_contracts(pipeline)

def test_detects_missing_writes():
    pipeline = Agent("a") >> Agent("b").reads("x")  # Missing .writes("x")
    assert len(check_contracts(pipeline)) > 0
```

### Namespace testing

```python
def test_state_transforms():
    t = S.pick("a", "b") >> S.rename(a="x")
    assert t is not None

def test_context_specs():
    spec = C.window(n=5) + C.from_state("key")
    assert spec is not None

def test_prompt_composition():
    prompt = P.role("Analyst") + P.task("Analyze") + P.constraint("Be concise")
    agent = Agent("test").instruct(prompt)
    assert agent is not None
```

### Pattern testing

```python
from adk_fluent.patterns import review_loop, cascade

def test_review_loop():
    loop = review_loop(Agent("w").mock(["Draft"]), Agent("r").mock(["LGTM"]),
                       quality_key="review", target="LGTM")
    assert loop is not None
```

## What to test vs not

### DO test
- Builder method stores the right config
- Operators produce correct topology
- Data flow contracts are satisfied
- Edge cases: empty input, None values, missing keys
- Immutability after operator use
- Validation catches bad config

### DON'T test
- Mock response content (you're testing your own mock)
- ADK internals (that's google-adk's job)
- Generated code behavior (covered by generated scaffolds)
- Exact LLM output format (too brittle)

## Running tests

```bash
uv run pytest tests/ -v --tb=short           # All tests
uv run pytest tests/manual/test_X.py -v      # Specific file
uv run pytest tests/ -x -q --tb=short        # Stop on first failure
uv run pytest tests/manual/ -v               # Manual tests only
```

## Naming conventions

- File: `test_feature_name.py`
- Class: `TestFeatureName`
- Function: `test_what_it_verifies` (not `test_feature_works`)

## References

For deprecated methods to check for in tests, read
[`../_shared/references/deprecated-methods.md`](../_shared/references/deprecated-methods.md).

For the complete namespace method inventory, read
[`../_shared/references/namespace-methods.md`](../_shared/references/namespace-methods.md).
