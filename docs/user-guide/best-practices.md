# Best Practices & Anti-Patterns

When building complex agentic systems, it's easy to fall into patterns that work for a prototype but fail in production. This guide outlines the "adk-fluent way"—showing you how to leverage the framework's primitives for maximum reliability, security, and maintainability.

## 1. Routing: Deterministic vs. LLM-Driven

One of the most common mistakes is using an LLM to make decisions that could be evaluated with simple code. If a decision is deterministic (e.g., checking a user tier, reading a category tag), **do not use an LLM**.

::::\{tab-set}
:::\{tab-item} ❌ Anti-Pattern: LLM Routing

```python
# Wastes tokens, adds latency, and risks hallucinated routing decisions.
router = (
    Agent("router")
    .model("gemini-2.5-flash")
    .instruct("Look at the state. If customer_tier is 'VIP', transfer to vip_agent. Otherwise transfer to standard_agent.")
    .sub_agent(vip_agent)
    .sub_agent(standard_agent)
)
```

:::
:::\{tab-item} ✅ Best Practice: Deterministic Routing

```python
from adk_fluent._routing import Route

# Zero token cost, zero latency, 100% reliable.
router = (
    Route("customer_tier")
    .eq("VIP", vip_agent)
    .otherwise(standard_agent)
)
```

:::
::::

*Rule of thumb:* Only use LLM-driven routing (like `.agent_tool()`) when the decision requires semantic understanding (e.g., "Which of these three domain experts is best suited to answer this vague question?").

## 2. Infrastructure: Dependency Injection vs. Global State

When your agents need to interact with external systems (databases, APIs), you must provide them with clients or credentials. Never pass these as standard arguments to tools, as this leaks infrastructure details into the LLM's schema context.

::::\{tab-set}
:::\{tab-item} ❌ Anti-Pattern: Leaking Credentials

```python
# The LLM sees `db_connection` in the tool schema and might try to invent a string for it!
def fetch_user(user_id: str, db_connection: str) -> str:
    return db.execute(db_connection, f"SELECT * FROM users WHERE id={user_id}")

agent = Agent("data_fetcher").tool(fetch_user)
```

:::
:::\{tab-item} ✅ Best Practice: Dependency Injection

```python
# The LLM only sees `user_id`. The framework injects `db_connection` at runtime.
def fetch_user(user_id: str, db_connection: object) -> str:
    return db_connection.execute(f"SELECT * FROM users WHERE id={user_id}")

agent = (
    Agent("data_fetcher")
    .tool(fetch_user)
    .inject(db_connection=my_prod_db_client)
)
```

:::
::::

## 3. Data Transformation: Custom Agents vs. Functions

You need to clean up some data between two LLM calls (e.g., extracting an ID from a string, or truncating text). In native ADK, this requires creating a whole new `BaseAgent` class. In `adk-fluent`, you should just use a plain function or the `S` module.

::::\{tab-set}
:::\{tab-item} ❌ Anti-Pattern: Over-engineering

```python
# Too much boilerplate for a simple data transform.
class TextCleaner(BaseAgent):
    async def _run_async_impl(self, ctx):
        ctx.session.state["clean_text"] = ctx.session.state["raw"].strip().lower()

pipeline = Agent("step1") >> TextCleaner(name="cleaner") >> Agent("step2")
```

:::
:::\{tab-item} ✅ Best Practice: Function Steps

```python
from adk_fluent import S

# Option A: S module factory
pipeline = Agent("step1") >> S.transform("raw", lambda x: x.strip().lower()) >> Agent("step2")

# Option B: Plain function step
def clean_text(state):
    return {"clean_text": state.get("raw", "").strip().lower()}

pipeline = Agent("step1") >> clean_text >> Agent("step2")
```

:::
::::

## 4. Context Management: Global vs. Scoped History

By default, conversational agents see the entire message history. For intermediate background tasks (like classifying intent or extracting JSON), passing the whole conversation wastes tokens, increases latency, and drastically increases the chance of hallucination.

::::\{tab-set}
:::\{tab-item} ❌ Anti-Pattern: Global Context

```python
# The parser sees the user's entire chat history, which might confuse it.
parser = (
    Agent("invoice_parser")
    .model("gemini-2.5-flash")
    .instruct("Parse the invoice into JSON.")
    # (Default behavior: sees all past messages)
)
```

:::
:::\{tab-item} ✅ Best Practice: Scoped Context

