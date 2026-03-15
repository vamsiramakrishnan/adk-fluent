# A2A (Agent-to-Agent) Protocol Integration for adk-fluent

## Research Summary

This document analyzes how Google's ADK implements A2A protocol support and proposes
a seamless fluent builder approach for adk-fluent.

---

## 1. What Is A2A?

The **Agent-to-Agent (A2A)** protocol is an open standard (Apache 2.0, now under
Linux Foundation) for inter-agent communication. It complements MCP:

| | MCP | A2A |
|---|---|---|
| **Purpose** | Tool invocation | Agent collaboration |
| **Paradigm** | Structured I/O | Opaque autonomous tasks |
| **Transport** | stdio / HTTP | HTTP + JSON-RPC 2.0 / gRPC |
| **Discovery** | Tool schemas | `/.well-known/agent.json` |

**Core concepts:**
- **AgentCard** — discovery document at `/.well-known/agent.json`
- **AgentSkill** — capability declaration (id, name, description, tags, examples)
- **Task** — unit of work with lifecycle states (WORKING → COMPLETED/FAILED/CANCELED)
- **Message / Part** — content exchange (TextPart, FilePart, DataPart)
- **Streaming** — SSE for real-time task updates
- **Push notifications** — webhook-based async updates

**Protocol methods (JSON-RPC 2.0):**
- `SendMessage` — initiate/continue a task
- `SendStreamingMessage` — send + subscribe to SSE stream
- `GetTask` / `ListTasks` — query task status
- `CancelTask` — cancel running task
- `SubscribeToTask` — reconnect to active stream
- Push notification CRUD methods

---

## 2. How ADK-Python Implements A2A Today

### 2.1 Module Layout

```
src/google/adk/a2a/
  executor/a2a_agent_executor.py     # Server-side executor
  utils/agent_card_builder.py        # Auto-generates AgentCard
  utils/agent_to_a2a.py             # to_a2a() convenience function
  converters/                        # ADK Event ↔ A2A Message converters
  agent/config.py                    # A2aRemoteAgentConfig
  agent/interceptors/                # Before/after hooks

src/google/adk/agents/
  remote_a2a_agent.py               # Client-side proxy agent
```

All marked `@a2a_experimental` — subject to breaking changes.

### 2.2 Server Side: Exposing an Agent via A2A

**Current ADK approach (boilerplate-heavy):**

```python
from google.adk.a2a.utils.agent_to_a2a import to_a2a

# Option 1: to_a2a() convenience function
app = to_a2a(
    agent=root_agent,
    host="0.0.0.0",
    port=8001,
    agent_card=None,  # auto-generated from agent metadata
)
# Run with: uvicorn module:app --port 8001

# Option 2: CLI
# adk api_server --a2a --port 8001 agents_dir/
```

**What `to_a2a()` does internally:**
1. Creates `InMemoryTaskStore` + `InMemoryPushNotificationConfigStore`
2. Wraps agent in `A2aAgentExecutor` (creates Runner with in-memory services)
3. Passes executor to `DefaultRequestHandler` (JSON-RPC dispatch)
4. Uses `AgentCardBuilder` to auto-generate `AgentCard` from agent metadata
5. Creates `A2AStarletteApplication` with `/.well-known/agent.json` endpoint
6. Returns Starlette ASGI app

**AgentCardBuilder** auto-extracts:
- Skills from LLM agents (model, tools, planner, code executor)
- Sub-agent hierarchies (recursive)
- Examples from `ExampleTool` or instruction text
- Input/output mode detection

### 2.3 Client Side: Consuming a Remote A2A Agent

```python
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

remote = RemoteA2aAgent(
    name="helper",
    description="Does specialized work.",
    agent_card="http://remote:8001/.well-known/agent.json",
    # Also accepts: AgentCard object or file path
    timeout=600.0,
)

# Used as a regular sub-agent — parent LLM delegates naturally
orchestrator = Agent(
    model="gemini-2.0-flash",
    name="orchestrator",
    instruction="Delegate specialized tasks to helper.",
    sub_agents=[remote],
)
```

**Key insight:** `RemoteA2aAgent` extends `BaseAgent`, NOT a tool. The parent
LLM treats it identically to a local sub-agent. Network communication,
serialization, and card resolution are fully abstracted.

There is **no `A2aTool`** in ADK — client consumption is agent-based, not tool-based.

### 2.4 AgentCard Structure

