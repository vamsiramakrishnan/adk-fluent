# Missing Verbs & Idioms: The Next DX Frontier

> **Status**: Research / RFC
> **Date**: 2026-03-29
> **Branch**: `claude/skill-based-agents-research-NSzDc`

---

## The Thesis

adk-fluent's operators (`>>`, `|`, `*`, `//`, `@`) eliminated 60-80% of boilerplate.
But builders still force you to think in **infrastructure verbs** (`.writes()`,
`.context()`, `.before_model()`) instead of **intent verbs** (`.refine()`,
`.sample()`, `.escalate()`). The next 10x comes from verbs that express
what the agent *should do*, not how the plumbing works.

---

## 1. Self-Improvement Verbs

### `.refine()` — Critique-and-improve as a single verb

**Today** (7 lines, two agents, manual wiring):

```python
writer = Agent("writer").instruct("Write about {topic}.").writes("draft")
critic = Agent("critic").instruct("Rate this draft 1-10: {draft}").reads("draft").writes("score")
pipeline = (writer >> critic) * until(lambda s: int(s.get("score", 0)) >= 8, max=3)
```

**With `.refine()`** (1 line):

```python
writer = (
    Agent("writer")
    .instruct("Write about {topic}.")
    .refine("Rate 1-10. Suggest improvements.", target=8, max_rounds=3)
)
```

`.refine(critique_prompt, *, target, max_rounds, model=None)` internally creates
a critic agent, wires `writes`/`reads`, and wraps in a `review_loop`. The
critique prompt receives the agent's output as `{draft}`. `target` is compared
against a numeric score extracted from the critic's response.

### `.sample()` — Best-of-N generation

**Today** (manual race + scoring):

```python
candidates = Agent("a").instruct("Write a poem.") | Agent("b").instruct("Write a poem.") | Agent("c").instruct("Write a poem.")
scorer = Agent("judge").instruct("Pick the best poem from {results}.")
pipeline = candidates >> scorer
```

**With `.sample()`** (1 line):

```python
poet = Agent("poet").instruct("Write a poem about {topic}.").sample(3, select="best")
```

`.sample(n, *, select="best", judge_prompt=None, model=None)` runs the agent
`n` times in parallel (FanOut of clones), then selects using a judge agent.
`select` can be `"best"`, `"shortest"`, `"longest"`, or a custom `Callable`.

### `.reflect()` — Chain-of-thought with hidden scratchpad

**Today** (manual state key + context wiring):

```python
agent = (
    Agent("analyst")
    .instruct("Think step by step. Write your reasoning, then your answer.")
    .writes("_reasoning")
)
```

**With `.reflect()`**:

```python
agent = (
    Agent("analyst")
    .instruct("Analyze this data.")
    .reflect()  # Adds "Think step by step" + hides reasoning from downstream
)
```

`.reflect(scratchpad_key="_thinking")` prepends chain-of-thought instructions
and stores reasoning in a private state key. Only the final answer propagates
to downstream agents via `.writes()`.

---

## 2. Resilience Verbs

### `.resilient()` — Retry + fallback + circuit breaker in one

**Today** (3 separate middleware calls):

```python
agent = (
    Agent("api_caller", "gemini-2.5-flash")
    .instruct("Call the API.")
    .middleware(M.retry(max_attempts=3) | M.fallback_model("gemini-2.5-pro") | M.circuit_breaker(threshold=5))
)
```

**With `.resilient()`**:

```python
agent = (
    Agent("api_caller", "gemini-2.5-flash")
    .instruct("Call the API.")
    .resilient(retries=3, fallback="gemini-2.5-pro", circuit_breaker=5)
)
```

### `.escalate()` — Tiered quality gates

**Today** (manual routing logic):

```python
def quality_gate(state):
    score = float(state.get("confidence", 0))
    if score > 0.9: return "auto_approve"
    if score > 0.6: return "human_review"
    return "reject"

pipeline = agent >> S.compute(tier=quality_gate) >> Route("tier")
    .eq("auto_approve", publisher)
    .eq("human_review", human_reviewer >> publisher)
    .eq("reject", revision_agent)
```

**With `.escalate()`**:

```python
agent = (
    Agent("writer")
    .instruct("Write the report.")
    .escalate(
        auto_approve=lambda s: float(s["confidence"]) > 0.9,
        review=lambda s: float(s["confidence"]) > 0.6,
        reject=revision_agent,
    )
)
```

---

## 3. Data Flow Verbs

### `.pipe()` — Implicit writes/reads chaining

**Today** (explicit key wiring on every agent):

```python
researcher = Agent("researcher").instruct("Research {topic}.").writes("findings")
writer = Agent("writer").instruct("Write about {findings}.").reads("findings").writes("draft")
editor = Agent("editor").instruct("Edit {draft}.").reads("draft")
pipeline = researcher >> writer >> editor
```

**With `.pipe()`** (zero key management):

