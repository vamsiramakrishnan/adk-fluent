---
name: architect-agents
description: Design multi-agent systems with adk-fluent. Use when the user needs help choosing between patterns, designing agent topologies, planning data flow, or structuring complex agent workflows.
allowed-tools: Bash, Read, Glob, Grep
---

# Architect Multi-Agent Systems with adk-fluent

Help the user design effective multi-agent systems using adk-fluent's patterns,
operators, and best practices.

## Decision framework

### Step 1: Choose the right topology

| Need | Pattern | adk-fluent syntax |
|------|---------|-------------------|
| Steps that must run in order | Pipeline (sequential) | `a >> b >> c` or `Pipeline("p").step(a).step(b)` |
| Steps that can run simultaneously | FanOut (parallel) | `a \| b \| c` or `FanOut("f").branch(a).branch(b)` |
| Iterative refinement | Loop | `(a >> b) * 3` or `Loop("l").step(a).step(b).max_iterations(3)` |
| Quality-gated iteration | Review loop | `review_loop(writer, critic, target="LGTM")` |
| Best-of-N selection | Race | `race(a, b, c)` |
| Conditional execution | Gate | `a >> gate(pred) >> b` |
| Rule-based routing | Route | `Route("key").eq("val", agent).otherwise(fallback)` |
| Graceful degradation | Fallback | `fast_model // strong_model` |
| Scatter-gather | Map-reduce | `map_reduce(mapper, reducer, items_key="items")` |
| Parallel + merge | Fan-out-merge | `fan_out_merge(a, b, merge_key="combined")` |
| Supervised execution | Supervised | `supervised(worker, supervisor)` |

### Step 2: Design the data flow

Use `.writes()` and `.reads()` to connect agents through shared state:

```python
# Good: explicit data flow
researcher = Agent("researcher").instruct("Research {topic}.").writes("findings")
writer = Agent("writer").instruct("Write using {findings}.").reads("findings").writes("draft")
editor = Agent("editor").instruct("Edit {draft}.").reads("draft")

pipeline = researcher >> writer >> editor
```

**Data flow rules:**
- Every `.reads("key")` must have a matching `.writes("key")` upstream
- Use `check_contracts(pipeline)` to verify data flow automatically
- Use `S.pick()` / `S.drop()` to control what flows between steps
- Use `S.rename()` when key names don't match between agents

### Step 3: Engineer the context

Each agent should see only what it needs:

| Agent role | Context spec | Why |
|-----------|-------------|-----|
| Main conversational agent | `C.default()` or `C.window(n=10)` | Needs history |
| Background utility agent | `C.none()` | No history needed |
| Agent that needs specific data | `C.from_state("key1", "key2")` | Only relevant state |
| Agent in a team | `C.from_agents("agent1", "agent2")` | Sees teammate output |
| Token-constrained agent | `C.budget(max_tokens=2000)` | Within limits |
| Privacy-sensitive agent | `C.redact("email", "phone")` | Scrub PII |

### Step 4: Structure the prompts

Use `P` namespace for clear, composable prompts:

```python
agent = Agent("analyst").instruct(
    P.role("You are a senior data analyst.")
    + P.context("You have access to the company's sales database.")
    + P.task("Analyze the provided data and identify trends.")
    + P.constraint(
        "Be concise — max 3 bullet points",
        "Include confidence levels",
        "Cite specific numbers",
    )
    + P.format("Return JSON with keys: trends, confidence, summary")
)
```

**Prompt composition rules:**
- Section order: role → context → task → constraint → format → example
- Use `P.when(pred, block)` for conditional sections
- Use `P.from_state("key")` for dynamic injection
- Use `P.example(input=, output=)` for few-shot learning

## Common architectures

### Research pipeline