```json
{
  "name": "Research Assistant",
  "description": "Helps with academic research",
  "url": "http://localhost:8001/a2a",
  "version": "1.0.0",
  "protocolVersion": "0.3",
  "skills": [
    {
      "id": "academic-research",
      "name": "Academic Research",
      "description": "Research with citations",
      "tags": ["research", "citations"],
      "examples": ["Find articles on climate change"],
      "inputModes": ["text/plain"],
      "outputModes": ["text/plain"]
    }
  ],
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": false
  },
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "provider": {
    "organization": "Acme Corp",
    "url": "https://acme.com"
  },
  "securitySchemes": { ... },
  "supportedInterfaces": [
    { "transport": "JSONRPC", "url": "http://localhost:8001/a2a" }
  ]
}
```

### 2.5 Dependencies

ADK A2A requires: `pip install google-adk[a2a]`

Key SDK types from `a2a-python`: `A2AStarletteApplication`, `DefaultRequestHandler`,
`InMemoryTaskStore`, `AgentCard`, `AgentSkill`, `A2AClient`, `Message`, `TaskState`.

---

## 3. Current adk-fluent State

### What exists:
- Local agent delegation via `.agent_tool(agent)` — wraps agent as callable tool
- `AgentTool` builder in `tool.py` (auto-generated)
- Runtime builders (`App`, `Runner`, `InMemoryRunner`) — execution only, no A2A
- Service builders for sessions, memory, artifacts — but no A2A service

### What's missing:
- No `RemoteA2aAgent` builder (remote agent consumption)
- No A2A server/service builder (agent publishing)
- No AgentCard configuration API
- No A2A-aware patterns or routing
- No A2A entries in codegen manifest/seeds

---

## 4. Proposed Fluent API Design

### Design Principles

1. **Zero boilerplate** — publishing should be 1-2 lines, consuming 1 line
2. **Symmetry** — publishing and consuming feel like mirror operations
3. **Composable** — A2A agents participate in all existing operators (`>>`, `|`, `*`, `//`)
4. **Progressive disclosure** — simple cases are trivial, complex cases are possible
5. **Auto-inference** — AgentCard generated from existing builder metadata
6. **Native fit** — follows established builder patterns, namespaces, and IR

### 4.1 Consuming Remote A2A Agents (Client Side)

**The simplest possible API:**

```python
from adk_fluent import Agent, RemoteAgent

# One-liner: consume a remote A2A agent
remote = RemoteAgent("helper", "http://remote:8001")

# Use in any composition — identical to local agents
pipeline = Agent("coordinator", "gemini-2.5-flash") \
    .instruct("Route research tasks to helper.") \
    .sub_agent(remote) \
    .build()

# Works with all operators
pipeline = Agent("local") >> remote >> Agent("reviewer")
fanout   = remote | Agent("local-backup")
fallback = remote // Agent("local-fallback")
```

**Builder methods for RemoteAgent:**

```python
remote = (
    RemoteAgent("helper", "http://remote:8001")
    .describe("Specialized research agent")       # override card description
    .timeout(300)                                   # HTTP timeout
    .card(agent_card_obj)                           # explicit AgentCard object
    .card_path("/path/to/agent-card.json")          # load from file
    .auth(bearer="token")                           # authentication
    .auth(oauth=OAuthConfig(...))                   # OAuth2
    .auth(api_key="key", header="X-API-Key")        # API key
    .streaming(True)                                # prefer streaming
    .full_history(True)                             # send full history
)
```

**Under the hood:** Wraps `google.adk.agents.remote_a2a_agent.RemoteA2aAgent`.
The URL can be:
- Full card URL: `http://host:port/.well-known/agent.json`
- Base URL: `http://host:port` (auto-appends `/.well-known/agent.json`)

### 4.2 Publishing Agents via A2A (Server Side)

**The simplest possible API:**

```python
from adk_fluent import Agent, A2AServer

# Build your agent normally
agent = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research topics thoroughly.")
    .tool(web_search)
    .skill("research", "Academic Research", tags=["research"])  # NEW: A2A skill metadata
    .build()
)

# One-liner: publish as A2A server
app = A2AServer(agent).build()
# Run with: uvicorn module:app --port 8001
```

**Progressive complexity:**

