# A2A Protocol Audit: DX Gaps, Anti-Patterns & adk-fluent Integration Report

## Context

The A2A (Agent-to-Agent) protocol is an open standard for inter-agent communication — the "HTTP for agents." **v1.0.0 was released 2026-03-12** (3 days ago) under the Linux Foundation, with the normative source being `a2a.proto`. Google ADK has experimental A2A support (`@a2a_experimental`). This audit examines what breaks when you try to run a **full agent mesh** — multiple agents discovering, delegating, streaming, and failing across network boundaries — and identifies the DX gaps adk-fluent should close.

### Sources Analyzed
- **A2A spec v1.0.0**: `a2a.proto` (normative), JSON-RPC/gRPC/HTTP bindings, 9 ADRs
- **A2A repo**: https://github.com/a2aproject/A2A — cloned and audited
- **Google ADK**: `google.adk.a2a.*` and `google.adk.agents.remote_a2a_agent` (v1.25.0, experimental)
- **adk-fluent**: Full codebase audit + existing research doc at `docs/research/a2a-fluent-integration.md`

### A2A v1.0.0 Breaking Changes (Relevant to This Audit)
- Package renamed with LF prefix (`lf.a2a.v1`)
- Enum format aligned with ProtoJSON (`TASK_STATE_WORKING` not `working`)
- OAuth 2.0 modernized (removed implicit/password grants, added device code + PKCE)
- `referenceTaskIds` added for multi-turn refinement chains
- Push notification config consolidated into single object
- `TASK_STATE_SUBMITTED` added (new initial state before `WORKING`)
- `TASK_STATE_AUTH_REQUIRED` added (auth interruption state)
- `TASK_STATE_REJECTED` added (agent declines task)

---

## 1. The Full Agent Mesh Scenario

Consider a realistic production topology:

```
                    ┌─────────────────┐
                    │   User / CLI    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Orchestrator   │  (local, gemini-2.5-pro)
                    │  Port 8000      │
                    └──┬─────┬─────┬──┘
            ┌──────────┤     │     ├──────────┐
   ┌────────▼───────┐  │  ┌──▼──────────┐  ┌──▼──────────┐
   │ Research Agent  │  │  │ Code Agent   │  │ Review Agent │
   │ Port 8001       │  │  │ Port 8002    │  │ Port 8003    │
   │ (team A)        │  │  │ (team B)     │  │ (team C)     │
   └────────┬────────┘  │  └──────────────┘  └──────────────┘
            │           │
   ┌────────▼────────┐  │
   │ Citation Agent   │  │
   │ Port 8004        │  │
   │ (team A)         │  │
   └──────────────────┘  │
                         │
                ┌────────▼────────┐
                │ Fallback Agent   │
                │ Port 8005        │
                │ (team D)         │
                └──────────────────┘
```

**What must work:** Discovery, skill matching, delegation, streaming, error recovery, multi-turn state, auth propagation, lifecycle management, observability — all across process and network boundaries.

**What actually breaks:** Almost everything beyond happy-path single-turn delegation.

---

## 2. Gap Analysis: Publishing Skills for A2A Agents

### 2.1 Anti-Pattern: Implicit Skill Inference

**The problem:** ADK's `AgentCardBuilder` auto-extracts skills by crawling an agent's tools, sub-agents, and instruction text. This is convenient but fundamentally wrong for production:

```python
# ADK today — skills are inferred, not declared
agent = LlmAgent(
    name="researcher",
    model="gemini-2.5-flash",
    instruction="Research topics. Search the web. Write citations.",
    tools=[web_search, arxiv_search, citation_formatter],
)
app = to_a2a(agent, port=8001)
# AgentCard skills: auto-generated from tool names + docstrings
# Result: 3 skills named after internal tool functions — meaningless to consumers
```

**Why this is wrong:**
- **Leaky abstraction** — internal tool names become public API surface
- **No semantic grouping** — `web_search` and `arxiv_search` are both "research" but appear as separate skills
- **No versioning** — changing a tool name silently changes your published skill contract
- **No modality contracts** — skills don't declare "I accept PDF input" or "I return structured JSON"
- **No examples** — consumers can't discover how to invoke skills without reading docs

