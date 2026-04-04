# A2A -- Agent-to-Agent Communication

The **A2A (Agent-to-Agent)** protocol enables agents to communicate across process boundaries, machines, and organizations. adk-fluent wraps Google's A2A protocol with the same fluent builder API used for local agents.

:::{tip}
**Visual learner?** Open the [A2A Topology Interactive Reference](../a2a-topology-reference.html){target="_blank"} for mesh topology diagrams, state bridging flows, resilience patterns, and discovery methods.
:::

:::{admonition} Install
:class: tip

A2A requires the optional `a2a` extra:

```bash
pip install adk-fluent[a2a]
```

This installs `google-adk[a2a]` which provides the A2A protocol implementation.
:::

## Architecture

```
┌─────────────────────┐   A2A Protocol    ┌─────────────────────┐
│ Local Agent         │  (JSON over HTTP)  │ Remote Agent        │
│                     │ ◄───────────────►  │                     │
│ RemoteAgent(        │                    │ A2AServer(          │
│   "researcher",     │                    │   my_agent          │
│   agent_card=url    │                    │ ).port(8001)        │
│ )                   │                    │  .skill("research") │
└─────────────────────┘                    └─────────────────────┘
```

**Two builders:**

| Builder | Role | Description |
|---------|------|-------------|
| `RemoteAgent` | Consumer | Call a remote A2A agent as if it were local |
| `A2AServer` | Publisher | Expose a local agent via A2A protocol |

## RemoteAgent -- Consuming Remote Agents

```python
from adk_fluent import RemoteAgent

remote = (
    RemoteAgent("researcher", agent_card="http://researcher:8001/.well-known/agent.json")
    .describe("Remote research specialist")
    .timeout(30)
    .sends("query")           # serialize state keys into A2A message
    .receives("findings")     # deserialize A2A response back into state
    .persistent_context()     # maintain contextId across calls in same session
)
```

### In Pipelines

`RemoteAgent` extends `BuilderBase` -- all operators work:

```python
from adk_fluent import Agent

# Sequential pipeline with remote agent
pipeline = Agent("writer") >> remote >> Agent("reviewer")

# Fallback to local if remote fails
fallback = remote // Agent("local-fallback", "gemini-2.5-flash")

# Parallel fan-out
fanout = remote | Agent("local-search", "gemini-2.5-flash")
```

### Discovery

```python
# DNS well-known discovery
remote = RemoteAgent.discover("research-agent.agents.acme.com")

# Environment variable
remote = RemoteAgent("code", env="CODE_AGENT_URL")

# Registry-based
from adk_fluent import AgentRegistry
registry = AgentRegistry("http://registry:9000")
remote = registry.find(name="research")
```

## A2AServer -- Publishing Local Agents

```python
from adk_fluent import A2AServer

server = (
    A2AServer(my_agent)
    .port(8001)
    .version("1.0.0")
    .provider("Acme Corp", "https://acme.com")
    .skill("research", "Academic Research",
           description="Deep research with citations",
           tags=["research", "citations"])
    .health_check()
    .graceful_shutdown(timeout=30)
)
```

### A2UI Extension

Declare A2UI capabilities in the AgentCard:

```python
server = (
    A2AServer(my_agent)
    .port(8001)
    .ui(catalogs=["https://a2ui.org/specification/v0_10/basic_catalog.json"])
)
# Adds a2ui extension metadata to the .well-known/agent.json
```

## A2A Middleware

Resilience patterns for remote communication:

```python
from adk_fluent._middleware import M

# Retry with exponential backoff
pipeline.middleware(M.a2a_retry(max_attempts=3, backoff=2.0))

# Circuit breaker (fail fast after threshold)
pipeline.middleware(M.a2a_circuit_breaker(threshold=5, reset_after=60))

# Per-agent timeout
pipeline.middleware(M.a2a_timeout(seconds=30))
```

## A2A Tool Composition

Wrap a remote agent as a tool the LLM can call:

```python
from adk_fluent import T

agent = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct("Use the research tool for academic queries.")
    .tools(T.a2a("http://researcher:8001/.well-known/agent.json",
                  name="research", description="Academic research"))
)
```

## Composition Patterns

### Cascade (Fallback Chain)

```python
from adk_fluent.patterns import a2a_cascade

# Try agents in order, fall back on failure
pipeline = a2a_cascade(
    "http://fast-agent:8001/.well-known/agent.json",
    "http://strong-agent:8002/.well-known/agent.json",
    names=["fast", "strong"],
    timeout=30,
)
```

### Fan-Out (Parallel)

```python
from adk_fluent.patterns import a2a_fanout

# Query multiple remote agents in parallel
pipeline = a2a_fanout(
    "http://web-search:8001/.well-known/agent.json",
    "http://paper-search:8002/.well-known/agent.json",
    names=["web", "papers"],
)
```

### Delegate (Coordinator with Specialists)

```python
from adk_fluent.patterns import a2a_delegate

# Coordinator routes to named remote specialists
pipeline = a2a_delegate(
    Agent("coordinator", "gemini-2.5-flash").instruct("Route queries."),
    research="http://research:8001/.well-known/agent.json",
    code="http://code:8002/.well-known/agent.json",
)
```

## State Bridging

Control what data flows between local and remote agents:

```python
remote = (
    RemoteAgent("analyst", agent_card=url)
    .sends("query", "context")      # state keys → A2A message
    .receives("analysis", "score")   # A2A response → state keys
)
```

Keys listed in `.sends()` are serialized into the A2A `message.text` (or parts). Keys listed in `.receives()` are extracted from the response and written to state.

## Graceful Degradation

When `google-adk[a2a]` is not installed:

- `RemoteAgent`, `A2AServer`, `AgentRegistry` raise `ImportError` with install instructions
- A2A middleware (`M.a2a_retry`, etc.) raises `ImportError`
- Local agent features, UI composition, and all other namespaces work normally

```python
try:
    from adk_fluent import RemoteAgent
except ImportError:
    # pip install adk-fluent[a2a]
    pass
```