```python
# Simple — auto-infer everything
app = A2AServer(agent).build()

# Medium — customize card metadata
app = (
    A2AServer(agent)
    .port(8001)
    .version("1.0.0")
    .provider("Acme Corp", "https://acme.com")
    .streaming(True)
    .push_notifications(True)
    .docs("https://docs.acme.com/research")
    .build()
)

# Advanced — full card control + auth + task store
app = (
    A2AServer(agent)
    .port(8001)
    .version("2.0.0")
    .provider("Acme Corp", "https://acme.com")
    .streaming(True)
    .auth_scheme("bearer", SecurityScheme(...))
    .task_store(my_redis_task_store)
    .push_store(my_push_config_store)
    .runner(custom_runner)
    .card(explicit_agent_card)            # bypass auto-generation
    .build()
)
```

### 4.3 Agent Skill Metadata (New Builder Method)

The `.skill()` method on Agent adds A2A skill metadata that `A2AServer` uses
for card generation:

```python
agent = (
    Agent("assistant", "gemini-2.5-flash")
    .instruct("Multi-capable assistant.")
    .tool(search_fn)
    .tool(email_fn)
    # Declare A2A skills (optional — auto-inferred if omitted)
    .skill("search", "Web Search",
           description="Search the web for information",
           tags=["search", "web"],
           examples=["Find the latest news on AI"])
    .skill("email", "Email Drafting",
           description="Draft professional emails",
           tags=["email", "writing"])
    .build()
)
```

If no `.skill()` calls are made, `AgentCardBuilder` auto-extracts skills from
the agent's tools, sub-agents, and instruction text (existing ADK behavior).

### 4.4 The `.publish()` Shorthand

For maximum brevity, add `.publish()` directly on Agent:

```python
# Ultra-concise: build + publish in one chain
app = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research topics.")
    .tool(web_search)
    .publish(port=8001)  # Returns Starlette app directly
)

# Equivalent to:
agent = Agent("researcher", "gemini-2.5-flash").instruct("...").tool(web_search)
app = A2AServer(agent).port(8001).build()
```

### 4.5 The `.remote()` Static Constructor

Alternative ergonomic entry point on Agent itself:

```python
# These are equivalent:
remote = RemoteAgent("helper", "http://remote:8001")
remote = Agent.remote("helper", "http://remote:8001")
```

### 4.6 T Namespace Extensions

For tool-centric usage patterns:

```python
# Add a remote A2A agent as a tool (AgentTool wrapping RemoteA2aAgent)
agent = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct("Use the research tool for deep research.")
    .tools(T.a2a("http://research:8001", name="research_tool"))
    .build()
)
```

### 4.7 Multi-Agent A2A Server

Serve multiple agents from one server:

```python
app = (
    A2AServer()
    .agent(researcher, path="/research")
    .agent(writer, path="/writing")
    .agent(analyst, path="/analysis")
    .port(8001)
    .build()
)
# Serves:
#   /.well-known/agent.json (combined or per-path)
#   /research/a2a
#   /writing/a2a
#   /analysis/a2a
```

---

## 5. Composition Patterns

### 5.1 A2A Fallback Chain

```python
from adk_fluent import Agent, RemoteAgent

# Try remote first, fall back to local
pipeline = RemoteAgent("pro", "http://pro:8001") // Agent("local", "gemini-2.5-flash")

# Multi-level fallback
pipeline = (
    RemoteAgent("pro", "http://pro:8001")
    // RemoteAgent("backup", "http://backup:8002")
    // Agent("local", "gemini-2.5-flash")
)
```

### 5.2 Hybrid Local-Remote Fan-Out

```python
results = (
    RemoteAgent("web-search", "http://search:8001")
    | RemoteAgent("paper-search", "http://papers:8002")
    | Agent("local-db", "gemini-2.5-flash").tool(db_query)
)

pipeline = Agent("coordinator") >> results >> Agent("synthesizer")
```

### 5.3 A2A-Aware Routing

```python
from adk_fluent import Agent, RemoteAgent, Route

pipeline = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the request type.")
    .writes("request_type")
    >> Route("request_type")
        .eq("research", RemoteAgent("research", "http://research:8001"))
        .eq("writing", RemoteAgent("writing", "http://writing:8002"))
        .otherwise(Agent("general", "gemini-2.5-flash"))
)
```

### 5.4 Higher-Order Pattern Functions

```python
from adk_fluent.patterns import a2a_cascade, a2a_mesh

# Cascading remote agents (try in order)
result = a2a_cascade(
    "http://fast:8001",
    "http://accurate:8002",
    "http://fallback:8003",
)

# Fan-out across A2A mesh
result = a2a_mesh(
    research="http://research:8001",
    analysis="http://analysis:8002",
    writing="http://writing:8003",
)
```