**What the A2A spec actually requires:**
```json
{
  "skills": [{
    "id": "academic-research",
    "name": "Academic Research",
    "description": "Deep research with citations across arxiv, pubmed, and web",
    "tags": ["research", "citations", "academic"],
    "examples": ["Find recent papers on transformer architectures"],
    "inputModes": ["text/plain", "application/pdf"],
    "outputModes": ["text/plain", "application/json"]
  }]
}
```

**Gap in adk-fluent:** No `.skill()` builder method exists. No way to declare explicit, versioned, semantically meaningful skills.

### 2.2 Anti-Pattern: AgentCard as Afterthought

**The problem:** The AgentCard is generated *after* the agent is built, as a deployment concern. But skills are a *design-time* concern — they define the agent's public contract.

```python
# Current flow (backwards):
# 1. Build agent with tools
# 2. Generate card from agent internals
# 3. Hope the card makes sense to consumers

# Correct flow should be:
# 1. Declare skills (public contract)
# 2. Build agent to fulfill those skills
# 3. Card is derived from declared skills
```

**Impact on mesh:** In a mesh, agents discover each other by skills. If skills are auto-inferred, the discovery index is full of implementation details (`web_search_v2`, `_internal_format_citations`) instead of semantic capabilities (`research`, `code-review`).

### 2.3 Anti-Pattern: No Skill Versioning

**The problem:** A2A spec supports `version` on AgentCard but not on individual skills. When an agent's capabilities change (new tool, removed tool), the entire card version bumps — no way to express "skill X is v2 but skill Y is still v1."

**Impact on mesh:** Consumer agents cache cards. If a skill silently changes behavior without a version bump, downstream agents break with no signal. There's no way to do canary releases of individual capabilities.

### 2.4 Anti-Pattern: ADK's AgentCardBuilder Doesn't Map to v1.0.0 Proto Schema

**The problem:** The A2A v1.0.0 proto defines `AgentSkill` with fields ADK's auto-generation doesn't populate:

```protobuf
// From a2a.proto (normative)
message AgentSkill {
  string id = 1;                           // REQUIRED — ADK uses tool function name
  string name = 2;                         // REQUIRED — ADK uses tool function name (same!)
  string description = 3;                  // REQUIRED — ADK uses tool docstring
  repeated string tags = 4;               // REQUIRED — ADK leaves empty
  repeated string examples = 5;           // Optional — ADK sometimes extracts from ExampleTool
  repeated string input_modes = 6;        // Optional — ADK defaults to ["text/plain"]
  repeated string output_modes = 7;       // Optional — ADK defaults to ["text/plain"]
  repeated SecurityRequirement security_requirements = 8;  // Optional — ADK ignores
}
```

**Gaps:**
- `tags` is REQUIRED but ADK auto-gen leaves it empty — **spec violation**
- `id` and `name` are both set to the Python function name — `web_search` is not a meaningful skill name
- `security_requirements` per-skill is never populated — no skill-level auth differentiation
- `input_modes`/`output_modes` are always `["text/plain"]` — no multimodal skill declaration

**Also missing from AgentCard auto-gen:**
```protobuf
message AgentCard {
  // ADK populates these:
  string name = 1;
  string description = 2;
  repeated AgentInterface supported_interfaces = 3;
  string version = 5;
  AgentCapabilities capabilities = 7;
  repeated string default_input_modes = 10;
  repeated string default_output_modes = 11;
  repeated AgentSkill skills = 12;

  // ADK does NOT populate these:
  AgentProvider provider = 4;              // No provider info
  optional string documentation_url = 6;  // No docs link
  map<string, SecurityScheme> security_schemes = 8;  // No auth
  repeated SecurityRequirement security_requirements = 9;  // No auth
  repeated AgentCardSignature signatures = 13;  // No card signing
  optional string icon_url = 14;           // No icon
}
```

**Impact:** ADK-generated cards are technically non-compliant (missing required `tags` on skills) and missing security, provider, and documentation fields that enterprise consumers expect.

