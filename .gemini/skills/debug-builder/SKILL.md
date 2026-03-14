---
name: debug-builder
description: Debug an adk-fluent builder issue. Use when a builder isn't working as expected, a build fails, contracts fail, or the user needs help understanding builder state.
allowed-tools: Bash, Read, Glob, Grep
---

# Debug an adk-fluent Builder

Help the user diagnose and fix builder issues.

## Diagnostic tools

adk-fluent has built-in introspection. Use these methods on any builder:

### Quick diagnosis

```python
agent = Agent("name", "gemini-2.5-flash").instruct("...")

# See all configured fields
agent.explain()

# Structured diagnosis (IR tree)
agent.diagnose()

# Formatted diagnostic report
agent.doctor()

# What the LLM actually sees
agent.llm_anatomy()

# Five-concern data flow view
agent.data_flow()

# Validate contracts and configuration
agent.validate()
```

### Contract checking

```python
from adk_fluent import check_contracts

# Check a pipeline for data flow issues
pipeline = Agent("a").writes("x") >> Agent("b").reads("x")
issues = check_contracts(pipeline)
```

### Common issues and fixes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `.reads()` key not found at runtime | Upstream agent doesn't `.writes()` that key | Add `.writes(key)` to the producing agent |
| Method chaining breaks in IDE | Missing `.pyi` stub or method returns wrong type | Regenerate stubs: `python scripts/generator.py seeds/seed.toml manifest.json --stubs-only` |
| `.build()` raises ValidationError | Pydantic validation on ADK native object | Check field types match ADK expectations, use `.explain()` to see current config |
| Operator `>>` produces wrong pipeline | Sub-expression reuse without copy | Operators are immutable (copy-on-write) — check you're not mutating shared refs |
| Context not reaching downstream agent | Missing `.context()` or wrong C spec | Use `.llm_anatomy()` to see what the LLM actually receives |
| Agent not responding as expected | System prompt issue | Use `.llm_anatomy()` to inspect the full prompt sent to the LLM |
| `.mock()` not working | Mock responses exhausted or wrong format | `.mock()` takes a list of strings; ensure enough responses for all interactions |

### Architecture reference

- **Hand-written core**: `_base.py` (BuilderBase with all operators and methods)
- **Generated builders**: `agent.py`, `workflow.py`, `tool.py`, etc.
- **Namespace modules**: `_transforms.py` (S), `_context.py` (C), `_prompt.py` (P), `_artifacts.py` (A), `_middleware.py` (M), `_tools.py` (T), `_eval.py` (E), `_guards.py` (G)
- **IR tree**: `_ir.py` + `_ir_generated.py`
- **Testing utilities**: `testing/` directory