### 5.5 Review Loop with Remote Reviewer

```python
from adk_fluent.patterns import review_loop

pipeline = review_loop(
    worker=Agent("writer", "gemini-2.5-flash").instruct("Write the draft."),
    reviewer=RemoteAgent("expert-reviewer", "http://reviewer:8001"),
    quality_key="quality_score",
    target=0.9,
    max_rounds=3,
)
```

---

## 6. Implementation Plan

### Phase 1: Core Builders (Minimum Viable)

**Goal:** Consume and publish A2A agents with zero boilerplate.

| Component | File | Approach |
|---|---|---|
| `RemoteAgent` builder | `src/adk_fluent/a2a.py` | Hand-written, wraps `RemoteA2aAgent` |
| `A2AServer` builder | `src/adk_fluent/a2a.py` | Hand-written, wraps `to_a2a()` |
| `.skill()` method | `src/adk_fluent/agent.py` | Add to Agent builder |
| `.publish()` shorthand | `src/adk_fluent/agent.py` | Convenience, calls A2AServer |
| `Agent.remote()` static | `src/adk_fluent/agent.py` | Factory method |
| Exports | `src/adk_fluent/__init__.py` | Add RemoteAgent, A2AServer |

**Estimated scope:** ~400 lines of new code.

### Phase 2: Composition & Patterns

**Goal:** A2A agents work seamlessly in all operators and patterns.

| Component | File | Approach |
|---|---|---|
| Operator support | `src/adk_fluent/_base.py` | Ensure RemoteAgent works with `>>`, `|`, `*`, `//` |
| `T.a2a()` | `src/adk_fluent/_tools.py` | Wrap RemoteAgent as AgentTool |
| Route integration | `src/adk_fluent/_routing.py` | Accept RemoteAgent in Route branches |
| `a2a_cascade()` | `src/adk_fluent/patterns.py` | Higher-order pattern |
| `a2a_mesh()` | `src/adk_fluent/patterns.py` | Higher-order pattern |

**Estimated scope:** ~200 lines of new code.

### Phase 3: IR, Contracts & Diagnostics

**Goal:** Static analysis and visualization for A2A topologies.

| Component | File | Approach |
|---|---|---|
| `RemoteAgentNode` IR | `src/adk_fluent/_ir.py` | New node type with endpoint metadata |
| Contract checking | `src/adk_fluent/testing/` | Validate A2A data flow |
| Mermaid rendering | `src/adk_fluent/viz.py` | Show remote agents distinctly |
| `.diagnose()` support | `src/adk_fluent/_helpers.py` | Include A2A metadata |

**Estimated scope:** ~200 lines of new code.

### Phase 4: Codegen Integration

**Goal:** Auto-generate A2A builders from ADK manifest.

| Component | File | Approach |
|---|---|---|
| Scan A2A classes | `scripts/scanner.py` | Add RemoteA2aAgent to manifest |
| Seed updates | `seeds/seed.toml` | Define A2A builder rules |
| Config builders | `src/adk_fluent/config.py` | Auto-generate A2A configs |

### Phase 5: Advanced Features

| Component | Description |
|---|---|
| Auth presets | Common auth patterns (Bearer, OAuth, mTLS) |
| Service mesh | Discovery + load balancing across A2A agents |
| Health checks | Probe remote agent availability |
| A2A middleware | `M.a2a_retry()`, `M.a2a_circuit_breaker()` |
| Multi-agent server | Serve multiple agents from one process |

---

## 7. Dependency Considerations

- `google-adk[a2a]` — needed for `RemoteA2aAgent`, `to_a2a()`, converters
- `a2a-python` SDK — transitive dependency via `google-adk[a2a]`
- `httpx` — async HTTP client (transitive via a2a-python)
- `starlette` — ASGI framework (transitive via a2a-python)

**Recommendation:** Make A2A an optional extra in adk-fluent:

```toml
[project.optional-dependencies]
a2a = ["google-adk[a2a]>=1.20.0"]
```

Usage: `pip install adk-fluent[a2a]`

This avoids forcing A2A dependencies on users who only need local agents.

---

## 8. Before vs After Comparison

### Publishing an Agent (Server Side)