### 2.5 Missing: Skill-Level Input/Output Contracts

**The problem:** A2A skills declare `inputModes` and `outputModes` as MIME types, but there's no structured schema. A consumer knows "this skill accepts text/plain" but not "this skill expects a JSON object with fields `query`, `max_results`, `date_range`."

**Impact on mesh:** Agents can't validate payloads before sending. Failures happen at execution time, not at composition time. No static analysis possible.

**What adk-fluent should do:**
```python
# Skill with typed contract
agent = (
    Agent("researcher", "gemini-2.5-flash")
    .skill("research", "Academic Research",
           description="Deep research with citations",
           tags=["research"],
           examples=["Find papers on transformers"],
           input_schema=ResearchQuery,    # Pydantic model
           output_schema=ResearchResult)  # Pydantic model
    .build()
)
```

---

## 3. Gap Analysis: Consuming A2A Agents with First-Class Composition

### 3.1 Anti-Pattern: RemoteA2aAgent is a Black Box in Composition

**The problem:** ADK's `RemoteA2aAgent` extends `BaseAgent` — correct architecturally — but it's opaque to composition operators:

```python
# This works syntactically but has hidden semantics
remote = RemoteA2aAgent(name="helper", agent_card="http://helper:8001/...")
pipeline = Agent("coordinator") >> remote >> Agent("reviewer")
```

**Hidden problems:**
- **State boundary:** Does `remote` see the state written by `coordinator`? ADK serializes the *prompt* not the *state* into the A2A `Message`. State keys written by upstream agents are invisible to remote agents unless explicitly passed.
- **Error propagation:** If `remote` fails (network timeout, 503, task FAILED), what happens to the pipeline? ADK has no documented behavior. The pipeline may hang, silently skip, or crash.
- **Streaming mismatch:** If the pipeline uses `streaming_mode`, does `remote` support it? If not, the pipeline blocks on `remote` while streaming for other steps — inconsistent UX.

### 3.2 Anti-Pattern: No State Serialization Across A2A Boundaries

**The critical gap:** ADK's state model (`session.state`) is local. A2A's model is `Message` + `Part`. There is **no automatic mapping** between them.

```python
# This DOES NOT work as expected:
pipeline = (
    Agent("writer").instruct("Write a draft.").writes("draft")
    >> RemoteAgent("reviewer", "http://reviewer:8001")
    # The reviewer DOES NOT see state["draft"]
    # It only sees the conversation messages forwarded by the parent LLM
)
```

**What actually happens:**
1. `writer` executes, stores result in `state["draft"]`
2. Parent LLM sees `state["draft"]` in context and formulates a delegation prompt
3. `RemoteA2aAgent` sends that prompt as an A2A `Message`
4. Remote agent receives raw text — no structured state, no key names, no schema

**Impact on mesh:** State flow in a mesh is lossy. Data transforms (`S.pick`, `S.rename`) operate on local state but have no effect on what crosses A2A boundaries. The entire `S` namespace is broken for remote agents.

**What's needed:**
```python
# Explicit state bridging
remote = (
    RemoteAgent("reviewer", "http://reviewer:8001")
    .sends("draft", "context")       # serialize state keys into A2A message parts
    .receives("feedback", "score")    # deserialize A2A artifacts back into state
)
```

### 3.3 Anti-Pattern: Operators Don't Know About Network Boundaries

**The problem:** `>>`, `|`, `*`, `//` treat all agents identically. But remote agents have fundamentally different failure modes:

| Concern | Local Agent | Remote A2A Agent |
|---------|-------------|-------------------|
| Latency | ~ms | ~seconds (network + remote LLM) |
| Failure mode | Exception | HTTP timeout, 503, FAILED task, connection refused |
| State access | Direct `session.state` | Serialized via Message/Part |
| Streaming | In-process generator | SSE over HTTP |
| Cost | Predictable | Unknown (remote may use expensive model) |
| Retry | Not needed | Essential |
| Circuit breaking | Not needed | Essential |
| Timeout | Rare | Always needed |