```python
from adk_fluent import C

# The parser only sees exactly the variables it needs to do its job.
parser = (
    Agent("invoice_parser")
    .model("gemini-2.5-flash")
    .instruct("Parse this invoice: {invoice_text}")
    .context(C.none()) # Hide conversation history
)
```

:::
::::

## 5. Cross-Cutting Concerns: Callbacks vs. Middleware

When you need to add logging, retry logic, or latency tracking to multiple agents, manually attaching callbacks leads to duplicated code and missed edges.

::::\{tab-set}
:::\{tab-item} ❌ Anti-Pattern: Scattered Callbacks

```python
# Hard to maintain. Easy to forget when adding a new agent.
agent_a = Agent("a").before_model(log_req).after_model(log_res)
agent_b = Agent("b").before_model(log_req).after_model(log_res)
agent_c = Agent("c").before_model(log_req).after_model(log_res)

pipeline = agent_a >> agent_b >> agent_c
```

:::
:::\{tab-item} ✅ Best Practice: Middleware

```python
from adk_fluent._middleware import M

# Define agents purely by their business logic
agent_a = Agent("a")
agent_b = Agent("b")
agent_c = Agent("c")

# Apply observability across the entire pipeline at the top level
pipeline = (agent_a >> agent_b >> agent_c).middleware(
    M.retry(3) | M.log() | M.latency()
)
```

:::
::::

*Tip:* If you need to share pure configuration (like a specific model version and temperature) across many agents without using middleware, use a `Preset`.

## 6. The Interplay of Namespace Modules (C, S, A, T, M, P)

The true power of `adk-fluent` emerges when the single-letter namespace modules are used *together*. They are designed to act as a cohesive functional pipeline, mapping external data into isolated state, scoping that state into the LLM's context, and applying resilience.

### Scenario: The ETL RAG Pattern

Consider a scenario where an agent needs to answer a question based on a specific uploaded file.

::::\{tab-set}
:::\{tab-item} ❌ Anti-Pattern: Monolithic Prompts & State

```python
# The agent tries to do too much at once. The raw file contents might blow up the context window.
agent = (
    Agent("qa_bot")
    .instruct("Read the file stored in state['file_contents'] and answer the user. File: {file_contents}")
    # Relies on the user manually injecting 'file_contents' into the session state beforehand
)
```

:::
:::\{tab-item} ✅ Best Practice: A -> S -> C -> P

```python
from adk_fluent import A, S, C, P, Agent

# 1. (A) Read the artifact into state
# 2. (S) Transform the raw text into a cleaned summary to save tokens
# 3. (C) Scope the agent to ONLY see the summarized context (hide the rest of the chat)
# 4. (P) Compose the prompt dynamically

pipeline = (
    A.read_text("knowledge_base.txt", into_key="raw_text")
    >> S.transform("raw_text", lambda text: text[:2000].strip()) # Clean it up
    >> S.rename(raw_text="clean_context")
    >> Agent("qa_bot")
    .context(C.from_state("clean_context") + C.user_only()) # Hide previous assistant messages
    .instruct(
        P.system("You are a QA bot.") +
        P.guidelines("Only answer using the provided context. If you don't know, say so.") +
        P.text("Context: {clean_context}")
    )
)
```

:::
::::

### Scenario: The Resilient Tool Coordinator

When an agent relies on external tools (like an API), those tools will inevitably fail or rate-limit. Instead of writing complex error-handling code inside your tools, use the interplay of `T` (Tools) and `M` (Middleware).

::::\{tab-set}
:::\{tab-item} ❌ Anti-Pattern: Fat Tools

```python
# Tool is polluted with retry logic and error handling
def fetch_weather(city: str) -> str:
    for attempt in range(3):
        try:
            return api.get_weather(city)
        except RateLimitError:
            time.sleep(1)
    return "Error fetching weather"

agent = Agent("weather_bot").tool(fetch_weather)
```

:::
:::\{tab-item} ✅ Best Practice: T + M Interplay

```python
from adk_fluent import Agent
from adk_fluent._tools import T
from adk_fluent._middleware import M

# Tool is pure business logic
def fetch_weather(city: str) -> str:
    return api.get_weather(city)

# 1. (T) Wrap the tool and apply strict schemas
# 2. (M) Apply exponential backoff and observability at the agent level
agent = (
    Agent("weather_bot")
    .tools(T.fn(fetch_weather) | T.schema(WeatherOutputSchema))
    .middleware(M.retry(max_attempts=3) | M.log())
)
```

:::
::::
