# One-Shot Execution

adk-fluent provides execution helpers that eliminate Runner and Session boilerplate. These methods let you go from builder to result in a single call.

:::{admonition} Execution backend awareness
:class: note

All execution methods below work with the default **ADK backend**. When using alternative backends, behavior varies:

| Method | ADK (default) | Temporal (in dev) | asyncio (in dev) |
|--------|--------------|-------------------|------------------|
| `.ask()` | Works | Not recommended (blocking) | Works |
| `.ask_async()` | Works | Works (starts workflow) | Works |
| `.stream()` | Real-time streaming | Falls back to batch | Works |
| `.session()` | In-memory history | Requires external state | Works |
| `.map_async()` | Concurrent tasks | Each prompt = workflow | Concurrent tasks |

See [Execution Backends](execution-backends.md) for details. The examples below use the default ADK backend.
:::

## `.ask(prompt)`

Send a prompt, get response text. No Runner or Session setup needed.

::::{tab-set}
:::{tab-item} ADK (default)
```python
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")

response = agent.ask("What is the capital of France?")
print(response)  # "The capital of France is Paris."
```
:::
:::{tab-item} Temporal (in dev)
```python
# .ask() is sync and blocks — use .ask_async() with Temporal instead.
# Temporal requires an async event loop to start workflows.
```
:::
:::{tab-item} asyncio (in dev)
```python
from adk_fluent import Agent

agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .engine("asyncio")
)

response = agent.ask("What is the capital of France?")
print(response)
```
:::
::::

`.ask()` internally builds the agent, creates a Runner and Session, sends the prompt, and returns the final response text.

## `.ask_async(prompt)`

Async version of `.ask()`. **Required for the Temporal backend.**

::::{tab-set}
:::{tab-item} ADK (default)
```python
import asyncio
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")

async def main():
    response = await agent.ask_async("What is the capital of France?")
    print(response)

asyncio.run(main())
```
:::
:::{tab-item} Temporal (in dev)
```python
import asyncio
from temporalio.client import Client
from adk_fluent import Agent

async def main():
    client = await Client.connect("localhost:7233")

    agent = (
        Agent("helper", "gemini-2.5-flash")
        .instruct("You are a helpful assistant.")
        .engine("temporal", client=client, task_queue="qa")
    )
    # Starts a Temporal workflow — durable, crash-recoverable
    response = await agent.ask_async("What is the capital of France?")
    print(response)

asyncio.run(main())
```
:::
:::{tab-item} asyncio (in dev)
```python
import asyncio
from adk_fluent import Agent

async def main():
    agent = (
        Agent("helper", "gemini-2.5-flash")
        .instruct("You are a helpful assistant.")
        .engine("asyncio")
    )
    response = await agent.ask_async("What is the capital of France?")
    print(response)

asyncio.run(main())
```
:::
::::

## `.stream(prompt)`

Async generator that yields response text chunks as they arrive.

::::{tab-set}
:::{tab-item} ADK (default)
```python
import asyncio
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")

async def main():
    async for chunk in agent.stream("Tell me a story."):
        print(chunk, end="", flush=True)

asyncio.run(main())
```
Real-time streaming — chunks arrive as the LLM generates them.
:::
:::{tab-item} Temporal (in dev)
```python
# Temporal does NOT support real-time streaming.
# .stream() falls back to collecting all events, then yielding them at once.
# Use .ask_async() instead for Temporal workloads.

async for chunk in agent.stream("Tell me a story."):
    print(chunk, end="", flush=True)  # All chunks arrive at once
```
:::
:::{tab-item} asyncio (in dev)
```python
import asyncio
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("Tell stories.").engine("asyncio")

async def main():
    async for chunk in agent.stream("Tell me a story."):
        print(chunk, end="", flush=True)

asyncio.run(main())
```
:::
::::

## `.events(prompt)`

Async generator that yields raw ADK `Event` objects, giving full access to state deltas, function calls, and other event metadata:

```python
import asyncio
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")

async def main():
    async for event in agent.events("What is 2+2?"):
        print(event)

asyncio.run(main())
```

## `.session()`

Create an interactive multi-turn session using `async with`:

```python
import asyncio
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")

async def main():
    async with agent.session() as chat:
        r1 = await chat.send("Hi, my name is Alice.")
        print(r1)
        r2 = await chat.send("What is my name?")
        print(r2)  # Should remember "Alice"

asyncio.run(main())
```

The session maintains conversation history across turns, enabling multi-turn interactions.

## `.map(prompts, concurrency=5)`

Batch execution against multiple prompts with bounded concurrency:

```python
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("Translate to French.")

prompts = ["Hello", "Goodbye", "Thank you", "Please"]
results = agent.map(prompts, concurrency=3)
for prompt, result in zip(prompts, results):
    print(f"{prompt} -> {result}")
```

## `.map_async(prompts, concurrency=5)`

Async version of `.map()`:

```python
import asyncio
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("Translate to French.")

async def main():
    prompts = ["Hello", "Goodbye", "Thank you"]
    results = await agent.map_async(prompts, concurrency=3)
    for prompt, result in zip(prompts, results):
        print(f"{prompt} -> {result}")

asyncio.run(main())
```

## `.test(prompt, contains=, matches=, equals=)`

Smoke test: calls `.ask()` and asserts the output matches the given condition:

```python
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a math tutor.")

# Assert the response contains a specific string
agent.test("What is 2+2?", contains="4")

# Assert with regex
agent.test("What is 2+2?", matches=r"\b4\b")

# Assert exact match
agent.test("What is 2+2?", equals="4")
```

`.test()` returns `self` so it can be chained with other builder methods. It is useful for quick inline smoke tests during development.

## `.to_app(config=None)`

