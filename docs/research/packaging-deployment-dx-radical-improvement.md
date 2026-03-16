# Packaging, Deployment & Developer Experience: Gap Audit and Radical Improvement Proposal

> Research document — adk-fluent execution lifecycle DX analysis
> Date: 2026-03-16

---

## 1. Current State: Where Things Stand Today

### 1.1 The ADK Toolchain (What Exists)

ADK provides a complete lifecycle CLI:

| Command | Purpose | adk-fluent equivalent |
|---------|---------|----------------------|
| `adk create` | Scaffold new agent project | **Nothing** |
| `adk run` | Interactive CLI testing | `.ask()` (programmatic only) |
| `adk web` | Dev server with web UI, event tracing, session management | **Nothing** |
| `adk api_server` | Production FastAPI server (no UI) | `A2AServer` (A2A protocol only) |
| `adk eval` | Run evaluation suites from YAML/JSON | `.eval()` / `.eval_suite()` (programmatic only) |
| `adk deploy agent_engine` | Deploy to Google Agent Engine | Works (`.build()` returns native ADK) |
| `adk deploy cloud_run` | Deploy to Cloud Run | Works (native ADK objects) |
| `adk deploy gke` | Deploy to GKE | Works (native ADK objects) |
| `adk conformance` | Record + replay consistency tests | **Nothing** |

### 1.2 The adk-fluent CLI (What We Have)

```
adk-fluent visualize <module> [--var name] [--output file] [--format html|mermaid]
```

That's it. One command. Mermaid diagrams.

### 1.3 The Gap

The adk-fluent story today is:

1. **Define** — Excellent. The fluent API is the best part.
2. **Build** — Excellent. `.build()` returns real ADK objects.
3. **Test locally** — Good. `.ask()`, `.mock()`, `.test()` work.
4. **Visualize** — Good. `.to_mermaid()`, `.explain()`, `.doctor()`.
5. **Serve** — Partial. `A2AServer` exists but it's A2A-protocol-only. No generic HTTP API server.
6. **Package** — **Nothing.** No Dockerfile generation, no manifest generation, no worker codegen CLI.
7. **Deploy** — **Passthrough only.** Falls through to `adk deploy` which works because `.build()` returns native objects. But zero support for Temporal/Prefect/DBOS deployment.
8. **Observe in production** — **Nothing beyond ADK's built-in tooling.**

The critical insight: **adk-fluent is a build-time library that stops at `.build()`**. Everything after that is "use ADK's tools." This works for the ADK backend but completely breaks down for Temporal, Prefect, DBOS, and any future backend.

---

## 2. The Packaging Gap: Backend by Backend

### 2.1 ADK Backend

**Current path:** Define → `.build()` → write `agent.py` with `root_agent = ...` → `adk deploy`

**Gaps:**
- User must manually create the `agent.py` file with the right `root_agent` variable name
- No auto-generation of `requirements.txt` from builder dependencies
- No Dockerfile generation (relies on `adk deploy` to handle it)
- No environment variable management for API keys, model configs
- No health check configuration
- No session service selection guidance

**What works:** Once you write `agent.py`, the `adk deploy` flow handles Cloud Run, Agent Engine, and GKE.

### 2.2 Temporal Backend

**Current path:** Define → `backend.compile(ir)` → `temporal_worker.py` codegen → ???

**Gaps:**
- Worker codegen exists (`generate_worker_code()`) but there's no CLI to invoke it
- No Dockerfile for the Temporal worker
- No `docker-compose.yml` with Temporal server + worker
- No deployment manifest for Temporal Cloud
- No task queue configuration generation
- User must manually set up Temporal server (`temporal server start-dev`)
- No guidance on model provider configuration in the worker

### 2.3 Prefect Backend

**Current path:** Define → `backend.compile(ir)` → `prefect_worker.py` codegen → ???

**Gaps:**
- Flow codegen exists (`generate_flow_code()`) but no CLI
- No `prefect.yaml` deployment manifest generation
- No work pool setup guidance
- No Prefect Cloud deployment path
- No Docker configuration

### 2.4 DBOS Backend

