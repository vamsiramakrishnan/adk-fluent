---
name: cheatsheet
description: >
  MUST READ before writing or modifying adk-fluent agent code.
  adk-fluent API quick reference — builder methods, operators, namespaces,
  patterns, and common idioms. Includes mappings from native ADK to fluent API.
  Do NOT use for creating new projects (use scaffold-project).
allowed-tools: Bash, Read, Glob, Grep
---

# adk-fluent Cheatsheet

> **Quick reference for writing agents with adk-fluent.**
> For developing the library itself, use `/develop-feature`.
> For creating a new project, use `/scaffold-project`.

## Reference Files

| File | Contents |
|------|----------|
| [`../_shared/references/api-surface.md`](../_shared/references/api-surface.md) | Complete builder method inventory with signatures |
| [`../_shared/references/namespace-methods.md`](../_shared/references/namespace-methods.md) | S, C, P, A, M, T, E, G namespace functions |
| [`../_shared/references/patterns-and-primitives.md`](../_shared/references/patterns-and-primitives.md) | Composition patterns and expression operators |
| [`../_shared/references/deprecated-methods.md`](../_shared/references/deprecated-methods.md) | Deprecated method → replacement mapping |

Read `../_shared/references/api-surface.md` for the full method reference.

---

## Install & Import

```bash
pip install adk-fluent
```

```python
from adk_fluent import Agent, Pipeline, FanOut, Loop, Route
from adk_fluent import S, C, P, A, M, T, E, G
```

Never import from internal modules (`adk_fluent._base`, `adk_fluent.agent`).

---

## Native ADK → adk-fluent Mapping

| Native ADK | adk-fluent equivalent |
|------------|----------------------|
| `LlmAgent(name=, model=, instruction=)` | `Agent("name", "model").instruct("...")` |
| `SequentialAgent(name=, sub_agents=[a, b])` | `Pipeline("name").step(a).step(b)` or `a >> b` |
| `ParallelAgent(name=, sub_agents=[a, b])` | `FanOut("name").branch(a).branch(b)` or `a \| b` |
| `LoopAgent(name=, sub_agents=[a, b], max_iterations=3)` | `Loop("name").step(a).step(b).max_iterations(3)` or `(a >> b) * 3` |
| `AgentTool(agent=child)` | `.agent_tool(child)` |
| `sub_agents=[child]` | `.sub_agent(child)` |
| `output_key="key"` | `.writes("key")` |
| `include_contents="none"` | `.reads("key1", "key2")` or `.context(C.none())` |
| `generate_content_config=...` | `.generate_content_config()` |
| `before_agent_callback=fn` | `.before_agent(fn)` |
| `after_model_callback=fn` | `.after_model(fn)` |

---

## Agent Builder — Quick Reference

### Create and configure

```python
agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .describe("Handles general queries")        # metadata, not sent to LLM
    .tool(search_fn)
    .build()
)
```

### Data flow (5 concerns)

```python
agent = (
    Agent("processor", "gemini-2.5-flash")
    .reads("input_data")                        # CONTEXT: inject state keys
    .context(C.window(n=5))                     # CONTEXT: conversation history
    .accepts(InputSchema)                       # INPUT: validate tool invocation
    .returns(OutputSchema)                      # OUTPUT: constrain LLM response
    .writes("result")                           # STORAGE: save response to state
    .produces(ProducesSchema)                   # CONTRACT: document writes (no runtime effect)
    .consumes(ConsumesSchema)                   # CONTRACT: document reads (no runtime effect)
)
```

### Tools

```python
agent.tool(search_fn)                           # Single tool
agent.tools([fn1, fn2])                         # Replace all tools
agent.tools(T.fn(fn1) | T.fn(fn2))             # Composed tools
agent.agent_tool(child_agent)                   # Agent as tool (parent stays in control)
agent.inject(db=my_db_client)                   # Hidden from LLM schema
```

### Transfer control (multi-agent routing)

```python
agent.sub_agent(specialist)                     # LLM decides when to transfer
agent.sub_agent(specialist.isolate())           # Specialist can't escape
agent.stay()                                    # Don't return to parent
agent.no_peers()                                # Don't transfer to siblings
```

### Callbacks and guards

```python
agent.before_agent(fn).after_agent(fn)          # Agent lifecycle
agent.before_model(fn).after_model(fn)          # LLM lifecycle
agent.before_tool(fn).after_tool(fn)            # Tool lifecycle
agent.guard(G.pii() | G.length(max=500))        # Output validation
```

### Flow control

```python
agent.loop_until(pred, max=10)                  # Loop while predicate is false
agent.loop_while(pred, max=3)                   # Loop while predicate is true
agent.timeout(30)                               # Time limit
agent.dispatch(name="bg", on_complete=handler)  # Fire-and-forget
```