```python
pipeline = (
    Agent("researcher").instruct("Research {topic}.")
    >> Agent("writer").instruct("Write about {previous}.")
    >> Agent("editor").instruct("Edit {previous}.")
).pipe()
```

`.pipe()` on a Pipeline auto-wires `.writes()` and `.reads()` using a
convention: each agent writes to `_{name}_output`, and `{previous}` resolves
to the prior agent's output key. No manual key juggling.

### `.collect()` — Gather parallel results into a structured merge

**Today** (manual merge key + S.merge):

```python
pipeline = (
    (web_search | paper_search | news_search)
    >> S.merge("web_results", "paper_results", "news_results", into="all_sources")
    >> synthesizer.reads("all_sources")
)
```

**With `.collect()`**:

```python
pipeline = (
    (web_search | paper_search | news_search).collect("sources")
    >> synthesizer  # Automatically sees {sources}
)
```

`.collect(key)` on a FanOut auto-merges all branch outputs into a single
state key as a structured dict.

### `.yields()` — Streaming output with side-effects

```python
agent = (
    Agent("narrator")
    .instruct("Narrate the story.")
    .yields(on_chunk=update_ui, on_complete=save_to_db)
)
```

`.yields()` hooks into streaming to execute side-effects per chunk without
blocking the stream.

---

## 4. Composition Verbs

### `.branch()` — Inline conditional without Route

**Today** (full Route object):

```python
pipeline = classifier >> Route("category").eq("A", agent_a).eq("B", agent_b).otherwise(agent_c)
```

**With `.branch()`**:

```python
pipeline = classifier.branch(
    A=agent_a,
    B=agent_b,
    _otherwise=agent_c,
)
```

`.branch(**routes, _otherwise=None, key=None)` is sugar for Route when
the routing key is the agent's `.writes()` key.

### `.fan()` — Named parallel with auto-merge

```python
results = agent.fan(
    web=Agent("web").instruct("Search web."),
    papers=Agent("papers").instruct("Search papers."),
    news=Agent("news").instruct("Search news."),
)
# results.writes() → {"web": ..., "papers": ..., "news": ...}
```

`.fan(**agents)` creates a FanOut where each branch writes to a named key
that matches the kwarg name.

### `debate()` — Adversarial refinement pattern

```python
from adk_fluent import debate

conclusion = debate(
    pro=Agent("advocate").instruct("Argue FOR {proposition}."),
    con=Agent("critic").instruct("Argue AGAINST {proposition}."),
    judge=Agent("judge").instruct("Evaluate both arguments. Decide."),
    rounds=3,
)
```

New pattern: `pro` and `con` alternate for `rounds`, each seeing the other's
response. `judge` renders final verdict.

### `ensemble()` — Best-of-N agents with voting

```python
from adk_fluent import ensemble

result = ensemble(
    Agent("fast", "gemini-2.5-flash").instruct("Classify."),
    Agent("strong", "gemini-2.5-pro").instruct("Classify."),
    Agent("local", "llama-3").instruct("Classify."),
    vote="majority",  # or "unanimous", "weighted", custom fn
)
```

### `saga()` — Transactional multi-step with compensation

```python
from adk_fluent import saga

order = saga(
    steps=[
        ("reserve_inventory", reserve_agent, undo_reserve_agent),
        ("charge_payment", payment_agent, refund_agent),
        ("ship_order", shipping_agent, cancel_shipment_agent),
    ],
)
# If step 3 fails, runs cancel_shipment → refund → undo_reserve
```

---

## 5. Observation Verbs

### `.trace()` — First-class observability

**Today**:

```python
agent.middleware(M.log() | M.cost() | M.latency() | M.trace())
```

**With `.trace()`**:

```python
agent.trace()  # Equivalent to above — everything on
agent.trace("cost", "latency")  # Only specific concerns
agent.trace(export="otlp://localhost:4317")  # With OTLP export
```

### `.budget()` — Cost and token limits

```python
agent = (
    Agent("researcher")
    .instruct("Research thoroughly.")
    .budget(max_cost=0.50, max_tokens=100_000)
)
# Stops execution if budget exceeded, with clear error
```

### `.explain_run()` — Post-execution introspection

```python
result, trace = await agent.ask_async("Research quantum computing", trace=True)
trace.cost          # $0.12
trace.latency       # 3.4s
trace.tokens        # {"input": 1200, "output": 800}
trace.tool_calls    # [{"name": "search", "args": {...}, "result": "..."}]
trace.agent_path    # ["researcher", "fact_checker", "synthesizer"]
```

---

## 6. Persona Verbs

### `.persona()` — Composable personality traits

**Today**:

```python
agent = Agent("advisor").instruct(
    P.role("You are a senior financial advisor with 20 years of experience.")
    + P.constraint("Be conservative", "Cite regulations", "Use formal tone")
)
```

**With `.persona()`**:

```python
agent = (
    Agent("advisor")
    .persona("senior financial advisor", years=20)
    .tone("formal", "conservative")
    .instruct("Advise on the portfolio allocation.")
)
```

`.persona(role, **traits)` generates structured role prompts.
`.tone(*adjectives)` adds style constraints. These compose with `P.*` —
they're syntactic sugar, not a new system.

---

## 7. Testing Verbs

### `.snapshot()` — Golden-file testing

```python
agent.snapshot("tests/golden/research_output.txt", prompt="Research quantum computing")
# First run: saves output as golden file
# Subsequent runs: asserts output matches (within threshold)
```

### `.benchmark()` — Performance regression testing

```python
agent.benchmark(
    prompts=["prompt1", "prompt2", "prompt3"],
    metrics=["latency", "cost", "quality"],
    baseline="benchmarks/v1.json",
)
# Compares against baseline, fails if regression > threshold
```

### `.fuzz()` — Adversarial input testing

```python
agent.fuzz(
    seed="Research {topic}",
    mutations=100,  # Generate 100 adversarial variants
    expect_no=["error", "I cannot", "undefined"],
)
```

---

## 8. The Aesthetic Vision: What Beautiful Code Looks Like

### Before (infrastructure verbs):

```python
researcher = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research {topic} using web search.")
    .tool(search_web)
    .writes("findings")
    .context(C.none())
)
fact_checker = (
    Agent("fact_checker", "gemini-2.5-flash")
    .instruct("Verify claims in {findings}. Rate accuracy 1-10.")
    .reads("findings")
    .writes("verified")
    .context(C.from_state("findings"))
)
writer = (
    Agent("writer", "gemini-2.5-pro")
    .instruct("Write a report from {verified}. Include citations.")
    .reads("verified")
    .returns(ResearchReport)
)
critic = (
    Agent("critic", "gemini-2.5-flash")
    .instruct("Rate the report quality 1-10: {report}")
    .reads("report")
    .writes("quality")
)
pipeline = (researcher >> fact_checker >> writer >> critic) * until(
    lambda s: int(s.get("quality", 0)) >= 8, max=3
)
pipeline = pipeline.middleware(M.retry(3) | M.log() | M.cost())
```

### After (intent verbs):

```python
pipeline = (
    Agent("researcher", "gemini-2.5-flash")
        .instruct("Research {topic}.")
        .tool(search_web)
    >> Agent("fact_checker", "gemini-2.5-flash")
        .instruct("Verify claims. Rate accuracy 1-10.")
    >> Agent("writer", "gemini-2.5-pro")
        .instruct("Write report with citations.")
        .returns(ResearchReport)
).pipe().refine("Rate quality 1-10.", target=8, max_rounds=3).trace()
```

**What changed:**
- `.pipe()` eliminated 4x `.writes()` + `.reads()` + `.context()`
- `.refine()` eliminated the critic agent + loop wiring
- `.trace()` replaced the middleware composition

---

## 9. Implementation Priority

### Tier 1: High impact, low effort (builder methods)

| Verb | Lines saved | Complexity |
|------|------------|------------|
| `.pipe()` | 2-3 per agent | Medium — auto-wire writes/reads |
| `.refine()` | 5-8 per loop | Medium — wraps review_loop |
| `.trace()` | 1-3 per agent | Low — sugar for middleware |
| `.budget()` | 2-4 per agent | Low — wraps G.budget + M.cost |
| `.resilient()` | 3-5 per agent | Low — composes existing middleware |
| `.branch()` | 2-3 per route | Low — sugar for Route |

### Tier 2: Medium impact, medium effort (new patterns)

| Pattern | What it replaces | Complexity |
|---------|-----------------|------------|
| `debate()` | Manual adversarial loop | Medium |
| `ensemble()` | Manual race + judge | Medium |
| `.sample()` | Manual FanOut of clones | Medium |
| `.collect()` | S.merge after FanOut | Low |
| `.fan()` | FanOut + manual writes | Low |
| `.escalate()` | Route + quality predicates | Medium |

### Tier 3: High impact, high effort (new capabilities)

| Capability | What's new | Complexity |
|------------|-----------|------------|
| `saga()` | Compensation/rollback | High |
| `.reflect()` | Hidden scratchpad | Medium |
| `.snapshot()` | Golden-file testing | Medium |
| `.benchmark()` | Performance regression | High |
| `.fuzz()` | Adversarial testing | High |
| `.explain_run()` | Post-execution trace | High |

---

## 10. Design Principles

1. **Intent over infrastructure** — verbs should express WHAT, not HOW
2. **Compose, don't replace** — new verbs build on existing primitives
3. **Progressive disclosure** — simple usage is one line, full control via kwargs
4. **Zero magic** — `.pipe()` is sugar, not invisible wiring. `.explain()` shows what it did
5. **Operator-first** — if it can be an operator, make it one. Verbs are for things operators can't express
6. **Aesthetic gravity** — beautiful code attracts. If the fluent form isn't prettier than the manual form, don't add it