**Current path:** Define → `backend.compile(ir)` → `dbos_worker.py` codegen → ???

**Gaps:**
- App codegen exists (`generate_app_code()`) but no CLI
- No PostgreSQL migration setup
- No DBOS config generation
- No Docker configuration with PostgreSQL
- No DBOS Cloud deployment path

### 2.5 asyncio Backend

**Current path:** Define → `backend.compile(ir)` → `backend.run()` → done

**Gaps:**
- No deployment story at all (and that's fine — it's for testing)
- But also no way to serve it as an HTTP endpoint

---

## 3. What "Brilliant" Looks Like: The 100x Engineer Approach

The question isn't "how do we add more CLI commands." The question is: **what would make agent development feel like magic?**

### 3.1 The Next.js Analogy

React was a great library for building UIs. But it was just a library. You needed webpack, babel, a dev server, routing, SSR, deployment... Next.js wrapped all of that into one coherent experience:

- `npx create-next-app` → scaffold
- `next dev` → hot-reload dev server
- `next build` → optimized production build
- `vercel deploy` → one-command deploy

**adk-fluent should be the Next.js of agent development.** Not just a builder library — a complete development platform that owns the full lifecycle.

### 3.2 The Key Insight: IR Is the Universal Artifact

adk-fluent has something most agent frameworks don't: a **backend-agnostic intermediate representation**. The IR is a frozen, serializable tree that describes what the agent does without coupling to any runtime. This is our superpower.

From the IR, we can generate:
- Native ADK objects (already done)
- Temporal workflows (done)
- Prefect flows (done)
- DBOS durable functions (done)
- **FastAPI servers** (not done)
- **Dockerfiles** (not done)
- **Kubernetes manifests** (not done)
- **OpenAPI specs** (not done)
- **Agent cards** (partially done via A2A)
- **Test scaffolds** (not done)
- **Cost estimates** (not done)

The IR is the **build artifact**. Everything else is a compilation target.

---

## 4. Proposal: Seven Radical DX Improvements

### Improvement 1: `adk-fluent dev` — The Agent Development Server

**What it does:** One command to start a local development environment with hot-reload, web UI, event tracing, and streaming console.

```bash
adk-fluent dev agent.py
```

**What you get:**

```
  adk-fluent dev v0.X.0

  Agent:    research_pipeline (3 agents, 2 tools)
  Backend:  adk (default)
  Server:   http://localhost:8080

  Endpoints:
    POST /ask          — one-shot request/response
    POST /stream       — SSE streaming
    WS   /ws           — WebSocket for multi-turn
    GET  /health       — health check
    GET  /ir           — live IR tree (JSON)
    GET  /mermaid      — live Mermaid diagram
    GET  /openapi.json — auto-generated OpenAPI spec
    GET  /agent.json   — A2A agent card

  UI:
    http://localhost:8080/ui — interactive playground

  Watching agent.py for changes...
```

**Key features:**
- **Hot reload**: Watches Python files, reloads agent on change (like `uvicorn --reload` but agent-aware)
- **Embedded web UI**: Lightweight chat interface (not the full Angular adk-web, but a single-page app served from the Python process)
- **Streaming console**: Real-time event stream in the terminal showing agent execution, tool calls, state mutations
- **Protocol polyglot**: Same agent served via REST, WebSocket, SSE, and A2A simultaneously
- **OpenAPI auto-generation**: Builder contracts (`.accepts()`, `.returns()`, `.consumes()`, `.produces()`) become OpenAPI schemas automatically
- **Cost dashboard**: Live token count and estimated cost per session
- **Works with any backend**: For Temporal/Prefect/DBOS, serves via the compile → run path transparently

**Why this is radical:** Today, to test an agent via HTTP you need to: write `agent.py`, set up a separate web server, configure CORS, manage sessions, and figure out how to stream. `adk-fluent dev` collapses all of that into one command.

**Technical approach:**
- Use Starlette (already a dependency via A2A) as the ASGI framework
- Embed a minimal React/Preact chat UI as static assets (< 50KB gzipped)
- Use `watchfiles` for hot-reload (same approach as uvicorn)
- Auto-detect builders in the target module (reuse `_find_builders()` from cli.py)
- For non-ADK backends, use the compile layer transparently