```python
researcher = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Search for information about {topic}.")
    .tool(search_fn)
    .writes("research")
)
synthesizer = (
    Agent("synthesizer", "gemini-2.5-flash")
    .instruct("Synthesize {research} into a coherent report.")
    .reads("research")
    .writes("report")
)
reviewer = (
    Agent("reviewer", "gemini-2.5-flash")
    .instruct("Review {report} for accuracy. Say APPROVED if good.")
    .reads("report")
    .writes("review")
)

pipeline = review_loop(
    researcher >> synthesizer,
    reviewer,
    quality_key="review",
    target="APPROVED",
    max_rounds=3,
)
```

### Customer support triage

```python
classifier = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the customer issue. Set tier to: billing, technical, or general.")
    .writes("tier")
)

billing = Agent("billing", "gemini-2.5-flash").instruct("Handle billing issue.")
technical = Agent("technical", "gemini-2.5-pro").instruct("Handle technical issue.")
general = Agent("general", "gemini-2.5-flash").instruct("Handle general inquiry.")

system = classifier >> Route("tier").eq("billing", billing).eq("technical", technical).otherwise(general)
```

### Parallel analysis with merge

```python
web = Agent("web", "gemini-2.5-flash").instruct("Search web.").writes("web_results")
papers = Agent("papers", "gemini-2.5-flash").instruct("Search papers.").writes("paper_results")
synthesizer = (
    Agent("merge", "gemini-2.5-flash")
    .instruct("Merge {web_results} and {paper_results}.")
    .reads("web_results", "paper_results")
)

system = fan_out_merge(web, papers, merge_key="combined")
# Or manually: (web | papers) >> synthesizer
```

### Fallback chain with escalation

```python
# Try fast model first, fall back to stronger model
fast = Agent("fast", "gemini-2.5-flash").instruct("Answer the question.")
strong = Agent("strong", "gemini-2.5-pro").instruct("Answer the question thoroughly.")

system = fast // strong  # Fallback operator

# Or explicit cascade
from adk_fluent.patterns import cascade
system = cascade(fast, strong)
```

### Map-reduce over items

```python
analyzer = Agent("analyzer", "gemini-2.5-flash").instruct("Analyze this item.")
reducer = Agent("reducer", "gemini-2.5-flash").instruct("Summarize all analyses.")

system = map_reduce(analyzer, reducer, items_key="items", result_key="summary")
```

## Anti-patterns to avoid

### 1. LLM routing when rules work

```python
# Bad: using an LLM to route when the decision is deterministic
router = Agent("router").instruct("Decide which agent to use based on tier...")

# Good: deterministic routing
router = Route("tier").eq("VIP", vip_agent).otherwise(standard_agent)
```

### 2. Monolithic agents

```python
# Bad: one agent doing everything
agent = Agent("everything").instruct("Research, write, edit, and format the report...")

# Good: specialized agents in a pipeline
pipeline = researcher >> writer >> editor >> formatter
```

### 3. Missing context boundaries

```python
# Bad: background agent sees entire conversation history
bg_agent = Agent("utility").instruct("Format the data.")

# Good: utility agent with no history needed
bg_agent = Agent("utility").instruct("Format the data.").context(C.none())
```

### 4. Manual state threading

```python
# Bad: passing data through instructions manually
agent_b = Agent("b").instruct(f"Use this data: {data}")

# Good: using state keys
agent_a = Agent("a").writes("data")
agent_b = Agent("b").reads("data").instruct("Use {data}.")
```

### 5. Retry logic in tools

```python
# Bad: retry inside the tool function
def my_tool(query):
    for _ in range(3):
        try: return api_call(query)
        except: pass

# Good: middleware handles retries
agent = Agent("a").tool(my_tool).middleware(M.retry(max_attempts=3))
```

### 6. Exposing infrastructure in tool schemas

```python
# Bad: DB client in tool signature
def query_db(client: DBClient, sql: str): ...

# Good: inject infrastructure
agent = Agent("a").tool(query_db).inject(client=db_client)
```

## Visualization

Use built-in visualization to validate your architecture:

```python
# Generate Mermaid diagram
pipeline.to_mermaid()

# Structured IR view
pipeline.to_ir()

# Five-concern data flow analysis
pipeline.data_flow()

# Doctor report
pipeline.doctor()
```
