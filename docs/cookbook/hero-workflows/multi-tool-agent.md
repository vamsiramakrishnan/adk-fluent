# Multi-Tool Task Agent — Tools, Guards, and Dependency Injection

> **Modules in play:** `.tool()` function tools, `.guard()` safety guardrails,
> `.inject()` dependency injection, `.context()` context engineering,
> `>>` sequential with verifier

## The Real-World Problem

Your task agent needs three tools: web search, a calculator, and a cloud file
reader. The file reader requires an API key — but if you include `api_key` in
the tool's function signature, the LLM sees it in the schema and might try to
guess or hallucinate a key value. You also need a safety guardrail that screens
*every* request for attempts to access system files, execute arbitrary code, or
exfiltrate data. And after the agent finishes, a second agent should verify the
work.

The native ADK approach leaks infrastructure params into the LLM schema (via
`functools.partial`) and requires separate `before_model_callback` and
`after_model_callback` registrations for guards.

## The Fluent Solution

```python
from adk_fluent import Agent, C


def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}"


def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return f"Result: {expression}"


def read_file(path: str, api_key: str) -> str:
    """Read a file from cloud storage."""
    return f"Contents of {path} (via {api_key})"


def safety_guardrail(callback_context, llm_request):
    """Screen requests for unsafe operations."""
    # Block system file access, code execution, data exfiltration
    return None


# THE SYMPHONY: tools + DI + guard + verifier pipeline
task_agent = (
    Agent("task_agent", "gemini-2.5-flash")
    .instruct(
        "You are a versatile task agent. Use your tools to research, "
        "calculate, and read files. Explain your reasoning before using a tool."
    )
    .tool(search_web)
    .tool(calculate)
    .tool(read_file)
    .inject(api_key="prod_key")    # Hidden from LLM — only visible to read_file
    .guard(safety_guardrail)       # Registers as BOTH before_model AND after_model
)

# Verifier checks the task agent's work
verifier = (
    Agent("verifier", "gemini-2.5-flash")
    .instruct("Verify the task agent's output for accuracy and completeness.")
    .context(C.from_state("task_result"))
)

# Compose: agent → verifier
verified_agent = task_agent.writes("task_result") >> verifier
```

## The Interplay Breakdown

**Why `.inject()` instead of `functools.partial`?**
In native ADK, you'd use `functools.partial(read_file, api_key="prod_key")`.
The problem: `partial` changes the function signature in unpredictable ways
across Python versions, and the LLM schema may still leak the parameter name.
`.inject(api_key="prod_key")` uses adk-fluent's DI system to:
1. Remove `api_key` from the tool schema the LLM sees
2. Automatically supply the value when the tool is called
3. Keep the original function signature clean for testing

**Why `.guard()` instead of separate callback registration?**
A safety guardrail needs to run both *before* the LLM call (to screen the
request) and *after* (to screen the response). In native ADK, that's two
separate callback registrations. `.guard(fn)` registers the same function as
both `before_model_callback` and `after_model_callback` in a single call.

**Why `.tool()` three times instead of `.tools([...])`?**
`.tool()` appends — it doesn't replace. This means you can build up an
agent's tool belt incrementally, which is useful when tools come from
different sources (local functions, MCP servers, API specs). The alternative
`.tools(T.fn(search_web) | T.fn(calculate) | T.fn(read_file))` uses the
T module's composition operator for the same result.

**Why a separate verifier agent?**
Self-verification (asking the same LLM "was your output correct?") is weak.
A separate verifier agent with its own context (`C.from_state("task_result")`)
sees *only* the task output — not the original prompt, not the tool calls,
not the safety guardrail decisions. This isolation prevents confirmation bias.

## Pipeline Topology

```
task_agent
  ├─ tools: [search_web, calculate, read_file]
  ├─ inject: {api_key: "prod_key"}   ← hidden from LLM
  ├─ guard: safety_guardrail         ← before + after model
  └─ writes: "task_result"
      ──► verifier [C.from_state("task_result")]
```

## Running on Different Backends

::::{tab-set}
:::{tab-item} ADK (default)
```python
pipeline = task_agent >> verifier
response = pipeline.ask("Analyze the Q3 earnings for AAPL")
```
:::
:::{tab-item} Temporal (in dev)
```python
from temporalio.client import Client
client = await Client.connect("localhost:7233")

# Tool calls become Activity sub-calls within the agent Activity
# Guards and callbacks execute within the Activity boundary
pipeline = (task_agent >> verifier).engine("temporal", client=client, task_queue="tools")
response = await pipeline.ask_async("Analyze the Q3 earnings for AAPL")
```
:::
:::{tab-item} asyncio (in dev)
```python
pipeline = (task_agent >> verifier).engine("asyncio")
response = await pipeline.ask_async("Analyze the Q3 earnings for AAPL")
```
:::
::::
