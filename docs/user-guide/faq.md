# FAQ

:::{admonition} At a Glance
:class: tip

Top 20 questions about adk-fluent with direct answers and links.
:::

## General

### What is adk-fluent?

A fluent builder API for Google's Agent Development Kit (ADK). It reduces agent creation from 22+ lines to 1-3 lines while producing **identical native ADK objects**. Every `.build()` returns a real ADK object compatible with `adk web`, `adk run`, and `adk deploy`.

### Does adk-fluent add runtime overhead?

No. Builders exist only at definition time. After `.build()`, adk-fluent is gone --- you have a pure ADK object. Zero runtime overhead.

### Can I mix adk-fluent with native ADK code?

Yes. `.build()` returns a native ADK object. You can pass it to any ADK function, use it with `adk web`, or mix fluent and native agents in the same pipeline.

### Which models does adk-fluent support?

Any model that ADK supports. Use `gemini-2.5-flash` for fast/cheap, `gemini-2.5-pro` for quality. Model names are passed as strings to `.model()` or as the second positional arg to `Agent()`.

---

## Building Agents

### When do I call `.build()`?

Call `.build()` on the **outermost** builder only. Sub-builders inside `Pipeline`, `FanOut`, `Loop`, or expression operators are auto-built:

```python
# ✅ Correct --- .build() on the pipeline only
pipeline = (Agent("a") >> Agent("b")).build()

# ❌ Wrong --- don't build sub-builders
Pipeline("p").step(Agent("a").build()).build()
```

### What's the difference between `.instruct()` and `.describe()`?

- `.instruct()` sets the **system prompt** --- what the LLM is told to do
- `.describe()` sets **metadata** for transfer routing --- NOT sent to the LLM

### What's the difference between `.sub_agent()` and `.agent_tool()`?

- `.sub_agent()`: The LLM decides when to hand off (transfer-based). Control transfers to the child.
- `.agent_tool()`: The parent LLM invokes the child like a tool (stays in control).

Use `.agent_tool()` by default. Use `.sub_agent()` when the child needs full conversational control. See {doc}`transfer-control`.

### How do I add multiple tools?

```python
# One at a time
agent = Agent("a").tool(fn1).tool(fn2)

# All at once
agent = Agent("a").tools([fn1, fn2])

# T module composition
agent = Agent("a").tools(T.fn(fn1) | T.fn(fn2) | T.google_search())
```

---

## Data Flow

### How do I pass data between agents?

Use `.writes()` to store output in state, and `.reads()` or `{key}` templates to access it:

```python
pipeline = (
    Agent("a").writes("result")                # Store output
    >> Agent("b").instruct("Use {result}.")    # Template access
)
```

See {doc}`data-flow`.

### What's the difference between `.reads()` and `.context()`?

Both control what the agent sees. `.reads("key")` is a shorthand that:
1. Injects `state["key"]` into the prompt
2. Suppresses conversation history

`.context(C.xxx())` gives fine-grained control (window, user-only, budget, etc.). You can combine them. See {doc}`context-engineering`.

### Why does my agent see the same data twice?

ADK has three independent channels: conversation history, session state, and instruction templating. When you use `.writes("intent")`, the text appears in **both** conversation history (Channel 1) and state (Channel 2). Use `.reads("intent")` on downstream agents to suppress history and use only state.

See {doc}`architecture-and-concepts` for the full explanation.

### What's the difference between `.writes()` and `.returns()`?

- `.writes(key)` stores the **raw text** response in `state[key]` (for downstream agents)
- `.returns(Schema)` constrains the LLM to produce **structured JSON** matching a Pydantic model

They're orthogonal --- you can use both on the same agent.

---

## Operators

### What's the difference between `>>` and `|`?

- `>>` (sequence): Agents run one after another. `a >> b >> c`
- `|` (parallel): Agents run concurrently. `a | b | c`

### Can I combine operators?

Yes, all operators compose:

```python
pipeline = (
    (Agent("web") | Agent("papers"))          # Parallel research
    >> S.merge("web", "papers", into="all")   # Merge results
    >> Agent("writer") @ Report               # Write with schema
    >> (Agent("critic") >> Agent("reviser"))   # Review loop
    * until(lambda s: s.get("score") >= 0.8, max=3)
)
```

### What does `@` do?

`Agent("a") @ Schema` is equivalent to `Agent("a").returns(Schema)`. It constrains the LLM to produce JSON matching the Pydantic model.

---

## Testing

### How do I test without making LLM calls?

Use `mock_backend()` and `AgentHarness`:

```python
from adk_fluent.testing import AgentHarness, mock_backend

harness = AgentHarness(
    my_pipeline,
    backend=mock_backend({"agent_a": "mocked response"})
)
response = await harness.send("test")
```

See {doc}`testing`.

### How do I catch data flow bugs?

Use `check_contracts()` --- it's free (no LLM calls) and catches the most common bugs:

```python
from adk_fluent.testing import check_contracts
issues = check_contracts(my_pipeline.to_ir())
assert not issues
```

---

## Async / Sync

### I get RuntimeError in Jupyter / FastAPI. Why?

The sync methods (`.ask()`, `.map()`) raise `RuntimeError` inside an async event loop. Use the async variants:

```python
# ❌ In Jupyter/FastAPI
result = agent.ask("hello")  # RuntimeError!

# ✅ Use async variants
result = await agent.ask_async("hello")
```

---

## Advanced

### How do I use Temporal for durable execution?

```python
pipeline = (Agent("a") >> Agent("b")).engine("temporal", client=client, task_queue="my-queue")
```

See {doc}`temporal-guide`.

### Can I use MCP tools?

Yes, via the T module:

```python
agent = Agent("helper").tools(T.mcp(my_mcp_server))
```

### How do I inject dependencies (DB clients, API keys)?

Use `.inject()` --- injected params are hidden from the LLM tool schema:

```python
agent = Agent("lookup").tool(search_db).inject(db=my_database)
# LLM sees: search_db(query: str)
# At runtime: db=my_database injected
```

---

:::{seealso}
- {doc}`../getting-started` --- 5-minute quickstart
- {doc}`cheat-sheet` --- one-page API reference
- {doc}`glossary` --- term definitions
- {doc}`troubleshooting` --- error → cause → fix
:::