**Before (raw ADK) — ~25 lines:**
```python
from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from a2a.types import AgentCard, AgentSkill, AgentCapabilities, AgentProvider

agent = LlmAgent(
    name="researcher",
    model="gemini-2.5-flash",
    instruction="Research topics thoroughly.",
    tools=[web_search],
)

card = AgentCard(
    name="Research Assistant",
    description="Helps with research",
    url="http://localhost:8001/a2a",
    version="1.0.0",
    skills=[AgentSkill(id="research", name="Research", description="...", tags=["research"])],
    capabilities=AgentCapabilities(streaming=True),
    defaultInputModes=["text/plain"],
    defaultOutputModes=["text/plain"],
    provider=AgentProvider(organization="Acme", url="https://acme.com"),
)

app = to_a2a(agent, port=8001, agent_card=card)
```

**After (adk-fluent) — 5 lines:**
```python
from adk_fluent import Agent, A2AServer

app = (
    A2AServer(Agent("researcher", "gemini-2.5-flash").instruct("Research topics.").tool(web_search))
    .port(8001)
    .provider("Acme", "https://acme.com")
    .streaming(True)
    .build()
)
```

**Or ultra-concise — 1 line:**
```python
app = Agent("researcher", "gemini-2.5-flash").instruct("Research.").tool(search).publish(port=8001)
```

### Consuming a Remote Agent (Client Side)

**Before (raw ADK) — ~15 lines:**
```python
from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

remote = RemoteA2aAgent(
    name="helper",
    description="Specialized research agent",
    agent_card="http://remote:8001/.well-known/agent.json",
    timeout=300.0,
)

orchestrator = LlmAgent(
    name="coordinator",
    model="gemini-2.5-flash",
    instruction="Delegate research tasks to helper.",
    sub_agents=[remote],
)
```

**After (adk-fluent) — 4 lines:**
```python
from adk_fluent import Agent, RemoteAgent

pipeline = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct("Delegate research tasks to helper.")
    .sub_agent(RemoteAgent("helper", "http://remote:8001").timeout(300))
    .build()
)
```

**Or with operators — 1 line:**
```python
pipeline = Agent("coordinator") >> RemoteAgent("helper", "http://remote:8001")
```

### Hybrid Topology

**Before (raw ADK) — 40+ lines of manual wiring**

**After (adk-fluent) — 8 lines:**
```python
pipeline = (
    Agent("classifier", "gemini-2.5-flash").instruct("Classify.").writes("type")
    >> Route("type")
        .eq("research", RemoteAgent("research", "http://research:8001"))
        .eq("writing", RemoteAgent("writing", "http://writing:8002"))
        .otherwise(Agent("general", "gemini-2.5-flash"))
)
```

---

## 9. Open Questions

1. **Should `RemoteAgent` extend `BuilderBase` or be a thin wrapper?**
   - Recommendation: Extend `BuilderBase` with `_ADK_TARGET_CLASS = RemoteA2aAgent`
   - This gives it all builder infrastructure (operators, IR, cloning) for free

2. **Should `.publish()` return a built Starlette app or a builder?**
   - Recommendation: Return Starlette app directly (it's the terminal action)
   - For builder pattern use `A2AServer(agent)` which has `.build()`

3. **How to handle the `@a2a_experimental` status in ADK?**
   - Recommendation: Mirror it — mark adk-fluent A2A APIs as experimental
   - Use `warnings.warn("A2A support is experimental", stacklevel=2)`

4. **Namespace: standalone `A2A` module or extend `T`?**
   - Recommendation: Start with `RemoteAgent` + `A2AServer` top-level exports
   - Add `T.a2a()` for tool-wrapping pattern
   - Defer full `A2A` namespace until patterns stabilize

5. **Multi-agent server support?**
   - ADK supports this via `adk api_server --a2a`
   - Defer to Phase 5 — single-agent server covers 90% of use cases

---

## 10. References

- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [A2A GitHub Repository](https://github.com/a2aproject/A2A)
- [A2A Python SDK](https://github.com/a2aproject/a2a-python)
- [ADK A2A Documentation](https://google.github.io/adk-docs/a2a/)
- [ADK A2A Quickstart (Exposing)](https://google.github.io/adk-docs/a2a/quickstart-exposing/)
- [Google Cloud Blog - Convert ADK Agents for A2A](https://cloud.google.com/blog/products/ai-machine-learning/unlock-ai-agent-collaboration-convert-adk-agents-for-a2a)
- [google/adk-python source](https://github.com/google/adk-python) — `src/google/adk/a2a/` and `src/google/adk/agents/remote_a2a_agent.py`