**Impact on mesh:** A `FanOut` with 3 remote agents has completely different reliability characteristics than a `FanOut` with 3 local agents. The operator `|` doesn't encode this. One slow/failing remote agent blocks the entire fan-out with no timeout, no circuit breaker, no fallback.

### 3.4 Missing: Operator-Level Resilience for Remote Agents

**What's needed in adk-fluent:**

```python
# Fan-out with resilience (doesn't exist today)
fanout = (
    RemoteAgent("web", "http://web:8001").timeout(30)
    | RemoteAgent("papers", "http://papers:8002").timeout(30)
    | Agent("local-db", "gemini-2.5-flash").tool(db_query)
)

# Fallback chain (// operator works but no A2A-specific error handling)
chain = (
    RemoteAgent("fast", "http://fast:8001")
    // RemoteAgent("backup", "http://backup:8002")
    // Agent("local", "gemini-2.5-flash")
)

# What should happen:
# - If fast returns FAILED task → try backup
# - If fast times out → try backup (with reduced timeout budget)
# - If backup also fails → use local
# - Circuit breaker: if fast fails 3x in 60s → skip it for next 30s
```

### 3.5 Missing: A2A-Aware Routing

**The problem:** `Route` does deterministic state-based routing. But route targets can be remote A2A agents, and Route doesn't handle the possibility that a remote target is unavailable.

```python
# This works but is fragile
router = (
    Route("task_type")
    .eq("research", RemoteAgent("research", "http://research:8001"))
    .eq("code", RemoteAgent("code", "http://code:8002"))
    .otherwise(Agent("general", "gemini-2.5-flash"))
)
# If research agent is down, the route sends traffic to a dead endpoint
# No health-check, no failover, no circuit breaker
```

---

## 4. Gap Analysis: DNS, Discovery & Agent Lifecycle

### 4.1 Anti-Pattern: Hardcoded Endpoints

**The problem:** Every `RemoteA2aAgent` takes a URL. In a mesh with 10+ agents, that's 10+ hardcoded URLs scattered across codebases.

```python
# Team A's code
remote_code = RemoteA2aAgent(name="code", agent_card="http://code-agent.internal:8002/...")
# Team B's code
remote_code = RemoteA2aAgent(name="code", agent_card="http://code-agent.internal:8002/...")
# Team C's code
remote_code = RemoteA2aAgent(name="code", agent_card="http://code-agent.internal:8002/...")
# When code-agent moves to port 8003... all three teams must update
```

**What the A2A spec offers but ADK doesn't implement:**
- **Well-known discovery:** `GET https://agent-domain/.well-known/agent-card.json`
- **Curated registries:** Central service with query API (NOT specified in protocol — left to implementers)
- **DNS-SD:** Not in A2A spec at all, but a natural fit

**What's missing (both in ADK and adk-fluent):**

```python
# None of these exist:

# 1. DNS-based discovery
remote = RemoteAgent.discover("research-agent.agents.acme.com")

# 2. Registry-based discovery
registry = AgentRegistry("http://registry.internal:9000")
remote = registry.find(skill="research", tag="academic")

# 3. Environment-based configuration
remote = RemoteAgent("code", env="CODE_AGENT_URL")  # reads from env var

# 4. Service mesh integration
remote = RemoteAgent("code", service="code-agent", namespace="agents")  # K8s service
```

### 4.2 Anti-Pattern: No Agent Lifecycle Management

**The problem:** A2A agents are processes. Processes start, crash, restart, scale, and decommission. The A2A spec and ADK have **zero lifecycle management:**

| Lifecycle Event | What Should Happen | What Actually Happens |
|-----------------|-------------------|----------------------|
| Agent starts | Register with registry, announce skills | Nothing — consumers must know URL |
| Agent crashes | Consumers detect failure, route around | HTTP timeout after 30-300s |
| Agent restarts | Resume in-flight tasks | All tasks lost (InMemoryTaskStore) |
| Agent scales (N replicas) | Load balance across instances | Not supported — single URL |
| Agent decommissions | Drain tasks, deregister | Consumers discover via errors |
| Agent upgrades (new version) | Canary, blue-green, or rolling | Not supported — hard cut |
| Health check | Periodic liveness/readiness probes | No health endpoint in A2A spec |

