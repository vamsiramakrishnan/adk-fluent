# Appendix B: Deployment Targets Deep Dive

> Every deployment target, what it takes, what we generate, and where config lives.

---

## 1. The Complete Deployment Target Matrix

### 1.1 Targets by Backend

| Target | ADK | Temporal | Prefect | DBOS | asyncio |
|--------|-----|----------|---------|------|---------|
| **Docker (generic)** | Yes | Yes | Yes | Yes | Yes |
| **Cloud Run** | Yes (`adk deploy`) | Yes (container) | Yes (container) | Yes (container) | Yes (container) |
| **Agent Engine** | Yes (`adk deploy`) | No | No | No | No |
| **GKE / K8s** | Yes (`adk deploy`) | Yes (Helm) | Yes (Helm/K8s) | Yes (K8s + PG) | Yes (K8s) |
| **AWS Lambda** | Partial | No* | No* | No* | Yes (handler wrap) |
| **AWS ECS/Fargate** | Yes (container) | Yes (container) | Yes (container) | Yes (container) | Yes (container) |
| **Azure Container Apps** | Yes (container) | Yes (container) | Yes (container) | Yes (container) | Yes (container) |
| **Temporal Cloud** | N/A | Yes (worker) | N/A | N/A | N/A |
| **Prefect Cloud** | N/A | N/A | Yes (deployment) | N/A | N/A |
| **DBOS Cloud** | N/A | N/A | N/A | Yes (app) | N/A |
| **Bare metal / VM** | Yes (systemd) | Yes (systemd) | Yes (systemd) | Yes (systemd) | Yes (systemd) |

\*Lambda is unsuitable for Temporal/Prefect/DBOS because they need long-running processes (workers/servers). Lambda's 15-minute timeout and cold starts conflict with durable execution's model. DBOS has a special Lambda integration for short-lived workflows, but it's an edge case.

### 1.2 What Gets Generated Per Target

#### Docker (generic)

```
output/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
└── requirements.txt (if not using pyproject.toml)
```

