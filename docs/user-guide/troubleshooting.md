# Troubleshooting

:::{admonition} At a Glance
:class: tip

Error message → cause → fix lookup table. Find your error, understand why it happens, fix it.
:::

## Build Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `AttributeError: 'xxx' is not a recognized field. Did you mean: 'yyy'?` | Typo in builder method | Use the suggested method name |
| `ValueError: Agent 'x' has no model set` | Missing `.model()` or second positional arg | Add `Agent("name", "gemini-2.5-flash")` |
| `ValueError: Agent 'x' has no instruction` | Missing `.instruct()` | Add `.instruct("Your prompt here")` |
| `TypeError: build() got unexpected keyword argument` | Passing native ADK kwargs to builder | Use fluent methods instead: `.instruct()`, `.model()`, etc. |

## Data Flow Errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent reads `None` from state | Upstream agent forgot `.writes()` | Add `.writes("key")` to the upstream agent |
| Agent sees duplicate data | Three channels converging (history + state + template) | Add `.reads("key")` to suppress history on downstream agent |
| `{key}` template resolves to empty string | Key not in state when template resolves | Ensure upstream writes the key; check pipeline ordering |
| Route always takes the default branch | State key doesn't match any `.eq()` value | Check the actual state value; add `.log()` before Route |

## Context Errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent doesn't see user's original message | `.reads()` or `C.none()` suppresses history | Use `S.capture("user_msg")` before the agent, then `.reads("user_msg")` |
| Agent hallucinates from prior agents' output | Full history includes other agents' reasoning | Add `.context(C.user_only())` or `.context(C.none())` |
| Token limit exceeded | Too much history in context | Use `C.window(n=3)` or `C.budget(max_tokens=4000)` |

## Execution Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `RuntimeError: cannot run sync in async event loop` | Using `.ask()` or `.map()` in Jupyter/FastAPI | Use `.ask_async()` or `.map_async()` instead |
| `TypeError: Agent expected, got Builder` | Passing builder where ADK expects agent | Call `.build()` first |
| Infinite loop | `until()` predicate never satisfied | Always set `max=` parameter: `* until(pred, max=5)` |
| Parallel branches produce wrong results | Both branches write to same state key | Use distinct `.writes()` keys, then `S.merge()` |

## Contract Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Agent 'x' consumes key 'y' but no prior step produces it` | Missing `.produces()` or `.writes()` upstream | Add `.produces(Schema)` or `.writes("key")` |
| `Contract mismatch: expected 'x', got 'y'` | Schema field name mismatch | Align Pydantic model field names |

## Import Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ImportError: cannot import 'xxx' from adk_fluent` | Wrong import path | Always import from top-level: `from adk_fluent import Agent, S, C` |
| `ModuleNotFoundError: adk_fluent` | Not installed | `pip install adk-fluent` |
| `ImportError: A2A requires extra` | Missing optional dependency | `pip install adk-fluent[a2a]` |

---

## Debugging Techniques

### 1. Inspect builder state

```python
print(agent.explain())       # Full builder state
print(agent.data_flow())     # Five-concern snapshot
print(agent.llm_anatomy())   # What the LLM sees
```

### 2. Log state between pipeline steps

```python
pipeline = agent_a >> S.log("key1", "key2") >> agent_b
```

### 3. Visualize topology

```python
print(pipeline.to_mermaid())  # Copy-paste into mermaid.live
```

### 4. Check contracts

```python
from adk_fluent.testing import check_contracts
issues = check_contracts(pipeline.to_ir())
print(issues)  # List of data flow problems
```

### 5. Run diagnostic report

```python
print(agent.doctor())  # Formatted diagnostic with suggestions
```

---

:::{seealso}
- {doc}`error-reference` --- complete error catalog
- {doc}`testing` --- testing strategies and mock backend
- {doc}`faq` --- common questions
:::
