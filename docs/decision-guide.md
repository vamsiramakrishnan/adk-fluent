# Decision Guide

This page answers the question every developer asks: **"Which pattern should I use?"**

Use it as a flowchart when you're staring at a blank file and know what you
want but not how to express it in adk-fluent.

## Choosing a Topology

```
Do you have ONE agent?
  └── Yes → Agent("name", "model").instruct("...").build()
      └── See: Getting Started

Do you have MULTIPLE agents that run in ORDER?
  └── Yes → a >> b >> c (Pipeline)
      └── See: Expression Language, Cookbook #04

Do you have MULTIPLE agents that run INDEPENDENTLY?
  └── Yes → a | b | c (FanOut)
      └── See: Expression Language, Cookbook #05

Do you need to REPEAT until a condition?
  └── Yes → (a >> b) * until(pred) (Loop)
      └── See: Expression Language, Cookbook #06

Do you need to ROUTE based on a state value?
  └── Yes → Route("key").eq("x", agent_x).otherwise(fallback)
      └── See: Patterns, Cookbook #56

Do you need a FALLBACK chain (try fast, fall back to strong)?
  └── Yes → fast_agent // strong_agent
      └── See: Expression Language

Do you need ALL of the above?
  └── Yes → Compose them: a >> (b | c) >> (d >> e) * until(f) >> g
      └── See: Hero Workflows
```

## Choosing a Context Strategy

| Situation | Use | Why |
|---|---|---|
| Agent should see NO history | `C.none()` | Classifiers, routers, utility agents that shouldn't be influenced by prior conversation |
| Agent should see only USER messages | `C.user_only()` | Prevents leaking other agents' internal reasoning |
| Agent should see specific state keys | `C.from_state("key1", "key2")` | Explicit data contracts; agent sees only what it needs |
| Agent should see recent context only | `C.window(n=5)` | Keeps token budget manageable for long conversations |
| Agent should see specific other agents | `C.from_agents("agent_a", "agent_b")` | Multi-agent workflows where you want selective visibility |
| Default ADK behavior | Don't call `.context()` | Agent sees full conversation history |

See [Context Engineering](user-guide/context-engineering.md) for composition rules (`+` for union, `|` for pipe).

## Choosing a Data Flow Strategy

| Situation | Use | Why |
|---|---|---|
| Pass data to the next agent | `.writes("key")` | Named state key, explicit contract |
| Read data from a previous agent | `.reads("key")` or `{key}` in instruction | Inject state into prompt template |
| Capture user input into state | `S.capture("message")` | Zero-cost function step before pipeline |
| Transform data between agents | `S.transform("key", fn)` or `S.compute(...)` | No LLM call, pure function |
| Merge multiple keys | `S.merge("a", "b", into="combined")` | Combine parallel outputs |
| Validate state invariants | `S.guard(pred, msg="...")` | Fail fast if preconditions are broken |
| Set defaults | `S.default(key="fallback_value")` | Ensure keys exist before reading |

See [Data Flow](user-guide/data-flow.md) and [State Transforms](user-guide/state-transforms.md).

## Choosing an Output Strategy

| Situation | Use | Why |
|---|---|---|
| Free-form text | Don't add constraints | Default LLM behavior |
| Structured JSON | `agent @ MyPydanticModel` or `.returns(Model)` | Forces JSON conforming to schema; raises on parse failure |
| Named state key | `.writes("result")` | Downstream agents read `{result}` in prompts |
| Contract annotation only | `.produces(Schema)` | No runtime effect; `check_contracts()` verifies at build time |

See [Structured Data](user-guide/structured-data.md).

## Choosing a Testing Strategy

| Situation | Use | Why |
|---|---|---|
| Quick smoke test | `.test("prompt", contains="expected")` | Inline, no test file needed |
| Deterministic tests (no API) | `.mock({"agent": "response"})` | Canned responses, no LLM calls |
| Contract verification | `check_contracts(pipeline.to_ir())` | Static analysis of data flow |
| Full harness | `AgentHarness(builder, backend=mock_backend(...))` | Async send/receive with assertions |

See [Testing](user-guide/testing.md).

## Choosing a Middleware Strategy

| Situation | Use | Why |
|---|---|---|
| Retry on transient failures | `M.retry(max_attempts=3)` | Exponential backoff, no retry logic in tools |
| Log all agent events | `M.log()` | Structured logging for observability |
| Track token usage | `M.cost()` | Budget monitoring |
| Circuit breaker | `M.circuit_breaker(max_fails=5)` | Stop calling a failing model |
| Cache responses | `M.cache(ttl=300)` | Avoid redundant LLM calls |
| Scope to specific agents | `M.scope(["agent_a"], M.retry())` | Apply middleware selectively |

See [Middleware](user-guide/middleware.md).

## Common Recipes by Goal

### "I want to classify and route"

```python
from adk_fluent import Agent, S, C
from adk_fluent._routing import Route

classifier = Agent("classifier", MODEL).instruct("Classify: a, b, or c").context(C.none()).writes("category")
pipeline = S.capture("input") >> classifier >> Route("category").eq("a", agent_a).eq("b", agent_b).otherwise(agent_c)
```

See [Cookbook: Customer Support Triage](cookbook/hero-workflows/customer-support-triage.md)

### "I want parallel search then synthesis"

```python
from adk_fluent import Agent, C

results = (
    Agent("web", MODEL).instruct("Search web.").writes("web")
    | Agent("papers", MODEL).instruct("Search papers.").writes("papers")
)
pipeline = results >> Agent("synth", MODEL).instruct("Synthesize {web} and {papers}.")
```

See [Cookbook: Deep Research](cookbook/hero-workflows/deep-research.md)

### "I want write-review-revise loop"

```python
from adk_fluent import Agent

loop = (
    Agent("writer", MODEL).instruct("Write.").writes("draft")
    >> Agent("critic", MODEL).instruct("Score 0-1.").writes("score")
).loop_until(lambda s: float(s.get("score", 0)) >= 0.8, max_iterations=3)
```

See [Patterns: review_loop](user-guide/patterns.md)

### "I want to test without API calls"

```python
from adk_fluent import Agent
from adk_fluent.testing import mock_backend, AgentHarness

harness = AgentHarness(
    Agent("helper").instruct("Help."),
    backend=mock_backend({"helper": "I can help!"})
)
response = await harness.send("Hi")
assert response.final_text == "I can help!"
```

See [Testing](user-guide/testing.md)

## Still Not Sure?

- Browse the [Cookbook by use case](generated/cookbook/recipes-by-use-case.md) -- find a recipe that matches your domain
- Read the [Framework Comparison](user-guide/comparison.md) -- see how adk-fluent compares to LangGraph and CrewAI
- Check the [Hero Workflows](cookbook/index.md) -- 7 production-grade examples with full interplay breakdowns
- Read the [Error Reference](user-guide/error-reference.md) -- if you're stuck on a specific error