---

## Expression Operators

```python
pipeline = a >> b >> c                          # Sequential
fanout   = a | b | c                            # Parallel
loop     = (a >> b) * 3                         # Fixed loop
loop     = (a >> b) * until(pred, max=5)        # Conditional loop
fallback = fast // strong                       # Fallback chain
typed    = agent @ MySchema                     # Structured output
pipeline = a >> some_function >> b              # Function steps (zero LLM cost)
```

---

## Workflow Builders

### Pipeline

```python
pipeline = (
    Pipeline("flow")
    .step(Agent("a").instruct("Step 1.").writes("result"))
    .step(Agent("b").instruct("Step 2 using {result}."))
    .build()
)
```

### FanOut

```python
fanout = (
    FanOut("parallel")
    .branch(Agent("web").instruct("Search web."))
    .branch(Agent("papers").instruct("Search papers."))
    .build()
)
```

### Loop

```python
loop = (
    Loop("refine")
    .step(Agent("writer").instruct("Write."))
    .step(Agent("critic").instruct("Critique."))
    .max_iterations(3)
    .build()
)
```

### Route (deterministic routing)

```python
router = Route("tier").eq("VIP", vip_agent).otherwise(standard_agent)
```

---

## Namespace Quick Reference

| Module | Purpose | Used with |
|--------|---------|-----------|
| **S** | State transforms | `>>` operator |
| **C** | Context engineering | `.context()` |
| **P** | Prompt composition | `.instruct()` |
| **A** | Artifacts | `.artifacts()` |
| **M** | Middleware | `.middleware()` |
| **T** | Tool composition | `.tools()` |
| **E** | Evaluation | `.eval()`, `.eval_suite()` |
| **G** | Guards | `.guard()` |

### Common patterns

```python
# State: filter and rename between steps
pipeline = a >> S.pick("x", "y") >> S.rename(x="input") >> b

# Context: windowed history + state injection
agent.context(C.window(n=5) + C.from_state("config"))

# Prompt: structured composition
agent.instruct(P.role("Analyst") + P.task("Analyze data") + P.constraint("Be concise"))

# Middleware: retry + logging
pipeline.middleware(M.retry(max_attempts=3) | M.log())

# Guards: PII + length
agent.guard(G.pii() | G.length(max=500))
```

---

## Execution

```python
# One-shot (sync)
result = agent.ask("What is 2+2?")

# One-shot (async — use in Jupyter/FastAPI)
result = await agent.ask_async("What is 2+2?")

# Streaming
async for chunk in agent.stream("Tell me a story"):
    print(chunk, end="")

# Multi-turn session
async with agent.session() as chat:
    r1 = await chat.send("Hello")
    r2 = await chat.send("Follow up")

# Batch
results = agent.map(["prompt1", "prompt2"], concurrency=5)

# Testing (no API key needed)
agent.mock(["canned response"]).test("input", contains="canned")
```

---

## Composition Patterns

```python
from adk_fluent.patterns import review_loop, map_reduce, cascade, fan_out_merge

# Review loop
loop = review_loop(writer, reviewer, quality_key="review", target="LGTM")

# Map-reduce
result = map_reduce(mapper, reducer, items_key="items", result_key="summary")

# Fallback cascade
chain = cascade(fast_agent, medium_agent, strong_agent)

# Parallel + merge
merged = fan_out_merge(agent_a, agent_b, merge_key="combined")
```

---

## Common Gotchas

| Mistake | Fix |
|---------|-----|
| Calling `.build()` on sub-builders inside Pipeline/FanOut/Loop | Don't — sub-builders auto-build |
| Using `.ask()` in async context (Jupyter, FastAPI) | Use `.ask_async()` instead |
| Missing `.writes()` upstream of `.reads()` | Every `.reads("key")` needs a matching `.writes("key")` |
| Using `.instruct()` for agent metadata | Use `.describe()` for metadata, `.instruct()` for LLM instructions |
| LLM routing when rules suffice | Use `Route()` for deterministic decisions |
| Retry logic in tool functions | Use `M.retry()` middleware |
| Exposing DB clients in tool schemas | Use `.inject(db=client)` |
| Using deprecated methods | Check [`../_shared/references/deprecated-methods.md`](../_shared/references/deprecated-methods.md) |

---

## Introspection & Debugging

```python
agent.explain()          # Quick text summary
agent.llm_anatomy()      # What the LLM sees
agent.data_flow()        # Five-concern view
agent.doctor()           # Formatted diagnostic
agent.validate()         # Catch config errors early
agent.to_mermaid()       # Mermaid diagram
```
