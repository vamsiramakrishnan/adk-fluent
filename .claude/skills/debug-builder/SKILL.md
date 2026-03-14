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

# Quick text summary of all configured fields
agent.explain()

# What the LLM actually sees (instruction, context, tools)
agent.llm_anatomy()

# Five-concern data flow view (reads, writes, context, tools, callbacks)
agent.data_flow()

# Plain-text state dump
agent.inspect()
```

### Step 2: Structured diagnosis

```python
# IR tree — structured representation of the builder
agent.diagnose()

# Formatted diagnostic report (human-readable)
agent.doctor()

# Validate contracts and configuration (returns issues list)
issues = agent.validate()
```

### Step 3: Contract checking for workflows

```python
from adk_fluent import check_contracts

# Check a pipeline for data flow issues (reads without matching writes)
pipeline = Agent("a").writes("x") >> Agent("b").reads("x")
issues = check_contracts(pipeline)
for issue in issues:
    print(issue)
```

## Common issues and fixes

### Data flow problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `.reads()` key not found at runtime | Upstream agent doesn't `.writes()` that key | Add `.writes(key)` to the producing agent |
| State key empty or None | Agent didn't produce output for that key | Check `.llm_anatomy()` — is the instruction asking for the right output? |
| Pipeline step gets wrong data | `.reads()` keys don't match `.writes()` keys | Use `check_contracts(pipeline)` to find mismatches |
| State accumulates unwanted keys | No filtering between steps | Add `>> S.pick("key1", "key2") >>` between steps |

### Builder configuration problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `.build()` raises ValidationError | Pydantic validation on ADK native object | Use `.explain()` to see current config, check field types |
| Method not found on builder | Using deprecated method name | See deprecated methods table below |
| Method chaining breaks in IDE | Missing `.pyi` stub | Regenerate stubs: `just generate` |
| `.build()` returns unexpected type | Wrong builder class | Agent→LlmAgent, Pipeline→SequentialAgent, FanOut→ParallelAgent, Loop→LoopAgent |

### Operator problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `>>` produces wrong pipeline | Accidentally calling `.build()` on sub-builders | Don't call `.build()` on sub-expressions — operators auto-build |
| Operator composition gives error | Mixing built objects with builders | Use raw builders with operators, call `.build()` only on the final result |
| `*` loop doesn't stop | Predicate never returns True | Use `* until(pred, max=N)` with a max iteration guard |
| `//` fallback not triggering | First agent succeeds (even with bad output) | Fallback triggers on exceptions only — use `.guard()` for output quality |

### Context and prompt problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent ignores conversation history | No context spec or `C.none()` | Use `C.default()` or `C.window(n=5)` |
| Agent sees too much history | Default context includes everything | Use `C.window(n=3)` or `C.user_only()` |
| State keys not in prompt | `.reads()` without matching `{key}` in instruction | Use `{key}` placeholder in `.instruct()` or use `C.from_state("key")` |
| Prompt too long or unfocused | Instruction string too verbose | Use `P.role() + P.task() + P.constraint()` for structured prompts |

### Testing and mocking problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `.mock()` not working | Mock responses exhausted | Provide enough mock responses for all agent interactions |
| `.mock()` returns wrong response | Responses consumed in order | Responses are FIFO — order matters in multi-step pipelines |
| `.ask()` hangs | No mock and no API key | Always use `.mock()` in tests |
| `.test()` passes but `.ask()` fails | Mock behavior differs from real LLM | `.test()` uses mocks — verify with a real model if needed |

### Namespace module problems

| Symptom | Cause | Fix |
|---------|-------|-----|
| `S.transform()` not applying | Transform not in pipeline | Add `>> S.transform(key, fn) >>` between agents |
| `C.from_state()` empty | State key not populated yet | Ensure upstream agent `.writes()` the key before this agent runs |
| `P.role() + P.task()` concatenation wrong | Using `|` instead of `+` | Use `+` for union, `|` for pipe (transform chain) |
| `M.retry()` not retrying | Middleware not attached | Use `.middleware(M.retry())` on the agent or pipeline |
| `G.length()` not enforcing | Guard attached wrong | Use `.guard(G.length(max=100))` — guard runs as before/after model callback |

## Deprecated methods reference

| Deprecated | Current | Notes |
|-----------|---------|-------|
| `.save_as()` | `.writes()` | State key storage |
| `.delegate()` | `.agent_tool()` | Agent-as-tool wrapping |
| `.guardrail()` | `.guard()` | Input/output validation |
| `.retry_if()` | `.loop_while()` | Conditional looping |
| `.inject_context()` | `.prepend()` | Dynamic text prepend |
| `.output_schema()` | `.returns()` | Structured output |
| `.output_key()` / `.outputs()` | `.writes()` | State key storage |
| `.history()` / `.include_history()` | `.context()` | Context engineering |

## Architecture reference

When debugging, it helps to know where things live:

- **BuilderBase** (`_base.py`): All builder methods, operators, and primitives
- **Generated builders** (`agent.py`, `workflow.py`, `tool.py`, etc.): ADK field mapping
- **Namespace modules**: `_transforms.py` (S), `_context.py` (C), `_prompt.py` (P), `_artifacts.py` (A), `_middleware.py` (M), `_tools.py` (T), `_eval.py` (E), `_guards.py` (G)
- **IR tree**: `_ir.py` + `_ir_generated.py` — intermediate representation for introspection
- **Backends**: `backends/adk.py` — translates builder IR into native ADK objects
- **Patterns**: `patterns.py` — higher-order compositions (review_loop, map_reduce, etc.)
- **Testing**: `testing/` — contracts, mock backend, diagnosis, harness

## Quick copy-paste diagnostics

When helping a user debug, suggest they run this:

```python
from adk_fluent import Agent

agent = Agent("name", "gemini-2.5-flash").instruct("...")
# ... their configuration ...

# Run all diagnostics
print("=== EXPLAIN ===")
agent.explain()
print("\n=== DOCTOR ===")
agent.doctor()
print("\n=== VALIDATE ===")
for issue in agent.validate():
    print(f"  - {issue}")
print("\n=== LLM ANATOMY ===")
agent.llm_anatomy()
```
