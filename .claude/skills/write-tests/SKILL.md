---
name: write-tests
description: Write tests for adk-fluent features. Use when adding test coverage for new or existing features, fixing test failures, or following TDD practices.
allowed-tools: Bash, Read, Glob, Grep, Write, Edit
---

# Write Tests for adk-fluent

Guide for writing effective tests that cover builder behavior, operators,
namespace modules, patterns, and integration with ADK.

## Test organization

```
tests/
├── generated/         # Auto-generated test scaffolds (NEVER edit)
│   └── test_*_builder.py
├── manual/            # Hand-written tests (THIS is where you write)
│   └── test_*.py
├── golden/            # Snapshot tests for stability
└── conftest.py        # Shared fixtures
```

**Always put new tests in `tests/manual/`.**

## Test structure template

```python
"""Tests for [feature name].

Covers: [what aspects this file tests]
"""

import pytest
from adk_fluent import Agent, Pipeline, S, C, P


class TestFeatureName:
    """Group related tests in a class."""

    def test_basic_usage(self):
        """Simplest possible case."""
        agent = (
            Agent("test", "gemini-2.5-flash")
            .instruct("Do something.")
            .mock(["Expected output"])
        )
        result = agent.ask("input")
        assert "Expected" in result

    def test_with_pipeline(self):
        """Feature works inside a pipeline."""
        a = Agent("a").instruct("Step 1.").writes("x").mock(["A"])
        b = Agent("b").instruct("Use {x}.").reads("x").mock(["B"])
        pipeline = a >> b
        built = pipeline.build()
        assert built is not None

    def test_edge_case_empty(self):
        """Handles empty/missing input gracefully."""
        agent = Agent("test").instruct("Handle empty.").mock([""])
        result = agent.ask("")
        assert result is not None

    def test_validates(self):
        """Validation catches configuration errors."""
        agent = Agent("test").instruct("...")
        issues = agent.validate()
        assert not issues

    def test_immutability(self):
        """Operators don't mutate the original builder."""
        a = Agent("a").instruct("Original.")
        b = Agent("b").instruct("Other.")
        pipeline = a >> b
        # Original 'a' should be unchanged
        assert a is not pipeline


class TestFeatureNameOperators:
    """Test operator interactions."""

    def test_sequential(self):
        a = Agent("a").mock(["A"])
        b = Agent("b").mock(["B"])
        result = a >> b
        assert result is not None

    def test_parallel(self):
        a = Agent("a").mock(["A"])
        b = Agent("b").mock(["B"])
        result = a | b
        assert result is not None
```

## Testing patterns

### Mock-based testing (required for CI)

Always use `.mock()` — tests must run without API keys:

```python
def test_agent_with_mock():
    agent = (
        Agent("test", "gemini-2.5-flash")
        .instruct("Summarize the input.")
        .mock(["This is a summary of the provided text."])
    )
    result = agent.ask("Some long text here")
    assert "summary" in result.lower()
```

For multi-step pipelines, provide enough mock responses:

```python
def test_pipeline_mocks():
    a = Agent("a").instruct("Step 1.").writes("data").mock(["Step 1 result"])
    b = Agent("b").instruct("Step 2 using {data}.").reads("data").mock(["Step 2 result"])
    pipeline = a >> b
    # Each agent consumes one mock response
```

### Contract checking

Test data flow contracts for pipelines:

```python
from adk_fluent import check_contracts

def test_pipeline_contracts():
    a = Agent("a").writes("result")
    b = Agent("b").reads("result")
    pipeline = a >> b
    issues = check_contracts(pipeline)
    assert not issues, f"Contract violations: {issues}"


def test_detects_missing_writes():
    a = Agent("a")  # Missing .writes("result")
    b = Agent("b").reads("result")
    pipeline = a >> b
    issues = check_contracts(pipeline)
    assert len(issues) > 0  # Should detect the missing write
```

### Builder state testing

Test that builder methods store configuration correctly:

```python
def test_builder_stores_config():
    agent = (
        Agent("test", "gemini-2.5-flash")
        .instruct("Do something.")
        .writes("output")
    )
    # Use .explain() or internal state to verify
    agent.explain()  # Visual check
    # Or validate
    assert not agent.validate()
```

### Introspection testing

Test that diagnostic methods work:

```python
def test_explain_runs():
    agent = Agent("test").instruct("...")
    # Should not raise
    agent.explain()

def test_diagnose_runs():
    agent = Agent("test").instruct("...")
    result = agent.diagnose()
    assert result is not None

def test_doctor_runs():
    agent = Agent("test").instruct("...")
    agent.doctor()  # Should print without error

def test_to_ir():
    agent = Agent("test").instruct("...")
    ir = agent.to_ir()
    assert ir is not None
```

### Namespace module testing

Test S, C, P, M, T, G compositions:

```python
def test_state_transforms():
    t = S.pick("a", "b") >> S.rename(a="x")
    # Transforms compose via >>
    assert t is not None

def test_context_specs():
    spec = C.window(n=5) + C.from_state("key")
    # Specs compose via +
    assert spec is not None

def test_prompt_composition():
    prompt = P.role("Analyst") + P.task("Analyze data") + P.constraint("Be concise")
    agent = Agent("test").instruct(prompt)
    assert agent is not None

def test_middleware_composition():
    mw = M.retry(max_attempts=3) | M.log()
    agent = Agent("test").middleware(mw)
    assert agent is not None
```

### Pattern testing

Test higher-order composition patterns:

```python
from adk_fluent.patterns import review_loop, map_reduce, cascade

def test_review_loop():
    writer = Agent("writer").mock(["Draft"])
    reviewer = Agent("reviewer").mock(["LGTM"])
    loop = review_loop(writer, reviewer, quality_key="review", target="LGTM")
    assert loop is not None

def test_cascade():
    fast = Agent("fast").mock(["Quick answer"])
    strong = Agent("strong").mock(["Detailed answer"])
    chain = cascade(fast, strong)
    assert chain is not None
```

### Routing testing

```python
from adk_fluent import Route

def test_route_eq():
    a = Agent("a").mock(["A"])
    b = Agent("b").mock(["B"])
    router = Route("key").eq("val", a).otherwise(b)
    assert router is not None

def test_route_contains():
    a = Agent("a").mock(["A"])
    b = Agent("b").mock(["B"])
    router = Route("key").contains("sub", a).otherwise(b)
    assert router is not None
```

## What to test vs what not to test

### DO test

- Builder method stores the right config
- Operators produce the right topology (Pipeline, FanOut, Loop)
- Data flow contracts are satisfied
- Edge cases: empty input, None values, missing keys
- Immutability: operators don't mutate originals
- Deprecated methods still work (backward compat)
- Validation catches bad config
- Namespace compositions compose correctly
- Patterns produce valid builders

### DON'T test

- Mock response content (you're testing your own mock, not the agent)
- ADK internals (that's google-adk's job)
- Generated code behavior (covered by generated test scaffolds)
- External API responses (use `.mock()`)
- Exact LLM output format (too brittle)

## Running tests

```bash
# All tests
uv run pytest tests/ -v --tb=short

# Specific test file
uv run pytest tests/manual/test_my_feature.py -v

# Specific test
uv run pytest tests/manual/test_my_feature.py::TestFeature::test_basic -v

# With coverage
uv run pytest tests/ --cov=adk_fluent --cov-report=term-missing

# Fast: stop on first failure
uv run pytest tests/ -x -q --tb=short

# Only manual tests (skip generated)
uv run pytest tests/manual/ -v
```

## Naming conventions

- File: `test_feature_name.py`
- Class: `TestFeatureName`
- Function: `test_what_it_verifies` (not `test_feature_works`)
- Use descriptive names that explain the scenario:
  - `test_pipeline_with_missing_reads_key_raises`
  - `test_route_eq_matches_exact_value`
  - `test_operator_preserves_immutability`