**Impact on mesh:** A 6-agent mesh where any agent can crash means you need:
- Health checks for all 5 remote connections
- Retry logic for transient failures
- Circuit breakers for persistent failures
- Task recovery for in-flight work
- Graceful shutdown with task draining

**None of this exists in ADK or A2A spec.** Every team must build it themselves.

### 4.3 Anti-Pattern: No Task Durability

**The critical production gap:** `InMemoryTaskStore` means:

```
Scenario: Long-running research task (5 minutes)
1. User sends request → Orchestrator delegates to Research Agent
2. Research Agent creates A2A Task (state: WORKING)
3. Research Agent process crashes at minute 3
4. Task is gone — InMemoryTaskStore was in-process
5. Orchestrator's RemoteA2aAgent gets connection refused
6. User gets... nothing. No error. No partial result. No retry.
```

**What's needed:**
- Durable task store (Redis, PostgreSQL, Cloud Datastore)
- Task recovery on agent restart
- Idempotent task submission (retry-safe)
- Task timeout with cleanup

### 4.4 Missing: Push Notification Infrastructure

**The problem:** A2A supports push notifications (webhooks) for async task completion. But:

- `InMemoryPushNotificationConfigStore` — lost on restart
- No webhook validation (HMAC, signature verification)
- No delivery guarantees (no retry, no dead-letter queue)
- No backpressure mechanism
- No pub/sub alternative (Cloud Pub/Sub, Kafka)

**Impact on mesh:** Async workflows (human-in-the-loop, long-running tasks) cannot use push notifications reliably. Everyone falls back to polling `GetTask`, which doesn't scale.

### 4.5 Gap: Task State Machine is Richer Than ADK Implements

**A2A v1.0.0 defines 9 task states** (from the normative proto):

```
SUBMITTED → WORKING → COMPLETED (happy path)
                    → FAILED
                    → CANCELED
                    → INPUT_REQUIRED → WORKING (multi-turn)
                    → AUTH_REQUIRED → WORKING (auth challenge)
         → REJECTED (agent declines before starting)
```

**ADK implements only the basic flow:** SUBMITTED → WORKING → COMPLETED/FAILED. The interrupted states (`INPUT_REQUIRED`, `AUTH_REQUIRED`) and decline state (`REJECTED`) have no ADK-side handling:

- **INPUT_REQUIRED:** The remote agent needs clarification. ADK's `RemoteA2aAgent` has no mechanism to surface this to the parent LLM and relay the response back. The task just hangs.
- **AUTH_REQUIRED:** The remote agent needs additional authentication mid-task. No ADK mechanism to handle auth challenges dynamically.
- **REJECTED:** The remote agent declines the task. `RemoteA2aAgent` doesn't distinguish rejection from failure — both look like errors to the parent.

**Impact on mesh:** Multi-turn A2A conversations (the most valuable enterprise pattern) are effectively broken. An agent can't ask "do you want me to search arxiv or pubmed?" and get a response through the A2A protocol.

### 4.6 Gap: Extension Mechanism Not Leveraged

**A2A v1.0.0 has a mature extension framework** that neither ADK nor adk-fluent uses:

```protobuf
message AgentExtension {
  string uri = 1;        // e.g., "https://a2a-protocol.org/extensions/tracing/v1"
  string version = 2;
  bool required = 3;     // Client MUST support if true
  optional string documentation = 4;
}
```

**Existing extensions in the ecosystem:**
- **Secure Passport** — contextual personalization layer
- **Timestamp** — adds timestamps to Message/Artifact metadata
- **Traceability** — distributed tracing
- **Agent Gateway Protocol (AGP)** — autonomous squads & intent-based routing

**None of these are used by ADK.** The extension activation flow (`A2A-Extensions` header negotiation) is not implemented in `RemoteA2aAgent` or `A2aAgentExecutor`.