---

### Improvement 2: `adk-fluent serve` — Production-Ready Server

**What it does:** Generate and run a production-grade server from any builder expression.

```bash
# Serve a single agent
adk-fluent serve agent.py --port 8080

# Serve with Temporal backend
adk-fluent serve agent.py --backend temporal --task-queue agents

# Serve with specific session store
adk-fluent serve agent.py --sessions sqlite:///sessions.db

# Serve multiple agents from a directory
adk-fluent serve agents/ --port 8080
```

**Difference from `dev`:** No hot-reload, no UI, no debug endpoints. Optimized for production: structured logging, health checks, graceful shutdown, metrics endpoint.

**Generated server features:**
- `/ask` — synchronous request/response
- `/stream` — Server-Sent Events streaming
- `/ws` — WebSocket for multi-turn sessions
- `/health` — liveness probe
- `/ready` — readiness probe (checks model provider connectivity)
- `/metrics` — Prometheus-compatible metrics
- `/.well-known/agent.json` — A2A agent card (auto-generated from builder metadata)
- `/openapi.json` — OpenAPI spec (auto-generated from builder contracts)

**Why this matters:** Today, serving an agent requires either `adk api_server` (ADK-only, requires specific directory structure) or manually building a FastAPI app. `adk-fluent serve` works with any backend and any builder expression.

---

### Improvement 3: `adk-fluent package` — Universal Packaging

**What it does:** Generate deployment artifacts for any target.

```bash
# Docker (works with any backend)
adk-fluent package agent.py --target docker
# Output: Dockerfile, docker-compose.yml, .dockerignore

# Cloud Run
adk-fluent package agent.py --target cloudrun --project my-proj --region us-central1
# Output: Dockerfile, cloudbuild.yaml, service.yaml

# Kubernetes
adk-fluent package agent.py --target k8s --replicas 3
# Output: deployment.yaml, service.yaml, configmap.yaml, Dockerfile

# Temporal worker
adk-fluent package agent.py --target temporal --task-queue agents
# Output: worker.py, Dockerfile, docker-compose.yml (with Temporal server)

# Prefect deployment
adk-fluent package agent.py --target prefect --work-pool gpu-pool
# Output: flow.py, prefect.yaml, Dockerfile

# DBOS application
adk-fluent package agent.py --target dbos --database-url postgresql://...
# Output: app.py, dbos.yaml, Dockerfile, docker-compose.yml (with PostgreSQL)

# Lambda
adk-fluent package agent.py --target lambda
# Output: handler.py, template.yaml (SAM), requirements.txt
```

**What gets generated for Docker target:**

```dockerfile
# Auto-generated by adk-fluent package
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
HEALTHCHECK CMD curl -f http://localhost:8080/health || exit 1

CMD ["adk-fluent", "serve", "agent.py", "--port", "8080"]
```

```yaml
# docker-compose.yml (auto-generated)
services:
  agent:
    build: .
    ports:
      - "8080:8080"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

**For Temporal, the docker-compose includes the Temporal server:**

```yaml
services:
  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"
      - "8233:8233"  # Temporal UI
  worker:
    build: .
    depends_on: [temporal]
    environment:
      - TEMPORAL_ADDRESS=temporal:7233
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
    command: ["python", "worker.py"]
```

**Why this is radical:** Today, packaging an agent for deployment requires manual Dockerfile creation, figuring out dependencies, health check configuration, and backend-specific setup. `adk-fluent package` generates everything from the IR + builder metadata.

---

### Improvement 4: `adk-fluent scaffold` — Project Generation

**What it does:** Generate a complete agent project with best-practice structure.

```bash
adk-fluent scaffold my-agent
# Interactive: asks for model, backend, tools, deployment target

