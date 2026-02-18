# ADK Samples Port — Design Document

**Date:** 2026-02-17
**Goal:** Port 6 complex multi-agent ADK samples to the fluent API; create side-by-side comparison docs demonstrating advantages.

---

## Samples to Port

| # | Sample | ADK Pattern | Fluent API Highlights | Complexity |
|---|--------|-------------|----------------------|------------|
| 1 | LLM Auditor | `SequentialAgent` + 2 sub-agents + `after_model_callback` | `>>` operator, `.after_model()` | Low |
| 2 | Financial Advisor | `LlmAgent` + 4 `AgentTool` sub-agents + `output_key` | `.delegate()`, `.outputs()`, `.tool(google_search)` | Medium |
| 3 | Short Movie | 4 sequential sub-agents + Imagen/Veo tools + `output_key` | `>>` chain, `.outputs()`, custom tools | Medium |
| 4 | Deep Search | `SequentialAgent` + `LoopAgent` + custom `BaseAgent` + Pydantic output + callbacks | `>>`, `* until()`, `@` typed output, nested `Pipeline` | High |
| 5 | Brand Search | Router + `sub_agents` + BigQuery tool + Selenium tools | `.delegate()`, nested agents, custom tools | High |
| 6 | Travel Concierge | 6 sub-agent groups + `AgentTool` + callbacks + JSON state | Massive boilerplate reduction, `FanOut`, presets | High |

---

## Deliverables Per Sample

### 1. Example Code (`examples/<sample>/`)

```
examples/<sample>/
├── agent.py          # Fluent API version
├── prompt.py         # Prompts (kept separate for long prompts)
└── __init__.py       # ADK entry point
```

- Prompts stay in separate `prompt.py` files (some are 200+ lines)
- `agent.py` uses fluent API exclusively
- Must produce identical native ADK objects (same agent names, state keys, tools)
- Must be runnable with `adk web <sample>`

### 2. Documentation (`docs/user-guide/adk-samples/<sample>.md`)

Each page follows this structure:

```markdown
# <Sample Name>

Brief description of what the agent does.

## Architecture

Diagram/description of agent hierarchy and data flow.

## Native ADK (Original)

<details><summary>prompt.py (click to expand)</summary>
... long prompts ...
</details>

```python
# agent.py — Native ADK
from google.adk.agents import LlmAgent, SequentialAgent
...
```

## Fluent API

```python
# agent.py — Fluent API
from adk_fluent import Agent, Pipeline
...
```

## What Changed

Annotated callouts on specific reductions:
- "4 `AgentTool(agent=...)` wrappers → `.delegate()`"
- "Separate `__init__.py` imports → eliminated"
- etc.

## Metrics

| Metric | Native | Fluent | Reduction |
|--------|--------|--------|-----------|
| Lines of code (agent files) | X | Y | Z% |
| Number of files | X | Y | Z |
| Import statements | X | Y | Z% |
```

### 3. Index Page (`docs/user-guide/adk-samples/index.md`)

Overview page linking all 6 comparisons with a summary table.

---

## Fluent API Mapping Rules

### Agent Creation
```python
# Native
agent = LlmAgent(name="x", model="gemini-2.5-pro", instruction=PROMPT, output_key="result")

# Fluent
agent = Agent("x", "gemini-2.5-pro").instruct(PROMPT).outputs("result")
```

### Sequential Composition
```python
# Native
pipeline = SequentialAgent(name="pipe", sub_agents=[a, b, c])

# Fluent
pipeline = a >> b >> c
# or
pipeline = Pipeline("pipe").step(a).step(b).step(c)
```

### Tool-Based Delegation
```python
# Native
root = LlmAgent(name="root", tools=[AgentTool(agent=sub1), AgentTool(agent=sub2)])

# Fluent
root = Agent("root").delegate(sub1).delegate(sub2)
```

### Sub-Agent Delegation
```python
# Native
root = LlmAgent(name="root", sub_agents=[sub1, sub2])

# Fluent
root = Agent("root").sub_agents(sub1, sub2)
# Note: .sub_agents() uses dynamic field forwarding
```

### Callbacks
```python
# Native
agent = LlmAgent(name="x", after_model_callback=fn)

# Fluent
agent = Agent("x").after_model(fn)
```

### Loop with Exit Condition
```python
# Native
loop = LoopAgent(name="loop", max_iterations=5, sub_agents=[evaluator, checker, executor])

# Fluent
loop = Loop("loop").step(evaluator).step(checker).step(executor).max_iterations(5)
# or with operator:
loop = (evaluator >> checker >> executor) * 5
```

### Typed Output
```python
# Native
agent = LlmAgent(name="x", output_schema=Feedback)

# Fluent
agent = Agent("x") @ Feedback
```

---

## Decisions

1. **Prompts in separate files** — Long prompts (some 200+ lines) stay in `prompt.py`
2. **Docs use `<details>` tags** — Long prompt blocks are collapsed by default in comparisons
3. **Port order** — LLM Auditor → Financial Advisor → Short Movie → Deep Search → Brand Search → Travel Concierge
4. **Custom BaseAgent interop** — Deep Search's `EscalationChecker` stays as-is (fluent API wraps it, doesn't replace it)
5. **External tools unchanged** — Selenium, BigQuery, Imagen, Veo tools stay as regular Python functions; fluent API adds them via `.tool()`

---

## Non-Goals

- Not porting deployment scripts, eval harnesses, or test files
- Not porting frontend code (Deep Search React app, Short Movie FastAPI server)
- Not modifying the prompts themselves — prompts are copied verbatim
- Not creating new ADK features or extending the fluent API