Compile the builder through IR to a native ADK `App` object. This is the production-grade alternative to `.build()` that supports middleware, resumability, and event compaction:

```python
from adk_fluent import Agent, ExecutionConfig, CompactionConfig

app = (
    Agent("prod")
    .model("gemini-2.5-flash")
    .instruct("Production agent.")
    .to_app(config=ExecutionConfig(
        app_name="prod_service",
        resumable=True,
        compaction=CompactionConfig(interval=10, overlap=2),
    ))
)
```

Unlike `.build()` which returns a raw ADK agent, `.to_app()` returns a full `App` object with configuration applied.

## Execution Method Summary

| Method                                        | Description                                                                               |
| --------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `.ask(prompt)`                                | Send a prompt, get response text. No Runner/Session boilerplate                           |
| `.ask_async(prompt)`                          | Async version of `.ask()`                                                                 |
| `.stream(prompt)`                             | Async generator yielding response text chunks                                             |
| `.events(prompt)`                             | Async generator yielding raw ADK `Event` objects                                          |
| `.map(prompts, concurrency=5)`                | Batch execution against multiple prompts                                                  |
| `.map_async(prompts, concurrency=5)`          | Async batch execution                                                                     |
| `.session()`                                  | Create an interactive `async with` session context manager                                |
| `.test(prompt, contains=, matches=, equals=)` | Smoke test: calls `.ask()` and asserts output                                             |
| `.to_app(config=None)`                        | Compile through IR to native ADK `App` with config (resumability, compaction, middleware) |

## Choosing an Execution Method

| Situation | Use | Why |
|---|---|---|
| Quick prototyping / REPL | `.ask()` | Synchronous, zero boilerplate |
| Async application | `.ask_async()` | Non-blocking, integrates with asyncio |
| Real-time UI | `.stream()` | Chunks arrive as they're generated |
| Low-level debugging | `.events()` | Full ADK Event access including state deltas |
| Multi-turn chatbot | `.session()` | Maintains conversation history |
| Batch processing | `.map()` / `.map_async()` | Bounded concurrency, processes multiple prompts |
| Inline testing | `.test()` | Assert output during development |
| Production deployment | `.to_app()` | Full App with middleware, resumability, compaction |

## Interplay with Other Modules

### Execution + Middleware

`.ask()`, `.stream()`, and `.session()` don't support middleware -- they create lightweight runners internally. For middleware support, use `.to_app()`:

```python
from adk_fluent import Agent
from adk_fluent._middleware import M

# No middleware: fine for prototyping
response = Agent("helper").instruct("Help.").ask("Hi")

# With middleware: use .to_app()
pipeline = (Agent("a") >> Agent("b")).middleware(M.retry(3) | M.log())
app = pipeline.to_app()
```

### Execution + Visibility

`.stream()` respects visibility settings. Hidden agents' chunks don't appear in the stream:

```python
pipeline = (
    Agent("analyzer").instruct("Analyze.").hide()
    >> Agent("writer").instruct("Write.")
)
async for chunk in pipeline.stream("Explain"):
    print(chunk, end="")  # Only writer's output
```

See [Visibility](visibility.md).

### Execution + Context Engineering

`.session()` maintains conversation history across turns. Context engineering (`C.*`) controls how much of that history each agent sees:

```python
from adk_fluent import Agent, C

agent = Agent("advisor").instruct("Advise.").context(C.window(n=5))
async with agent.session() as chat:
    r1 = await chat.send("Question 1")
    # ... many turns later ...
    r10 = await chat.send("Question 10")
    # Agent sees turns 6-10 (window of 5)
```

See [Context Engineering](context-engineering.md).

### Execution + Testing

`.test()` is the bridge between execution and testing. It calls `.ask()` internally and asserts the output:

```python
# Development: inline smoke test
agent = Agent("math", "gemini-2.5-flash").instruct("You are a math tutor.")
agent.test("What is 2+2?", contains="4")

# CI: use mock_backend for deterministic tests
from adk_fluent.testing import AgentHarness, mock_backend
harness = AgentHarness(agent, backend=mock_backend({"math": "4"}))
```

See [Testing](testing.md).

## Best Practices

1. **Use `.ask()` for prototyping, `.to_app()` for production.** `.ask()` is convenient but doesn't support middleware, resumability, or compaction
2. **Use `.stream()` for user-facing output.** Streaming provides better UX than waiting for the full response
3. **Use `.map()` with bounded concurrency for batch jobs.** Don't fire 1000 concurrent requests — use `concurrency=` to control
4. **Use `.session()` for multi-turn interactions.** Don't manually manage conversation history
5. **Use `.test()` during development, `AgentHarness` in CI.** `.test()` hits the real LLM; `AgentHarness` with `mock_backend` is deterministic
6. **Use `.engine("temporal")` for crash-resilient pipelines.** When durability matters, switch to Temporal — your builder definitions stay the same (Temporal backend is in development)

:::{tip}
**Visual learner?** Open the [Execution Modes Interactive Reference](../execution-modes-reference.html){target="_blank"} for sync vs async flow diagrams, an environment compatibility matrix, and the RuntimeError trap.
:::

:::{seealso}
- [Execution Backends](execution-backends.md) — backend selection, capability matrix, `.engine()` method
- [Temporal Guide](temporal-guide.md) — durable execution, crash recovery, Temporal-specific patterns
- [Testing](testing.md) — `.mock()`, `.test()`, `AgentHarness`, and `check_contracts()`
- [Middleware](middleware.md) — pipeline-wide retry, logging, and tracing via `.to_app()`
- [Visibility](visibility.md) — controlling which agents' output appears in streams
- [Context Engineering](context-engineering.md) — controlling history in `.session()` interactions
:::