adk-fluent scaffold my-agent --model gemini-2.5-flash --backend temporal
# Non-interactive: generates with specified options
```

**Generated structure:**

```
my-agent/
├── agent.py              # Agent definition (fluent API)
├── tools.py              # Tool functions with type hints
├── prompts.py            # P.role() + P.task() compositions
├── schemas.py            # Input/output Pydantic models
├── config.py             # Configuration (model, backend, etc.)
├── Dockerfile            # Production container
├── docker-compose.yml    # Local development stack
├── pyproject.toml        # Dependencies with adk-fluent extras
├── .env.example          # Environment variable template
├── tests/
│   ├── test_agent.py     # Unit tests with .mock()
│   ├── test_tools.py     # Tool function tests
│   └── evals/
│       └── basic.py      # Evaluation suite
└── .github/
    └── workflows/
        └── ci.yml        # GitHub Actions: lint, test, eval
```

---

### Improvement 5: The Universal Agent Server Protocol

**The problem today:** ADK has `adk web` (Angular UI + FastAPI) and `adk api_server` (FastAPI only). A2A has its own protocol. MCP has its own protocol. Every frontend (web, mobile, Slack, Discord) needs a different integration.

**The radical idea:** adk-fluent should serve agents via a **protocol-agnostic gateway** that speaks every protocol simultaneously:

```
                    ┌──────────────────────────┐
                    │   adk-fluent serve        │
                    │                          │
  REST POST /ask ───┤                          ├─── Agent
  SSE /stream ──────┤   Protocol Gateway       │    (any backend)
  WebSocket /ws ────┤                          │
  A2A /.well-known ─┤   Translates any         │
  gRPC (future) ────┤   protocol to            │
  MCP (future) ─────┤   builder.ask_async()    │
                    │                          │
                    └──────────────────────────┘
```

**What this unlocks:**
- **Any frontend works:** React web app, Flutter mobile, Slack bot, Discord bot — they all POST to `/ask` or connect to `/ws`
- **A2A interop:** Other agents discover and call yours via the standard A2A protocol
- **MCP compatibility:** Future integration where agents expose their tools as MCP resources
- **Zero protocol code:** The developer writes the agent definition; adk-fluent handles all protocol translation

**Concrete API:**

```
POST /v1/ask
Content-Type: application/json

{
  "prompt": "Research AI in healthcare",
  "session_id": "optional-for-multi-turn",
  "state": {"optional": "initial state"},
  "stream": false
}

Response:
{
  "text": "Here are the findings...",
  "session_id": "sess_abc123",
  "state": {"findings": "..."},
  "metadata": {
    "tokens_in": 150,
    "tokens_out": 500,
    "latency_ms": 2300,
    "model": "gemini-2.5-flash",
    "backend": "adk"
  }
}
```

```
POST /v1/stream
Content-Type: application/json
Accept: text/event-stream

{
  "prompt": "Write a report",
  "session_id": "sess_abc123"
}

Response (SSE):
data: {"type": "text", "content": "# Report"}
data: {"type": "text", "content": "\n\nHealthcare AI..."}
data: {"type": "tool_call", "name": "search", "args": {"q": "..."}}
data: {"type": "tool_result", "name": "search", "result": "..."}
data: {"type": "text", "content": " findings show..."}
data: {"type": "done", "metadata": {"tokens_in": 200, "tokens_out": 1500}}
```

---

### Improvement 6: IR-Driven Auto-Generation

**The insight:** The IR knows everything about the agent — its structure, data flow, tool dependencies, model requirements, expected inputs/outputs. We can generate things no one has thought to generate.

#### 6a. Auto-Generated OpenAPI Spec

From builder contracts:
```python
agent = (
    Agent("analyzer")
    .accepts(QueryInput)      # → OpenAPI request schema
    .returns(AnalysisOutput)  # → OpenAPI response schema
    .consumes(RequiredState)  # → documented dependencies
    .produces(OutputState)    # → documented outputs
)
```

Generate:
```yaml
paths:
  /v1/ask:
    post:
      summary: "analyzer agent"
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/QueryInput'
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AnalysisOutput'
```

#### 6b. Auto-Generated Client SDKs

From the OpenAPI spec, generate typed client SDKs:

```bash
adk-fluent codegen client agent.py --language typescript --output ./sdk/
adk-fluent codegen client agent.py --language python --output ./sdk/
```

Output:
```typescript
// Auto-generated TypeScript client for analyzer agent
export class AnalyzerClient {
  constructor(private baseUrl: string) {}

