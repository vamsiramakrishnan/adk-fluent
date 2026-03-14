---
name: debug-builder
description: Debug an adk-fluent builder issue. Use when a builder isn't working as expected, a build fails, contracts fail, or the user needs help understanding builder state.
allowed-tools: Bash, Read, Glob, Grep
---

# Debug an adk-fluent Builder

Help the user diagnose and fix builder issues using adk-fluent's built-in introspection.

## Diagnostic workflow

Follow this order: inspect → diagnose → fix.

### Step 1: Inspect the builder state

```python
agent = Agent("name", "gemini-2.5-flash").instruct("...")

agent.explain()       # Quick text summary of all configured fields
agent.llm_anatomy()   # What the LLM actually sees
agent.data_flow()     # Five-concern data flow view
agent.inspect()       # Plain-text state dump
```

### Step 2: Structured diagnosis

```python
agent.diagnose()      # IR tree — structured representation
agent.doctor()        # Formatted diagnostic report
issues = agent.validate()  # Validate contracts and configuration
```

### Step 3: Contract checking for workflows

```python
from adk_fluent import check_contracts

pipeline = Agent("a").writes("x") >> Agent("b").reads("x")
issues = check_contracts(pipeline)
```

## Common issues and fixes

### Data flow problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `.reads()` key not found | Upstream doesn't `.writes()` that key | Add `.writes(key)` upstream |
| State key empty | Agent didn't produce output | Check `.llm_anatomy()` |
| Pipeline step gets wrong data | Keys don't match | Use `check_contracts(pipeline)` |
| Unwanted state accumulation | No filtering | Add `>> S.pick("key1", "key2") >>` |

### Builder configuration problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `.build()` raises ValidationError | Pydantic validation failed | Use `.explain()` to see config |
| Method not found | Using deprecated name | See deprecated methods reference below |
| `.build()` returns unexpected type | Wrong builder | Agent→LlmAgent, Pipeline→SequentialAgent |

### Operator problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `>>` produces wrong pipeline | Calling `.build()` on sub-builders | Don't `.build()` sub-expressions |
| `*` loop doesn't stop | Predicate never True | Use `* until(pred, max=N)` |
| `//` fallback not triggering | First agent succeeds | Fallback triggers on exceptions only |

### Context and prompt problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent ignores history | No context spec | Use `C.default()` or `C.window(n=5)` |
| State keys not in prompt | Missing placeholder | Use `{key}` in `.instruct()` |

### Testing and mocking problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `.mock()` not working | Responses exhausted | Provide enough mock responses |
| `.ask()` hangs | No mock and no API key | Always use `.mock()` in tests |

## References

For the deprecated methods mapping table, read
[`../_shared/references/deprecated-methods.md`](../_shared/references/deprecated-methods.md).

For the builder inventory (what builders exist and their fields), read
[`../_shared/references/builder-inventory.md`](../_shared/references/builder-inventory.md)
or run `uv run .claude/skills/_shared/scripts/list-builders.py`.

For the architecture reference (generated vs hand-written files), read
[`../_shared/references/generated-files.md`](../_shared/references/generated-files.md).

## Quick copy-paste diagnostics

```python
from adk_fluent import Agent

agent = Agent("name", "gemini-2.5-flash").instruct("...")
# ... user's configuration ...

print("=== EXPLAIN ===")
agent.explain()
print("\n=== DOCTOR ===")
agent.doctor()
print("\n=== VALIDATE ===")
for issue in agent.validate():
    print(f"  - {issue}")
```
