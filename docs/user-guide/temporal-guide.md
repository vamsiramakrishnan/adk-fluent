# Temporal Guide

:::{admonition} In Development
:class: warning

The Temporal backend is under active development. The core compile and run paths work, but the API may change. This guide documents the current design and intended patterns. Not recommended for production use yet.
:::

This guide covers Temporal-specific patterns, constraints, and examples for running adk-fluent agents with durable execution. For general backend selection, see [Execution Backends](execution-backends.md).

## Why Temporal?

Temporal provides **durable execution** — your agent pipeline survives process crashes, network failures, and deployments. If a 10-step pipeline crashes at step 7, Temporal replays steps 1–6 from cached results (zero LLM cost) and re-executes only step 7 onward.

This matters for:
- **Long-running agent pipelines** (research → write → review → publish)
- **Expensive LLM calls** that shouldn't be repeated on failure
- **Human-in-the-loop workflows** that pause for approval
- **Distributed execution** across multiple workers/machines

## Setup

### Install

```bash
pip install adk-fluent[temporal]
```

This adds `temporalio` as a dependency.

### Start Temporal (local development)

```bash
# Install Temporal CLI
brew install temporal  # macOS
# or: curl -sSf https://temporal.download/cli.sh | sh

# Start local dev server
temporal server start-dev
```

The Temporal UI is available at `http://localhost:8233`.

### Connect

```python
from temporalio.client import Client

client = await Client.connect("localhost:7233")
```

## Basic Usage

### Select the Temporal backend

```python
from adk_fluent import Agent

agent = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic thoroughly.")
    .engine("temporal", client=client, task_queue="research")
)

# Execute — this starts a Temporal workflow
response = await agent.ask_async("quantum computing advances")
```

### Pipelines

```python
from adk_fluent import Agent

pipeline = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the topic.").writes("findings")
    >> Agent("writer", "gemini-2.5-flash")
    .instruct("Write a report about {findings}.").writes("draft")
    >> Agent("reviewer", "gemini-2.5-flash")
    .instruct("Review and score the draft: {draft}")
)

pipeline = pipeline.engine("temporal", client=client, task_queue="pipeline")
response = await pipeline.ask_async("AI in healthcare")
```

Each agent step becomes a Temporal **activity** (non-deterministic LLM call). The pipeline structure becomes the **workflow** (deterministic orchestration). If the process crashes after the writer completes, only the reviewer re-executes.

## Determinism Rules

Temporal replays workflow code to reconstruct state. This means workflow code must be **deterministic** — given the same inputs, it must produce the same outputs.

### What is deterministic (safe in workflow code)

- State transforms: `S.pick()`, `S.merge()`, `S.rename()`, etc.
- Route decisions: `Route("key").eq("value", agent)`
- Conditional gates: `.proceed_if(lambda s: s.get("valid"))`
- Loop conditions: `until(lambda s: s.get("score") >= 0.8)`
- Pure functions: `>> merge_research` (no I/O)
- `tap(fn)` — observation only, no side effects

### What is non-deterministic (becomes an activity)

- LLM calls: every `AgentNode` (the core of what agents do)
- Tool calls: external API calls, database queries, file I/O
- `datetime.now()`, `random()`, `uuid4()`

### What to avoid in workflow code

```python
# BAD — non-deterministic in a transform
pipeline = agent >> (lambda s: {"time": datetime.now().isoformat()}) >> next_agent

# GOOD — use Temporal's workflow.now() inside an activity, or
# pass the timestamp as part of the initial input
```

## IR → Temporal Mapping

Understanding how IR nodes map to Temporal concepts helps you design effective pipelines.

| IR Node | Temporal Concept | Behavior |
|---------|-----------------|----------|
| `AgentNode` | **Activity** | LLM call; result cached on replay |
| `SequenceNode` (`>>`) | **Workflow body** | Sequential `await` of activities |
| `ParallelNode` (`\|`) | **Workflow** `asyncio.gather()` | Parallel activity execution |
| `LoopNode` (`*`) | **Workflow** `while` loop | Each iteration checkpointed |
| `TransformNode` (`>> fn`) | **Inline code** | Pure function, replayed from history |
| `TapNode` (`tap(fn)`) | **Inline code** | Observation, no I/O |
| `RouteNode` (`Route(...)`) | **Inline code** | Deterministic switch |
| `FallbackNode` (`//`) | **Workflow** try/except | Try activity A, on failure try B |
| `GateNode` (`gate(pred)`) | **Signal** + `wait_condition` | Pauses for external input |
| `DispatchNode` (`dispatch()`) | **Child workflow** | Fire-and-forget background task |
| `JoinNode` (`join()`) | **Await child handle** | Wait for background task |

### Key principle

**Deterministic nodes** = workflow code (replayed from history, zero cost).
**Non-deterministic nodes** = activities (cached, re-executed only on first run or after crash).

## Patterns

### Crash-resilient pipeline