  async ask(input: QueryInput): Promise<AnalysisOutput> {
    const res = await fetch(`${this.baseUrl}/v1/ask`, {
      method: 'POST',
      body: JSON.stringify({ prompt: input.query, state: input }),
    });
    return res.json();
  }

  async *stream(input: QueryInput): AsyncGenerator<StreamEvent> {
    // SSE streaming implementation
  }
}
```

#### 6c. Auto-Generated Test Scaffolds

From the IR, generate test cases that cover the agent's structure:

```bash
adk-fluent codegen tests agent.py --output tests/
```

Generates tests for:
- Each agent node in the pipeline (mocked individually)
- State flow (data passes correctly between agents)
- Tool execution (each tool called with expected args)
- Error paths (fallback chains trigger correctly)
- Structured output (response matches schema)

#### 6d. Auto-Generated Cost Estimates

From the IR, estimate per-request cost before deployment:

```bash
adk-fluent estimate agent.py

  Pipeline: researcher → analyst → writer

  Per request estimate:
    researcher (gemini-2.5-flash):  ~500 tokens in, ~2000 out  = $0.002
    analyst    (gemini-2.5-flash):  ~2500 tokens in, ~1500 out = $0.003
    writer     (gemini-2.5-flash):  ~2000 tokens in, ~3000 out = $0.004
                                                         Total ≈ $0.009/request

  At 1000 requests/day: ~$9/day, ~$270/month

  Backend overhead:
    adk:      $0 (in-process)
    temporal:  ~$50/month (Temporal Cloud) or self-hosted
    dbos:      ~$20/month (PostgreSQL hosting)
    prefect:   ~$0 (Prefect Cloud free tier) or self-hosted
```

---

### Improvement 7: The Portable Agent Format (`.agent`)

**The most radical idea.** An agent should be as portable as a Docker image.

```bash
# Build a portable agent artifact
adk-fluent build agent.py --output research-pipeline.agent

# Run it anywhere
adk-fluent run research-pipeline.agent
adk-fluent serve research-pipeline.agent --port 8080

# Deploy it
adk-fluent deploy research-pipeline.agent --target cloudrun
adk-fluent deploy research-pipeline.agent --target temporal

