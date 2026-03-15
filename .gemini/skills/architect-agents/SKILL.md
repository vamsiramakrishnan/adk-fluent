---
name: architect-agents
description: Design multi-agent systems with adk-fluent. Use when the user needs help choosing between patterns, designing agent topologies, planning data flow, or structuring complex agent workflows.
allowed-tools: Bash, Read, Glob, Grep
---

# Architect Multi-Agent Systems with adk-fluent

Help the user design effective multi-agent systems using adk-fluent's patterns
and best practices.

## Step 1: Choose the right topology

| Need | Pattern | Syntax |
|------|---------|--------|
| Steps in order | Pipeline | `a >> b >> c` |
| Steps in parallel | FanOut | `a \| b \| c` |
| Iterative refinement | Loop | `(a >> b) * 3` |
| Quality-gated iteration | Review loop | `review_loop(writer, critic, target="LGTM")` |
| Best-of-N selection | Race | `race(a, b, c)` |
| Conditional execution | Gate | `a >> gate(pred) >> b` |
| Rule-based routing | Route | `Route("key").eq("val", agent).otherwise(fallback)` |
| Graceful degradation | Fallback | `fast // strong` |
| Scatter-gather | Map-reduce | `map_reduce(mapper, reducer, items_key="items")` |
| Parallel + merge | Fan-out-merge | `fan_out_merge(a, b, merge_key="combined")` |

For all available patterns and primitives with full signatures, read
[`../_shared/references/patterns-and-primitives.md`](../_shared/references/patterns-and-primitives.md).

## Step 2: Design the data flow

```python
researcher = Agent("researcher").instruct("Research {topic}.").writes("findings")
writer = Agent("writer").instruct("Write using {findings}.").reads("findings").writes("draft")
editor = Agent("editor").instruct("Edit {draft}.").reads("draft")
pipeline = researcher >> writer >> editor
```

**Rules:**
- Every `.reads("key")` must have a matching `.writes("key")` upstream
- Use `check_contracts(pipeline)` to verify automatically
- Use `S.pick()` / `S.drop()` to filter state between steps
- Use `S.rename()` when key names don't match

## Step 3: Engineer the context

| Agent role | Context spec | Why |
|-----------|-------------|-----|
| Main conversational | `C.default()` or `C.window(n=10)` | Needs history |
| Background utility | `C.none()` | No history needed |
| Needs specific data | `C.from_state("key1", "key2")` | Only relevant state |
| In a team | `C.from_agents("agent1")` | Sees teammate output |
| Token-constrained | `C.budget(max_tokens=2000)` | Within limits |

For all C/P/S namespace methods, read
[`../_shared/references/namespace-methods.md`](../_shared/references/namespace-methods.md).

## Step 4: Structure prompts

```python
agent = Agent("analyst").instruct(
    P.role("Senior data analyst.")
    + P.task("Analyze the provided data.")
    + P.constraint("Be concise", "Use bullet points")
    + P.format("Return JSON with keys: trends, confidence, summary")
)
```

Section order: role → context → task → constraint → format → example.

## Common architectures

### Research pipeline

```python
pipeline = review_loop(
    researcher >> synthesizer,
    reviewer,
    quality_key="review", target="APPROVED", max_rounds=3,
)
```

### Customer support triage

```python
classifier = Agent("classifier").instruct("Classify issue.").writes("tier")
system = classifier >> Route("tier").eq("billing", billing_agent).eq("technical", tech_agent).otherwise(general_agent)
```

### Fallback chain

```python
system = Agent("fast", "gemini-2.5-flash") // Agent("strong", "gemini-2.5-pro")
```

### Map-reduce

```python
system = map_reduce(analyzer, reducer, items_key="items", result_key="summary")
```

## Anti-patterns to avoid

1. **LLM routing when rules work** — use `Route()` for deterministic decisions
2. **Monolithic agents** — split into specialized agents in a pipeline
3. **Missing context boundaries** — use `C.none()` for utility agents
4. **Manual state threading** — use `.writes()` / `.reads()` / `S.*` transforms
5. **Retry logic in tools** — use `M.retry()` middleware
6. **Exposing infrastructure in tool schemas** — use `.inject()` for DB clients

## Visualization

```python
pipeline.to_mermaid()    # Mermaid diagram
pipeline.to_ir()         # Structured IR view
pipeline.data_flow()     # Five-concern analysis
pipeline.doctor()        # Doctor report
```