```python
from adk_fluent import Agent, S

# A 4-step pipeline where each LLM call is an activity
pipeline = (
    Agent("extractor", "gemini-2.5-flash")
    .instruct("Extract entities from the document.").writes("entities")
    >> Agent("enricher", "gemini-2.5-flash")
    .instruct("Enrich {entities} with additional context.").writes("enriched")
    >> Agent("analyzer", "gemini-2.5-flash")
    .instruct("Analyze {enriched} for risks.").writes("analysis")
    >> Agent("reporter", "gemini-2.5-flash")
    .instruct("Write a risk report from {analysis}.")
)

pipeline = pipeline.engine("temporal", client=client, task_queue="docs")
```

If the process crashes after step 2 (enricher), Temporal replays:
- extractor → cached result (0 LLM cost)
- enricher → cached result (0 LLM cost)
- analyzer → **re-executes** (LLM call)
- reporter → **executes** (LLM call)

### Parallel research with durability

```python
from adk_fluent import Agent, S

research = (
    (
        Agent("web", "gemini-2.5-flash").instruct("Search the web.").writes("web_results")
        | Agent("papers", "gemini-2.5-flash").instruct("Search papers.").writes("paper_results")
    )
    >> S.merge("web_results", "paper_results", into="research")
    >> Agent("synthesizer", "gemini-2.5-flash")
    .instruct("Synthesize {research} into a report.")
)

research = research.engine("temporal", client=client, task_queue="research")
```

The parallel branches run as concurrent activities. If one fails, Temporal retries it without affecting the other.

### Review loop with checkpointing

```python
from adk_fluent import Agent, until

loop = (
    Agent("writer", "gemini-2.5-flash")
    .instruct("Write or revise the draft.").writes("draft")
    >> Agent("critic", "gemini-2.5-flash")
    .instruct("Score the draft 0-10.").writes("score")
) * until(lambda s: int(s.get("score", 0)) >= 8, max=5)

loop = loop.engine("temporal", client=client, task_queue="quality")
```

Each iteration is checkpointed. If the process crashes mid-loop, Temporal replays completed iterations from cache and continues from the last checkpoint.

### Fallback across models

```python
from adk_fluent import Agent

answer = (
    Agent("fast", "gemini-2.0-flash").instruct("Quick answer.")
    // Agent("thorough", "gemini-2.5-pro").instruct("Detailed answer.")
)

answer = answer.engine("temporal", client=client, task_queue="qa")
```

If the fast model fails (timeout, error), Temporal catches the exception and tries the thorough model. Both attempts are activities — the fast model's failure is recorded in history.

## Constraints and Limitations

### Streaming is not supported

Temporal workflows return results, not streams. `.stream()` falls back to collecting all events and yielding them at once:

```python
# This works but doesn't actually stream — waits for full completion
async for chunk in pipeline.stream("prompt"):
    print(chunk, end="")
```

For streaming UIs, use the ADK backend. For durable pipelines, use Temporal with `.ask_async()`.

### Sessions require external state

Temporal activities are stateless. Multi-turn `.session()` requires explicit state management:

```python
# Instead of .session(), use .ask_async() with explicit state passing
# State is managed by Temporal's workflow history
response = await pipeline.ask_async("first question")
# The pipeline's state is preserved in Temporal history
```

### All builders work, but execution semantics differ

Every adk-fluent builder, operator, and namespace module works with Temporal. The *definition* is identical. What changes is the *execution*:

| Feature | ADK | Temporal |
|---------|-----|---------|
| `.ask()` (sync) | Works | Not recommended (blocks) |
| `.ask_async()` | Works | Works (starts workflow) |
| `.stream()` | Real streaming | Falls back to batch |
| `.session()` | In-memory history | Requires external state |
| `.map_async()` | Concurrent tasks | Each prompt = workflow |
| State transforms | Inline | Deterministic replay |
| Middleware | ADK plugins | Runtime hooks |

## Worker Setup

For the Temporal backend to execute workflows, you need a running worker:

```python
from adk_fluent.backends.temporal_worker import create_worker

async def main():
    client = await Client.connect("localhost:7233")
    worker = await create_worker(client, task_queue="agents")
    await worker.run()
```

The worker registers the generic `adk_fluent_agent_workflow` and its activities with Temporal. Multiple workers can run on different machines for horizontal scaling.

## Comparison: When to Use What

| Scenario | Use ADK | Use Temporal |
|----------|---------|-------------|
| Quick prototype | Yes | No |
| Short-lived agent (< 1 min) | Yes | Overkill |
| Multi-step pipeline (minutes) | Maybe | Yes |
| Must survive crashes | No | Yes |
| Real-time streaming UI | Yes | No |
| Multi-turn chat session | Yes | Not ideal |
| Batch processing (1000 prompts) | Yes | Yes (each = workflow) |
| Human approval step | No | Yes (signals) |
| Distributed across machines | No | Yes |

:::{seealso}
- [Execution Backends](execution-backends.md) — overview of all backends and selection guide
- [IR & Backends](ir-and-backends.md) — IR node types and the compilation pipeline
- [Execution](execution.md) — `.ask()`, `.stream()`, `.session()` execution methods
- [Patterns](patterns.md) — higher-order patterns that compose well with Temporal
:::
