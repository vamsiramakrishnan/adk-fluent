# One-Shot Execution

adk-fluent provides execution helpers that eliminate Runner and Session boilerplate. These methods let you go from builder to result in a single call.

## `.ask(prompt)`

Send a prompt, get response text. No Runner or Session setup needed:

```python
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")

response = agent.ask("What is the capital of France?")
print(response)  # "The capital of France is Paris."
```

`.ask()` internally builds the agent, creates a Runner and Session, sends the prompt, and returns the final response text.

## `.ask_async(prompt)`

Async version of `.ask()`:

```python
import asyncio
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")

async def main():
    response = await agent.ask_async("What is the capital of France?")
    print(response)

asyncio.run(main())
```

## `.stream(prompt)`

Async generator that yields response text chunks as they arrive:

```python
import asyncio
from adk_fluent import Agent

agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")

async def main():
    async for chunk in agent.stream("Tell me a story."):
        print(chunk, end="", flush=True)

asyncio.run(main())
```

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

| Method | Description |
|--------|-------------|
| `.ask(prompt)` | Send a prompt, get response text. No Runner/Session boilerplate |
| `.ask_async(prompt)` | Async version of `.ask()` |
| `.stream(prompt)` | Async generator yielding response text chunks |
| `.events(prompt)` | Async generator yielding raw ADK `Event` objects |
| `.map(prompts, concurrency=5)` | Batch execution against multiple prompts |
| `.map_async(prompts, concurrency=5)` | Async batch execution |
| `.session()` | Create an interactive `async with` session context manager |
| `.test(prompt, contains=, matches=, equals=)` | Smoke test: calls `.ask()` and asserts output |
| `.to_app(config=None)` | Compile through IR to native ADK `App` with config (resumability, compaction, middleware) |