# Inspect it
adk-fluent inspect research-pipeline.agent
```

**What's in a `.agent` file:**
- Serialized IR tree (the universal contract)
- Tool source code (or references to installed packages)
- Prompt templates
- Schema definitions
- Configuration (model, backend preferences)
- Dependency manifest
- Metadata (version, author, capabilities, cost estimate)

**Why this matters:**
- **Backend-agnostic deployment:** Same `.agent` file deploys to ADK, Temporal, Prefect, or DBOS
- **Versioning:** Immutable artifact with a hash — rollback means deploying an older `.agent`
- **Sharing:** Publish to a registry, others compose your agent into their pipelines
- **Auditing:** The IR is inspectable — you can verify what an agent does before deploying it

---

## 5. Beyond ADK: What 100x Engineers Would Build

### 5.1 The Agent Development Platform (ADP)

ADK is a great SDK. But the future isn't just SDKs — it's platforms. Here's what a platform looks like:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent Development Platform                       │
│                                                                     │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐  ┌────────┐│
│  │ Define  │→ │  Build   │→ │  Test   │→ │ Package  │→ │ Deploy ││
│  │         │  │          │  │         │  │          │  │        ││
│  │ fluent  │  │ IR +     │  │ mock,   │  │ Docker,  │  │ Cloud  ││
│  │ API     │  │ compile  │  │ eval,   │  │ K8s,     │  │ Run,   ││
│  │         │  │          │  │ conform │  │ worker   │  │ GKE,   ││
│  │ IDE     │  │ validate │  │         │  │ codegen  │  │ Agent  ││
│  │ plugin  │  │ optimize │  │ cost    │  │          │  │ Engine ││
│  └─────────┘  └──────────┘  │ estimate│  └──────────┘  └────────┘│
│                              └─────────┘                           │
│                                                                     │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────────────────┐ │
│  │ Observe │  │ Iterate  │  │ Share   │  │ Orchestrate          │ │
│  │         │  │          │  │         │  │                      │ │
│  │ trace,  │  │ A/B test,│  │ registry│  │ multi-agent routing, │ │
│  │ metrics,│  │ canary,  │  │ compose │  │ cross-service mesh,  │ │
│  │ cost    │  │ rollback │  │ publish │  │ traffic management   │ │
│  └─────────┘  └──────────┘  └─────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 The Five Things No Agent Framework Does Today

**1. Shadow Mode / Canary Deployments for Agents**

```python
# Deploy v2 alongside v1, compare outputs
adk-fluent deploy agent_v2.agent --canary 10%  # 10% traffic to v2
adk-fluent promote agent_v2.agent              # 100% traffic to v2
adk-fluent rollback                            # back to v1
```

No agent framework has traffic management. But this is exactly what you need when swapping models (GPT-4 → Gemini), changing prompts, or restructuring pipelines. The IR makes this possible because you can diff two agent versions structurally.

**2. Cost-Aware Routing at Runtime**

```python
pipeline = (
    Agent("researcher")
    .instruct("Research the topic.")
    .model("gemini-2.5-flash")
    .fallback_model("gemini-2.5-pro")  # if flash fails quality check
    .cost_ceiling(0.01)                 # max $0.01 per invocation
)
```

At runtime, the platform tracks cumulative cost and can:
- Route to cheaper models when budget is tight
- Alert when cost exceeds thresholds
- Automatically switch to cached/mocked responses in testing

**3. Structural Diff Between Agent Versions**

```bash
adk-fluent diff v1.agent v2.agent

  Changes:
  + Added agent "fact_checker" after "researcher"
  ~ Changed model for "writer": gemini-2.5-flash → gemini-2.5-pro
  ~ Modified instruction for "analyst": added constraint "cite sources"
  - Removed tool "deprecated_search" from "researcher"

  Impact:
    Cost per request: $0.009 → $0.015 (+67%)
    Pipeline depth: 3 → 4 (+1 step)
    New tool dependency: fact_check_api
```

**4. Agent Composition Registry**

Like npm for agents. Publish reusable agent components:

```python
# Install a community agent component
# pip install adk-fluent-research-agent

from adk_fluent_research_agent import researcher

# Compose into your pipeline
pipeline = researcher >> Agent("writer").instruct("Write report from {findings}.")
```

The key insight: because agents are defined as IR trees, they're composable at the IR level. You don't need to import someone's code — just their IR definition + tool references.

**5. Multi-Tenant Agent Serving**

```bash
# Serve multiple agents from a single process
adk-fluent serve agents/ --multi-tenant

  Agents loaded:
    /v1/research  → research_pipeline (3 agents)
    /v1/support   → support_agent (1 agent)
    /v1/code      → code_reviewer (2 agents)

  Shared resources:
    Model provider: gemini-2.5-flash (connection pooled)
    Session store: sqlite:///sessions.db
    Metrics: http://localhost:9090/metrics
```

### 5.3 The Developer Experience Pyramid

```
                    ┌───────────┐
                   │  Deploy   │  ← One command to production
                  │  adk-fluent deploy
                 ├─────────────┤
                │   Package    │  ← Auto-generated artifacts
               │  adk-fluent package
              ├───────────────┤
             │    Serve        │  ← Universal protocol gateway
            │  adk-fluent serve
           ├─────────────────┤
          │     Test           │  ← Auto-generated tests + evals
         │  .mock() .eval() .test()
        ├───────────────────┤
       │      Develop         │  ← Hot-reload dev server
      │  adk-fluent dev
     ├─────────────────────┤
    │       Define            │  ← Fluent API (TODAY)
   │  Agent("x").instruct("...")
  └───────────────────────────┘
