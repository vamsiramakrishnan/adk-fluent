# Asyncio Backend -- Zero-Dependency IR Interpreter

The asyncio backend executes agent pipelines directly using Python
asyncio — no ADK, no Temporal, no external dependencies. It interprets
the IR tree and calls a ModelProvider for LLM invocations.

Use cases: testing without API keys, lightweight deployments, custom
model integrations (local models, OpenAI, Anthropic), and proving
that the five-layer architecture works with any backend.

:::{tip} What you'll learn
How to compose agents into a sequential pipeline.
:::

_Source: `69_asyncio_backend.py`_

```python
from adk_fluent import Agent, Pipeline, FanOut, Loop
from adk_fluent.backends.asyncio_backend import AsyncioBackend
from adk_fluent.compile import EngineCapabilities

# 1. Create an asyncio backend
#    In real usage, pass a ModelProvider for LLM calls.
#    Without one, agents return placeholder text.
backend = AsyncioBackend()

# 2. Compile and inspect a pipeline through the asyncio backend
pipeline = Agent("researcher").instruct("Research the topic.").writes("findings") >> Agent("writer").instruct(
    "Write based on {findings}."
)

ir = pipeline.to_ir()
compiled = backend.compile(ir)

# 3. The compiled result is an _AsyncioRunnable that wraps the IR
assert compiled.node is ir

# 4. Capabilities: parallel and streaming, but not durable
caps = backend.capabilities
assert isinstance(caps, EngineCapabilities)

# 5. FanOut compiles to parallel asyncio.gather()
fanout = Agent("web_search").instruct("Search the web.") | Agent("paper_search").instruct("Search academic papers.")
fanout_ir = fanout.to_ir()
fanout_compiled = backend.compile(fanout_ir)
assert fanout_compiled.node is fanout_ir

# 6. Loop compiles to iteration
loop_ir = (
    Loop("refine")
    .step(Agent("writer").instruct("Write."))
    .step(Agent("critic").instruct("Critique."))
    .max_iterations(3)
    .to_ir()
)
loop_compiled = backend.compile(loop_ir)

# 7. Builder shorthand: .engine("asyncio")
#    When used with .ask_async(), routes through the asyncio backend.
agent = Agent("solver").instruct("Solve the problem.").engine("asyncio")
assert agent._config["_engine"] == "asyncio"
```

## Equivalence

```python
# AsyncioBackend satisfies expected capabilities
assert caps.streaming is True
assert caps.parallel is True
assert caps.durable is False
assert caps.replay is False
assert caps.checkpointing is False
assert caps.distributed is False

# Backend name
assert backend.name == "asyncio"

# Compiled objects preserve the IR tree
assert compiled.node is ir
assert fanout_compiled.node is fanout_ir
assert loop_compiled.node is loop_ir
```