**Impact:** ADK agents can't participate in extension-enhanced meshes. They'll fail with `ExtensionSupportRequiredError` when connecting to agents that require extensions.

### 4.7 Missing: Observability Across A2A Boundaries

**The problem:** When a request traverses 4 agents across 4 processes, you need distributed tracing. The A2A spec mentions tracing but doesn't specify headers or correlation IDs.

**What's missing:**
- No trace context propagation (W3C Trace Context headers)
- No correlation ID across A2A task chains
- No aggregated latency view
- No cost attribution across agents
- No error correlation (which upstream failure caused which downstream failure)

### 4.8 Anti-Pattern: contextId / Session Impedance Mismatch

**The core problem:** A2A uses `contextId` (server-generated UUID) to group related tasks into a conversation. ADK uses `session_id` to maintain conversational state. These are fundamentally different:

| | A2A `contextId` | ADK `session_id` |
|---|---|---|
| **Generated by** | A2A server (remote agent) | ADK Runner (local) |
| **Scope** | Groups tasks at one remote agent | Groups turns at one local agent |
| **State model** | Opaque to client — server manages | `session.state` dict, fully accessible |
| **Lifetime** | Server-defined expiration | Until session service evicts |
| **Cross-agent** | One contextId per remote agent pair | One session for entire local topology |

**What happens in a mesh:**
```
User → Orchestrator (session_id=S1)
  → Research Agent (contextId=C1, generated by research agent)
  → Code Agent (contextId=C2, generated by code agent)
  → Research Agent again (should reuse C1? or new C3?)
```

**ADK does not map `session_id` to `contextId`.** Each `RemoteA2aAgent` call creates a new task, and it's unclear whether it reuses the previous `contextId` for conversation continuity. This means:
- Remote agents lose conversational context between calls
- "Remember what I asked you earlier" doesn't work across A2A boundaries
- Multi-turn refinement loops (`review_loop`) with remote reviewers start fresh each iteration

**What's needed in adk-fluent:**
```python
# Context-aware remote agent (doesn't exist)
remote = (
    RemoteAgent("reviewer", "http://reviewer:8001")
    .persistent_context()  # maintain contextId across calls within same session
    .context_key("reviewer_context_id")  # store contextId in session state
)
```

---

## 5. Severity-Ranked Gap Summary

### Critical (Blocks Production Mesh Deployments)

| # | Gap | Where | Impact |
|---|-----|-------|--------|
| 1 | **No task durability** — InMemoryTaskStore only | ADK | Long-running tasks lost on crash |
| 2 | **No state serialization across A2A boundaries** | ADK + adk-fluent | State keys invisible to remote agents; `S` namespace broken for remotes |
| 3 | **No error recovery / resilience patterns** | ADK + adk-fluent | One failing agent cascades to entire mesh |
| 4 | **Interrupted states not handled** — INPUT_REQUIRED, AUTH_REQUIRED ignored | ADK | Multi-turn A2A conversations broken; tasks hang |
| 5 | **contextId/session impedance mismatch** | ADK | Remote agents lose conversational context between calls |

### High (Significant DX Pain, Workarounds Exist)

| # | Gap | Where | Impact |
|---|-----|-------|--------|
| 6 | **No fluent builders (RemoteAgent, A2AServer)** | adk-fluent | 15-25 lines of boilerplate per agent |
| 7 | **No explicit skill declaration** — auto-gen violates spec (missing required `tags`) | ADK + adk-fluent | Skills inferred from internals, non-compliant cards |
| 8 | **Hardcoded endpoints, no discovery** | ADK + adk-fluent | Fragile coupling across teams |
| 9 | **No agent lifecycle management** | A2A spec + ADK | Manual coordination for start/stop/scale |
| 10 | **No distributed tracing** | ADK | Blind debugging across agent boundaries |
| 11 | **No A2A-aware composition operators** | adk-fluent | `>>`, `|`, `//` don't handle network failures |
| 12 | **Extension mechanism not implemented** | ADK | Can't participate in extension-enhanced meshes |
| 13 | **Experimental status (`@a2a_experimental`)** | ADK | No stability guarantees for production |