```

Today adk-fluent owns the bottom layer. The proposal is to own the entire pyramid.

---

## 6. Prioritized Implementation Roadmap

### Phase 1: Foundation (High impact, enables everything else)

| Item | Effort | Impact | Description |
|------|--------|--------|-------------|
| `adk-fluent serve` | Medium | Critical | Universal HTTP/WS/SSE/A2A server from any builder |
| `adk-fluent dev` | Medium | Critical | Dev server with hot-reload and embedded UI |
| `/v1/ask`, `/v1/stream`, `/ws` endpoints | Medium | Critical | Standard API protocol for all frontends |

**Why first:** Without a serving layer, there's no way to connect agents to frontends. This unblocks everything.

### Phase 2: Packaging (Enables deployment)

| Item | Effort | Impact | Description |
|------|--------|--------|-------------|
| `adk-fluent package --target docker` | Low | High | Dockerfile + docker-compose generation |
| `adk-fluent package --target temporal` | Low | High | Worker code + Temporal docker-compose |
| `adk-fluent package --target cloudrun` | Low | Medium | Cloud Run service YAML + Dockerfile |
| `adk-fluent scaffold` | Low | Medium | Project scaffolding with best-practice structure |

**Why second:** Once you can serve, you need to package and deploy.

### Phase 3: Intelligence (IR-driven automation)

| Item | Effort | Impact | Description |
|------|--------|--------|-------------|
| OpenAPI auto-generation | Low | High | From `.accepts()` / `.returns()` contracts |
| Cost estimation | Low | Medium | From IR node types + model pricing |
| Test scaffold generation | Medium | Medium | From IR structure |
| Client SDK generation | Medium | Medium | TypeScript/Python clients from OpenAPI |

**Why third:** These are unique differentiators that no other agent framework offers.

### Phase 4: Platform (Long-term vision)

| Item | Effort | Impact | Description |
|------|--------|--------|-------------|
| `.agent` portable format | High | High | Serialized IR + deps as deployable artifact |
| Agent registry | High | Medium | Publish/discover/compose agents |
| Structural diff | Medium | Medium | Compare agent versions |
| Canary deployments | High | Medium | Traffic-split between agent versions |
| Multi-tenant serving | Medium | Medium | Multiple agents in single process |

---

## 7. Comparison: What Exists vs. What We'd Build

| Capability | ADK today | adk-fluent today | adk-fluent proposed |
|-----------|-----------|-------------------|---------------------|
| Define agent | Native SDK (verbose) | Fluent API (concise) | Same |
| Local test | `adk run` (CLI) | `.ask()` (programmatic) | `adk-fluent dev` (hot-reload server + UI) |
| Web UI | `adk web` (Angular, separate process) | Nothing | Embedded lightweight UI in `dev` |
| Serve as API | `adk api_server` (ADK only) | `A2AServer` (A2A only) | `adk-fluent serve` (REST+WS+SSE+A2A) |
| Package | Manual Dockerfile | Nothing | `adk-fluent package` (any target) |
| Deploy | `adk deploy` (3 targets) | Passthrough to `adk deploy` | `adk-fluent deploy` (any backend, any target) |
| Eval | `adk eval` (YAML-based) | `.eval()` (programmatic) | Both + auto-generated scaffolds |
| Observe | Basic events | M namespace middleware | Backend-aware tracing |
| Multi-backend | N/A (ADK only) | 5 backends (compile) | 5 backends (full lifecycle) |
| Cost tracking | None | None | IR-driven estimation + runtime tracking |
| OpenAPI | None | None | Auto-generated from contracts |
| Versioning | None | None | `.agent` artifacts with structural diff |

---

## 8. The North Star

```bash
# Define
cat agent.py
# pipeline = Agent("researcher") >> Agent("writer")

# Develop (hot-reload, embedded UI, event tracing)
adk-fluent dev agent.py

# Test (auto-generated from IR)
adk-fluent test agent.py

# Estimate cost
adk-fluent estimate agent.py

# Package for any target
adk-fluent package agent.py --target docker

# Deploy anywhere
adk-fluent deploy agent.py --target cloudrun --project my-proj

# Observe in production
# (built-in metrics, tracing, cost dashboard)

# Iterate
adk-fluent diff v1.agent v2.agent
adk-fluent deploy v2.agent --canary 10%
adk-fluent promote v2.agent
```

**From 1 line of agent definition to production deployment, any backend, any target, any frontend — with full observability and cost control.**

That's what 100x engineers build.