**Dockerfile decisions:**
- Base image: `python:3.12-slim` (not alpine — google-adk has native deps that break on musl)
- Multi-stage build: No (adds complexity, marginal size reduction given google-adk's dep weight)
- Non-root user: Yes (security best practice)
- Health check: `HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"` (avoid curl dependency)

#### Cloud Run

```
output/
├── Dockerfile
├── .dockerignore
├── cloudbuild.yaml           # Cloud Build pipeline
├── service.yaml              # Cloud Run service definition
├── .env.example
└── deploy.sh                 # One-command deploy script
```

**Cloud Run specifics:**
- `PORT` environment variable (Cloud Run sets this, don't hardcode 8080)
- `--allow-unauthenticated` flag decision (default: no, require IAM)
- Memory: 512Mi minimum (google-adk import alone needs ~300 MB)
- CPU: 1 (sufficient for most agent workloads, LLM calls are I/O-bound)
- Concurrency: 80 (default, tune based on agent complexity)
- Min instances: 0 (cost), 1 (latency) — make configurable

#### Kubernetes (generic)

```
output/
├── Dockerfile
├── k8s/
│   ├── namespace.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml        # Non-secret configuration
│   ├── hpa.yaml              # Horizontal Pod Autoscaler
│   └── ingress.yaml          # Optional: external access
├── .dockerignore
└── .env.example
```

**K8s decisions:**
- Liveness probe: `/health` (TCP, 10s interval)
- Readiness probe: `/ready` (HTTP, 15s interval, checks model provider)
- Resource requests: 256Mi memory, 250m CPU (minimum for google-adk)
- Resource limits: 1Gi memory, 1 CPU (adjust based on agent)
- HPA: scale on CPU 70% threshold (LLM calls are I/O, CPU is misleading — custom metrics preferred)

#### Temporal Worker

```
output/
├── worker.py                  # Generated from temporal_worker.py codegen
├── Dockerfile
├── docker-compose.yml         # Includes Temporal server + PostgreSQL
├── .dockerignore
├── .env.example
└── requirements.txt
```

**docker-compose includes:**
```yaml
services:
  temporal:
    image: temporalio/auto-setup:latest
    ports: ["7233:7233"]
    environment:
      DB: postgresql
      DB_PORT: 5432
      POSTGRES_USER: temporal
      POSTGRES_PWD: temporal
      POSTGRES_SEEDS: postgresql
    depends_on: [postgresql]

  temporal-ui:
    image: temporalio/ui:latest
    ports: ["8233:8080"]
    environment:
      TEMPORAL_ADDRESS: temporal:7233

  postgresql:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: temporal
    volumes:
      - temporal-pg-data:/var/lib/postgresql/data

  worker:
    build: .
    depends_on: [temporal]
    environment:
      TEMPORAL_ADDRESS: temporal:7233
      GOOGLE_API_KEY: ${GOOGLE_API_KEY}
    command: ["python", "worker.py"]
```

#### Prefect Deployment

```
output/
├── flow.py                    # Generated from prefect_worker.py codegen
├── prefect.yaml               # Deployment manifest
├── Dockerfile
├── docker-compose.yml         # Includes Prefect server + PostgreSQL
├── .dockerignore
└── .env.example
```

#### DBOS Application

```
output/
├── app.py                     # Generated from dbos_worker.py codegen
├── dbos-config.yaml           # DBOS configuration
├── Dockerfile
├── docker-compose.yml         # Includes PostgreSQL
├── .dockerignore
└── .env.example
```

**DBOS docker-compose is the simplest** — just PostgreSQL:
```yaml
services:
  postgresql:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: dbos
      POSTGRES_USER: dbos
      POSTGRES_PASSWORD: dbos
    volumes:
      - dbos-pg-data:/var/lib/postgresql/data

  app:
    build: .
    depends_on: [postgresql]
    environment:
      DBOS_DATABASE_URL: postgresql://dbos:dbos@postgresql:5432/dbos
      GOOGLE_API_KEY: ${GOOGLE_API_KEY}
    ports: ["8080:8080"]
```

---

## 2. Configuration Externalization

### 2.1 The Problem

Agent definitions embed configuration: model names, API endpoints, instructions, tool URLs. In production, these need to be externalized (env vars, config files, secret managers).

**Today's situation:**
```python
# Hardcoded — works for dev, breaks for production
agent = Agent("helper", "gemini-2.5-flash").instruct("You are a helpful assistant.")
```

### 2.2 The Three-Layer Config Model

```
┌──────────────────────────────────────────┐
│ Layer 1: Code Defaults (agent.py)        │  ← Version controlled
│   Model: "gemini-2.5-flash"              │
│   Instruction: "You are helpful."        │
│   Backend: "adk"                         │
├──────────────────────────────────────────┤
│ Layer 2: Config File (config.yaml)       │  ← Environment-specific
│   Model: "gemini-2.5-pro"  # override   │
│   Backend: "temporal"       # override   │
│   Temporal task queue: "prod-agents"     │
├──────────────────────────────────────────┤
│ Layer 3: Environment Variables           │  ← Secrets, per-deployment
│   GOOGLE_API_KEY=...                     │
│   TEMPORAL_ADDRESS=temporal.prod:7233    │
│   DATABASE_URL=postgresql://...          │
└──────────────────────────────────────────┘
```

**Resolution order:** Env vars > config file > code defaults

### 2.3 Proposed Config File Format

```yaml
# adk-fluent.yaml (or .adk-fluent.yaml)
version: "1"

# Agent overrides (keyed by agent name)
agents:
  helper:
    model: ${MODEL_NAME:-gemini-2.5-flash}
    instruction: "You are a production assistant."

# Backend configuration
backend:
  name: ${BACKEND:-adk}
  temporal:
    address: ${TEMPORAL_ADDRESS:-localhost:7233}
    task_queue: ${TEMPORAL_TASK_QUEUE:-agents}
    namespace: ${TEMPORAL_NAMESPACE:-default}
  prefect:
    server_url: ${PREFECT_API_URL:-http://localhost:4200/api}
    work_pool: ${PREFECT_WORK_POOL:-default}
  dbos:
    database_url: ${DATABASE_URL:-postgresql://localhost:5432/dbos}

# Server configuration (for adk-fluent serve)
server:
  host: ${HOST:-0.0.0.0}
  port: ${PORT:-8080}
  workers: ${WORKERS:-1}
  cors_origins: ["*"]

# Session management
sessions:
  store: ${SESSION_STORE:-memory}  # memory | sqlite | postgresql
  sqlite_path: ${SESSION_DB:-./sessions.db}
  ttl_seconds: 3600

# Observability
observability:
  log_level: ${LOG_LEVEL:-INFO}
  otel_endpoint: ${OTEL_ENDPOINT:-}
  trace_sampling_rate: 0.1
```

### 2.4 How Config Flows Into the Builder

```python
# At startup, adk-fluent dev/serve reads config:
# 1. Load adk-fluent.yaml
# 2. Resolve ${ENV_VAR} references
# 3. Override builder defaults

# This happens transparently — the user's agent.py doesn't change:
agent = Agent("helper", "gemini-2.5-flash").instruct("Help.")

# But at serve time, if adk-fluent.yaml says model: gemini-2.5-pro,
# the resolved builder uses the override.
```

### 2.5 Secrets Management

**Never in config files. Always env vars or secret managers.**

For `adk-fluent package`, we generate a `.env.example`:
```bash
# .env.example — copy to .env and fill in values
GOOGLE_API_KEY=your-api-key-here
# OPENAI_API_KEY=your-openai-key-here
# ANTHROPIC_API_KEY=your-anthropic-key-here

# Backend-specific (uncomment as needed)
# TEMPORAL_ADDRESS=localhost:7233
# PREFECT_API_URL=http://localhost:4200/api
# DATABASE_URL=postgresql://user:pass@localhost:5432/dbos
```

For Cloud Run / GKE, we reference Secret Manager:
```yaml
# Cloud Run service.yaml snippet
spec:
  template:
    spec:
      containers:
        - env:
            - name: GOOGLE_API_KEY
              valueFrom:
                secretKeyRef:
                  name: google-api-key
                  key: latest
```

### 2.6 The Trade-off: Config File vs. Programmatic

| Approach | Pros | Cons |
|----------|------|------|
| **Config file** (adk-fluent.yaml) | Externalized, env-specific, ops-friendly | Another file to manage, another format to learn |
| **Programmatic** (configure()) | Pythonic, type-safe, IDE autocomplete | Hardcoded in source, can't change without redeploying code |
| **Env vars only** | Simple, universal, K8s/Docker native | No structure, hard to manage many vars |

**Recommendation:** Support all three. Config file for structured deployment settings, `configure()` for defaults, env vars for secrets and overrides. Don't force any single approach.

---

## 3. Deployment Target Deep Dives

### 3.1 Cloud Run — The 80% Case

Most adk-fluent users will deploy to Cloud Run. It's the lowest friction path from `adk deploy` and the default Google Cloud target.

**What we generate that `adk deploy cloud_run` doesn't:**
- A `Dockerfile` the user can inspect and customize
- A `cloudbuild.yaml` for CI/CD (not just one-time deploy)
- A `service.yaml` for declarative deployments (GitOps)
- A `deploy.sh` that wraps `gcloud run deploy` with the right flags

**Cloud Run constraints that affect agent design:**
- **Cold start:** 5-30 seconds (google-adk import is heavy). Mitigation: min-instances=1 for production.
- **Request timeout:** 300 seconds default, 3600 max. Long agent pipelines may need timeout extension.
- **Memory:** 512 Mi minimum recommended. google-adk + pyarrow + grpcio need ~300 MB at import.
- **Concurrency:** Default 80 concurrent requests. Agents are I/O-bound (waiting for LLM), so high concurrency is fine.
- **No persistent disk:** Sessions must use external store (SQLite on /tmp is ephemeral, use Firestore/Cloud SQL for persistence).

### 3.2 Agent Engine — The Managed Path

Agent Engine is Google's managed agent hosting. `adk deploy agent_engine` handles everything.

**What we DON'T generate:** Agent Engine is opaque — it builds and deploys internally. We just need the `root_agent` variable in `agent.py`.

**What we CAN add:**
- Validation that the builder is Agent Engine-compatible (no unsupported tools, no local file I/O)
- A `--dry-run` that checks Agent Engine constraints without deploying
- Cost estimation based on Agent Engine pricing

### 3.3 Generic Kubernetes — The Enterprise Path

For teams running their own K8s clusters (not GKE specifically).

**Generated manifests assume:**
- Namespace isolation (one namespace per agent)
- ConfigMap for non-secret configuration
- Secrets referenced but not generated (user creates them)
- HPA for autoscaling (but with a caveat — see below)

**The HPA caveat:** HPA scales on CPU/memory metrics. Agent workloads are I/O-bound (waiting for LLM APIs). CPU will be low even under high load. Better metrics:
- Custom metric: request queue depth
- Custom metric: concurrent active sessions
- External metric: LLM API latency (scale up when latency increases, indicating congestion)

We should generate an HPA with a comment explaining this, and a KEDA ScaledObject alternative for teams using KEDA.

### 3.4 AWS Lambda — The Controversial Target

Lambda is technically possible for simple, short-lived agents. But it's a poor fit for:
- Multi-turn sessions (Lambda is stateless)
- Streaming (Lambda responses are synchronous unless using Lambda URLs)
- Durable backends (Temporal/Prefect/DBOS need long-running workers)

**What we'd generate:**
```python
# handler.py — AWS Lambda handler for adk-fluent agent
import json
from agent import agent

def handler(event, context):
    body = json.loads(event.get("body", "{}"))
    prompt = body.get("prompt", "")
    # Note: This is a sync call. Consider Lambda timeout (default 3s, max 900s).
    result = agent.ask(prompt)
    return {
        "statusCode": 200,
        "body": json.dumps({"text": result}),
    }
```

**Honest recommendation:** Don't use Lambda for agent workloads unless:
- Single-turn only (no sessions)
- Fast model (gemini-flash, < 10s response)
- Low traffic (cold starts are expensive with google-adk's import weight)

We should generate the Lambda handler but include a prominent warning about these constraints.

### 3.5 Bare Metal / systemd — The Forgotten Target

Some teams deploy to VMs. They need:
```
output/
├── agent-service.service      # systemd unit file
├── install.sh                 # Setup script (venv, deps, user)
└── .env.example
```

```ini
# agent-service.service
[Unit]
Description=adk-fluent agent server
After=network.target

[Service]
Type=simple
User=agent
WorkingDirectory=/opt/agent
EnvironmentFile=/opt/agent/.env
ExecStart=/opt/agent/.venv/bin/adk-fluent serve agent.py --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 4. The Multi-Backend Deployment Decision Tree

```
Is your agent stateless (single-turn)?
├── Yes → Docker / Cloud Run / Lambda (simple container)
└── No (multi-turn, needs sessions)
    │
    Does it need crash recovery?
    ├── No → Docker / Cloud Run with external session store
    └── Yes (durable execution needed)
        │
        How much infrastructure can you manage?
        ├── Minimal → DBOS (just PostgreSQL)
        ├── Some → Prefect (server + workers)
        └── Full → Temporal (server + workers + monitoring)
            │
            Where are you deploying?
            ├── Google Cloud → Cloud Run / GKE / Agent Engine
            ├── AWS → ECS / Fargate / EKS
            ├── Azure → Container Apps / AKS
            └── On-prem → K8s / Docker Compose / systemd
```

`adk-fluent package` should walk the user through this decision tree (or accept the answers as flags).

---

## 5. What We're NOT Building

To be explicit about scope:

1. **No CI/CD pipeline** — We generate build manifests, not GitHub Actions / Cloud Build pipelines (except as optional scaffold templates)
2. **No secret management** — We reference secrets via env vars; we don't create them in Vault/Secret Manager
3. **No DNS/domain management** — We configure ports and health checks; we don't set up domains
4. **No SSL/TLS termination** — Handled by Cloud Run, ingress controllers, or load balancers
5. **No auto-scaling policies** — We generate HPA templates with sensible defaults; tuning is the user's job
6. **No multi-region deployment** — That's infrastructure architecture, not agent packaging