### Medium (DX Friction, Acceptable for Early Adoption)

| # | Gap | Where | Impact |
|---|-----|-------|--------|
| 14 | **No auth builder patterns** | adk-fluent | Manual auth config at every call site |
| 15 | **Push notifications not durable** | ADK | Async workflows unreliable |
| 16 | **Streaming semantics unspecified across agents** | A2A spec | Inconsistent streaming behavior in pipelines |
| 17 | **No skill versioning** | A2A spec | Silent contract breakage |
| 18 | **No multi-agent server** | adk-fluent | One process per agent (resource waste) |
| 19 | **AgentCard missing provider, security, signatures** | ADK auto-gen | Enterprise consumers reject incomplete cards |
| 20 | **TASK_STATE_REJECTED not distinguished from FAILED** | ADK | Can't differentiate "agent declined" from "agent crashed" |

### Low (Nice-to-Have, Future Work)

| # | Gap | Where | Impact |
|---|-----|-------|--------|
| 21 | **No cost estimation for remote agents** | adk-fluent IR | Can't predict mesh execution cost |
| 22 | **No A2A-specific middleware (M namespace)** | adk-fluent | No `M.a2a_retry()`, `M.a2a_circuit_breaker()` |
| 23 | **No registry query API in A2A spec** | A2A spec | Every implementer invents their own |
| 24 | **No card signing/verification** | ADK | Can't verify agent identity in untrusted meshes |

---

## 6. Recommended adk-fluent Implementation Priorities

### Phase 1 — MVP: Publish & Consume (Closes Gaps 5, 6, 10)

**Files to create/modify:**
- `src/adk_fluent/a2a.py` — `RemoteAgent` and `A2AServer` builders (~400 lines)
- `src/adk_fluent/agent.py` — Add `.skill()`, `.publish()`, `Agent.remote()` (~80 lines)
- `src/adk_fluent/_tools.py` — Add `T.a2a()` (~30 lines)
- `src/adk_fluent/__init__.py` — Export `RemoteAgent`, `A2AServer`
- `tests/test_a2a.py` — Unit tests (~200 lines)

**Key design decisions:**
- `RemoteAgent` extends `BuilderBase` → gets all operators for free
- `.skill()` stores metadata that `A2AServer` reads for card generation
- `.publish()` is a terminal method returning Starlette app (not a builder)

### Phase 2 — Resilience: State Bridge & Error Recovery (Closes Gaps 2, 3)

**New concepts:**
- `.sends(*keys)` / `.receives(*keys)` on `RemoteAgent` — explicit state bridging
- `M.a2a_retry(max=3, backoff="exponential")` — A2A-specific retry middleware
- `M.a2a_circuit_breaker(threshold=5, reset=60)` — circuit breaker
- `M.a2a_timeout(seconds=30)` — per-delegation timeout
- Operator-level error handling: `|` with timeout, `//` with A2A error detection

### Phase 3 — Discovery & Lifecycle (Closes Gaps 7, 8)

**New concepts:**
- `RemoteAgent.discover(domain)` — DNS-based well-known discovery
- `AgentRegistry` — central registry client
- `RemoteAgent("name", env="ENV_VAR")` — env-based configuration
- Health check integration in `A2AServer`
- Graceful shutdown with task draining

### Phase 4 — Observability (Closes Gap 9)

**New concepts:**
- `M.a2a_trace()` — W3C Trace Context propagation
- `M.a2a_metrics()` — cross-boundary latency and cost tracking
- `RemoteAgentNode` in IR — static analysis of mesh topology

---

## 7. Verification Plan

After implementation, verify with:

1. **Unit tests:** `uv run pytest tests/test_a2a.py -v`
2. **Integration test:** Spin up 2 A2A agents, have one delegate to the other
3. **Mesh test:** 4-agent mesh with fan-out, routing, and fallback
4. **Failure test:** Kill a remote agent mid-task, verify fallback behavior
5. **Contract test:** Validate AgentCard skills match declared `.skill()` metadata
6. **Composition test:** `RemoteAgent` works with `>>`, `|`, `*`, `//` operators
