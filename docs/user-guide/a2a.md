# A2A (Agent-to-Agent)

The A2A module lets your agents communicate with remote agents over the [A2A protocol](https://github.com/google/A2A). You can consume remote agents as first-class builders, publish your agents as A2A servers, and compose local and remote agents freely using all adk-fluent operators.

:::{tip}
**Visual learner?** Open the [A2A Topology Interactive Reference](../a2a-topology-reference.html){target="_blank"} for animated mesh topology diagrams, state bridging flow, and resilience middleware patterns.
:::

:::{admonition} Experimental
:class: warning
A2A support is experimental. The underlying `google-adk` A2A APIs are marked `@a2a_experimental` and may change without notice. Install with:

```bash
pip install adk-fluent[a2a]
```
:::

## Overview

A2A in adk-fluent has four parts:

| Component | Purpose |
|---|---|
| **RemoteAgent** | Consume a remote A2A agent -- use it like any other builder |
| **A2AServer** | Publish a local agent as an A2A server |
| **A2A Middleware** | Resilience patterns: retry, circuit breaker, timeout |
| **A2A Patterns** | Higher-order compositions: cascade, fan-out, delegate |

The key idea: `RemoteAgent` extends `BuilderBase`, so every operator works -- `>>`, `|`, `//`, `*`. You mix local and remote agents freely in the same expression.

## Consuming Remote Agents

### Basic Usage

```python
from adk_fluent import Agent, RemoteAgent

# Point at a running A2A server
remote = RemoteAgent("researcher", "http://researcher:8001")

# Use it exactly like a local agent
pipeline = Agent("coordinator", "gemini-2.5-flash").instruct("Classify.") >> remote
```

`RemoteAgent` accepts the agent card URL as the second argument. By convention, the A2A server publishes its agent card at `/.well-known/agent.json`, so you only need the base URL.

### Configuration

```python
remote = (
    RemoteAgent("researcher", "http://researcher:8001")
    .describe("Remote research specialist")  # metadata for routing
    .timeout(30)                              # HTTP timeout in seconds
    .streaming(True)                          # prefer streaming transport
    .full_history(True)                       # send full conversation to stateless agents
)
```

| Method | Default | Purpose |
|---|---|---|
| `.describe(text)` | `""` | Description for transfer routing (helps coordinator LLMs pick the right specialist) |
| `.timeout(seconds)` | `600` | HTTP timeout for the remote call |
| `.streaming(enabled)` | `False` | Prefer SSE streaming for long-running calls |
| `.full_history(enabled)` | `False` | Send full conversation history (for stateless remote agents) |

### Agent Card Sources

You can provide the agent card in several ways:

```python
# Base URL (appends /.well-known/agent.json)
remote = RemoteAgent("r", "http://researcher:8001")

# Explicit card URL
remote = RemoteAgent("r").card_url("http://researcher:8001/.well-known/agent.json")

# Load from local file
remote = RemoteAgent("r").card_path("./cards/researcher.json")

# From an AgentCard object
remote = RemoteAgent("r").card(my_agent_card)

# From environment variable
remote = RemoteAgent("r", env="RESEARCHER_AGENT_URL")
```

### Discovery

Two discovery mechanisms are built in:

**DNS well-known discovery** -- derive the agent card URL from a domain:

```python
remote = RemoteAgent.discover("researcher", "research.agents.acme.com")
# Resolves to: https://research.agents.acme.com/.well-known/agent.json
```

**Registry-based discovery** -- query a central registry service:

```python
from adk_fluent import AgentRegistry

registry = AgentRegistry("http://registry.internal:9000")
remote = registry.find("research", skill="academic-research")

# List all registered agents
agents = await registry.list_agents()
```

The registry uses a convention-based REST API:
- `GET /agents` -- list all
- `GET /agents?skill=x` -- filter by skill
- `GET /agents?tag=x` -- filter by tag
- `GET /agents/{name}` -- get by name

---

## State Bridging

When local and remote agents need to exchange data through session state, use `.sends()` and `.receives()` to declare the data flow:

```python
remote = (
    RemoteAgent("researcher", "http://researcher:8001")
    .sends("query", "context")       # local state keys → A2A message
    .receives("findings", "score")   # A2A response → local state keys
)
```

**How it works:**

1. **Before the remote call:** `.sends()` keys are extracted from local state and injected into the A2A request
2. **After the remote call:** `.receives()` keys are extracted from the A2A response and written back to local state

This means a remote agent participates in the same data flow as local agents:

```python
pipeline = (
    Agent("planner", "gemini-2.5-flash")
    .instruct("Create a research plan.")
    .writes("plan")
    >> RemoteAgent("researcher", "http://researcher:8001")
    .sends("plan")
    .receives("findings")
    >> Agent("writer", "gemini-2.5-flash")
    .instruct("Synthesize the findings: {findings}")
)
```

### Persistent Context

For multi-turn conversations with a remote agent, enable persistent context to maintain the A2A `contextId` across calls:

```python
remote = (
    RemoteAgent("assistant", "http://assistant:8001")
    .persistent_context()             # maintain contextId in state
    .context_key("_my_ctx_key")       # optional: custom state key
)
```

The `contextId` is stored in session state (default key: `_a2a_context_{agent_name}`) and reused on subsequent calls within the same session.

---

## Publishing Agents (A2AServer)

### Basic Server

Turn any agent into an A2A server:

```python
from adk_fluent import Agent, A2AServer

researcher = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("You are a research specialist. Provide thorough, cited answers.")
    .tool(web_search)
)

app = A2AServer(researcher).port(8001).build()
```

The return value is a Starlette ASGI application. Run it with any ASGI server:

```bash
uvicorn my_module:app --port 8001
```

The agent card is auto-generated and served at `http://localhost:8001/.well-known/agent.json`.

### Full Configuration

```python
app = (
    A2AServer(researcher)
    .host("0.0.0.0")                 # bind address (default)
    .port(8001)                       # port number
    .version("1.0.0")                 # version in agent card
    .provider("Acme Corp", "https://acme.com")  # organization info
    .streaming(True)                  # enable streaming support
    .push_notifications(True)         # enable push notifications
    .docs("https://acme.com/docs")    # documentation URL
    .health_check()                   # add /health endpoints
    .graceful_shutdown(timeout=30)    # drain tasks before stopping
    .build()
)
```

### Declaring Skills

Skills describe what your agent can do. They appear in the agent card and help clients understand capabilities:

```python
app = (
    A2AServer(researcher)
    .port(8001)
    .skill(
        "research",                     # skill ID
        "Academic Research",            # display name
        description="Deep research with citations and source verification",
        tags=["research", "academic", "citations"],
        examples=[
            "Find recent papers on transformer architectures",
            "What are the latest advances in quantum computing?",
        ],
    )
    .skill(
        "summarize",
        "Document Summarization",
        description="Summarize long documents into key points",
        tags=["summarize", "extraction"],
    )
    .build()
)
```

You can also declare skills directly on the Agent builder using `.skill()` -- they are picked up automatically by `A2AServer`:

```python
researcher = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("You are a research specialist.")
    .tool(web_search)
    .skill("research", "Academic Research",
           description="Deep research with citations",
           tags=["research", "citations"])
)

# A2AServer picks up the skill from the agent
app = A2AServer(researcher).port(8001).build()
```

### Health Checks

`.health_check()` adds two endpoints:

| Endpoint | Purpose | Response |
|---|---|---|
| `GET /health` | Liveness probe (always 200) | `{"status": "ok", "agent": "name"}` |
| `GET /health/ready` | Readiness probe | `{"status": "ready"}` (200) or 503 if not ready |

---

## Operator Composition

`RemoteAgent` participates in all expression operators:

```python
from adk_fluent import Agent, RemoteAgent

remote = RemoteAgent("researcher", "http://researcher:8001")

# Sequential pipeline
pipeline = Agent("classifier") >> remote >> Agent("writer")

# Parallel fan-out
parallel = remote | Agent("local_search")

# Fallback -- try remote first, fall back to local
fallback = remote.timeout(10) // Agent("local", "gemini-2.5-flash").instruct("Answer locally.")

# Loop -- remote reviewer in a refinement loop
loop = (Agent("writer") >> remote) * 3

# Conditional loop
from adk_fluent import until
loop = (Agent("writer") >> remote) * until(lambda s: s.get("approved"), max=5)
```

### Sub-agent Delegation

Use `RemoteAgent` as a transfer target:

```python
coordinator = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct("Route research questions to the specialist. Handle casual questions yourself.")
    .sub_agent(
        RemoteAgent("researcher", "http://researcher:8001")
        .describe("Remote research specialist for deep questions")
    )
    .build()
)
```

### Tool-based Invocation

Wrap a remote agent as a tool with `T.a2a()`:

```python
from adk_fluent import Agent, T

agent = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct("Use the research tool for deep questions.")
    .tools(T.a2a(
        "http://research:8001",
        name="deep_research",
        description="Deep research tool with citations"
    ))
    .build()
)
```

The difference: `T.a2a()` wraps the remote agent as an `AgentTool`. The parent LLM stays in control and can call multiple remote agents in a single turn. Compare with `.sub_agent()` which fully transfers control.

---

## A2A Middleware

Three middleware factories in the M module handle resilience for remote agents:

### Retry

```python
from adk_fluent import M

pipeline = (Agent("a") >> remote).middleware(
    M.a2a_retry(max_attempts=3, backoff=2.0)
)
```

Handles A2A-specific failures: HTTP transport errors, `FAILED`/`REJECTED` task states, and network transients. Uses exponential backoff.

| Parameter | Default | Purpose |
|---|---|---|
| `max_attempts` | `3` | Number of retry attempts |
| `backoff` | `2.0` | Base delay for exponential backoff |
| `agents` | all | Scope to specific agent names |
| `on_retry` | `None` | Callback `(ctx, agent_name, attempt, error)` |

### Circuit Breaker

```python
pipeline = (Agent("a") >> remote).middleware(
    M.a2a_circuit_breaker(threshold=5, reset_after=60)
)
```

Tracks failures per remote agent. After `threshold` failures, the circuit opens and fast-fails immediately (raises `A2ACircuitOpenError`). After `reset_after` seconds, it enters half-open state and probes with one request.

| Parameter | Default | Purpose |
|---|---|---|
| `threshold` | `5` | Failures before opening |
| `reset_after` | `60` | Seconds before half-open probe |
| `agents` | all | Scope to specific agent names |
| `on_open` | `None` | Callback `(ctx, agent_name)` when circuit opens |
| `on_close` | `None` | Callback `(ctx, agent_name)` when circuit closes |

**States:** `CLOSED` (normal) → `OPEN` (fast-fail) → `HALF_OPEN` (probe) → `CLOSED`

### Timeout

```python
pipeline = (Agent("a") >> remote).middleware(
    M.a2a_timeout(seconds=30)
)
```

Wall-clock timeout for the entire agent invocation. Critical for remote calls where network latency can be unpredictable.

| Parameter | Default | Purpose |
|---|---|---|
| `seconds` | `30` | Maximum seconds per invocation |
| `agents` | all | Scope to specific agent names |
| `on_timeout` | `None` | Callback `(ctx, agent_name, seconds)` |

### Composing Resilience Stacks

Combine middleware for production-grade resilience:

```python
resilience = (
    M.a2a_retry(max_attempts=3, backoff=2.0)
    | M.a2a_circuit_breaker(threshold=5, reset_after=60)
    | M.a2a_timeout(seconds=30)
)

pipeline = (Agent("a") >> remote).middleware(resilience)
```

Scope middleware to specific agents with `M.scope()`:

```python
stack = (
    M.scope("remote_*", M.a2a_retry(3))
    | M.a2a_timeout(seconds=30)
    | M.log()
)
```

---

## A2A Composition Patterns

Three higher-order patterns in `adk_fluent.patterns` simplify common A2A topologies:

### `a2a_cascade` -- Fallback Chain

Try remote agents in order. First success wins:

```python
from adk_fluent.patterns import a2a_cascade

fallback = a2a_cascade(
    "http://fast-model:8001",
    "http://accurate-model:8002",
    "http://fallback-model:8003",
    names=["fast", "accurate", "fallback"],
    timeout=300.0,
)
```

```
  ┌──────┐     fail     ┌──────────┐     fail     ┌──────────┐
  │ fast │────────────►  │ accurate │────────────►  │ fallback │
  └──────┘               └──────────┘               └──────────┘
      │ ok                   │ ok                       │ ok
      ▼                      ▼                          ▼
   response              response                   response
```

### `a2a_fanout` -- Parallel Fan-Out

Run all remote agents concurrently:

```python
from adk_fluent.patterns import a2a_fanout

parallel = a2a_fanout(
    "http://web-search:8001",
    "http://paper-search:8002",
    "http://patent-search:8003",
    names=["web", "papers", "patents"],
)
```

### `a2a_delegate` -- Coordinator with Remote Specialists

A local coordinator agent with named remote specialists as sub-agents. The coordinator LLM decides which specialist to delegate to:

```python
from adk_fluent.patterns import a2a_delegate

coordinator = a2a_delegate(
    Agent("coordinator", "gemini-2.5-flash")
    .instruct("Route tasks to the right specialist based on the user's request."),
    research="http://research:8001",
    writing="http://writing:8002",
    analysis="http://analysis:8003",
)
```

---

## Complete Examples

### Research Pipeline (Local + Remote)

A classifier routes to either a remote researcher or a local general agent:

```python
from adk_fluent import Agent, RemoteAgent, Route, M

research = (
    RemoteAgent("researcher", "http://researcher:8001")
    .describe("Remote research specialist for deep questions")
    .timeout(30)
    .sends("query")
    .receives("findings")
)

pipeline = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the user request as 'research' or 'general'. Output one word.")
    .writes("intent")
    >> Route("intent")
        .eq("research", research)
        .otherwise(
            Agent("general", "gemini-2.5-flash")
            .instruct("Answer the question directly.")
        )
).middleware(
    M.a2a_retry(max_attempts=3) | M.a2a_timeout(seconds=30) | M.log()
)
```

### Publishing with Full Configuration

```python
from adk_fluent import Agent, A2AServer

def web_search(query: str) -> str:
    """Search the web for information."""
    return f"Search results for: {query}"

researcher = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct(
        "You are a research specialist. Provide thorough, "
        "well-cited answers to research questions."
    )
    .tool(web_search)
)

app = (
    A2AServer(researcher)
    .port(8001)
    .version("1.0.0")
    .provider("Research Lab", "https://research-lab.example.com")
    .streaming(True)
    .skill(
        "research", "Academic Research",
        description="Deep research with citations",
        tags=["research", "academic"],
        examples=["Find recent papers on transformer architectures"],
    )
    .health_check()
    .graceful_shutdown(timeout=30)
    .build()
)

# Run: uvicorn my_module:app --port 8001
```

### Hybrid Topology with Resilience

```python
from adk_fluent import Agent, RemoteAgent, M
from adk_fluent.patterns import a2a_cascade, fan_out_merge

# Remote agents with fallback
researcher = a2a_cascade(
    "http://fast-research:8001",
    "http://thorough-research:8002",
    names=["fast", "thorough"],
)

# Mixed local/remote fan-out
results = fan_out_merge(
    RemoteAgent("web", "http://web:8001").writes("web_results"),
    Agent("db", "gemini-2.5-flash").instruct("Query internal DB.").writes("db_results"),
    merge_key="all_results",
)

# Full pipeline with resilience
pipeline = (
    Agent("planner", "gemini-2.5-flash").instruct("Create a research plan.").writes("plan")
    >> results
    >> Agent("writer", "gemini-2.5-flash").instruct("Synthesize {all_results} into a report.")
).middleware(
    M.a2a_retry(3) | M.a2a_circuit_breaker(5) | M.a2a_timeout(30) | M.log()
)
```

---

## Native ADK Comparison

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, RemoteAgent, A2AServer

# Consume
remote = RemoteAgent("helper", "http://helper:8001").timeout(30)
pipeline = Agent("coordinator") >> remote

# Publish
app = (
    A2AServer(my_agent)
    .port(8001)
    .skill("research", "Research", description="Deep research")
    .health_check()
    .build()
)
```
:::
:::{tab-item} Native ADK
```python
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from a2a.client import A2ACardResolver
from a2a.types import AgentCard
import httpx

# Consume -- manual card resolution
resolver = A2ACardResolver(httpx.AsyncClient())
card = await resolver.get_agent_card("http://helper:8001/.well-known/agent.json")
remote = RemoteA2aAgent(name="helper", agent_card=card)

# Publish -- manual server setup with a2a-sdk
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.types import AgentCard, AgentCapabilities, AgentSkill, AgentProvider

card = AgentCard(
    name="researcher",
    description="Research specialist",
    url="http://localhost:8001",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=False),
    skills=[AgentSkill(id="research", name="Research", description="Deep research")],
    defaultInputModes=["text/plain"],
    defaultOutputModes=["text/plain"],
)
executor = A2aAgentExecutor(agent=my_agent, card=card)
handler = DefaultRequestHandler(agent_executor=executor)
app = A2AStarletteApplication(agent_card=card, http_handler=handler)
```
:::
::::

## Tips

- **Always set `.describe()` on `RemoteAgent`** when using it as a sub-agent. The description helps the coordinator LLM pick the right specialist for transfer routing.
- **Use `.timeout()` on remote agents.** Network calls can hang -- always set a reasonable timeout.
- **Combine resilience middleware for production.** At minimum use `M.a2a_retry()` and `M.a2a_timeout()`. Add `M.a2a_circuit_breaker()` for services with known instability.
- **Use `T.a2a()` when the parent should stay in control.** For orchestrating multiple remote calls in a single turn, `T.a2a()` is better than `.sub_agent()`.
- **Use `a2a_cascade()` for model fallback chains.** Try a fast model first, fall back to a more accurate one.
- **Use environment variables for deployment.** `RemoteAgent("r", env="AGENT_URL")` lets you configure endpoints per environment without code changes.
- **Test with `.mock()` first.** Mock remote agents locally before connecting to real services.
