# Appendix D: Local Development Infrastructure — The "minikube for Orchestrators" Problem

> How do we make Temporal, Prefect, and DBOS as easy to run locally as `minikube start`?

---

## 1. The Problem Statement

### 1.1 Local K8s: A Solved Problem

Running Kubernetes locally is a solved problem with multiple mature options:

| Tool | Approach | Startup Time | Memory | Complexity |
|------|----------|-------------|--------|------------|
| **minikube** | VM or container | 30-60s | ~2 GB | Low |
| **kind** | Docker containers as nodes | 15-30s | ~500 MB | Very low |
| **k3d** | k3s in Docker | 10-20s | ~300 MB | Very low |
| **Docker Desktop** | Embedded K8s | Pre-running | ~1.5 GB | Zero (just enable) |

A developer can go from zero to a running K8s cluster in under a minute.

### 1.2 Local Orchestrators: An Unsolved Problem

Running Temporal, Prefect, or DBOS locally is significantly harder:

| Orchestrator | Local Setup Steps | Time to First Run | Memory Footprint |
|-------------|-------------------|-------------------|------------------|
| **Temporal** | Install CLI, start dev server OR docker-compose with PostgreSQL | 2-5 min | ~500 MB (server + DB) |
| **Prefect** | `pip install prefect`, `prefect server start` OR docker-compose | 1-3 min | ~250 MB (Python) + 200 MB (DB) |
| **DBOS** | `pip install dbos`, configure PostgreSQL OR use SQLite | 1-2 min | ~50 MB (SQLite) or ~200 MB (PostgreSQL) |

None of these are terrible. But none are one-command either.

### 1.3 What "One Command" Looks Like

The goal:

```bash
# Start a local Temporal environment with agent worker
adk-fluent dev agent.py --backend temporal
# Starts: Temporal server + PostgreSQL + Temporal UI + worker process
# All in Docker, managed by adk-fluent

# Start a local Prefect environment
adk-fluent dev agent.py --backend prefect
# Starts: Prefect server + PostgreSQL + worker

# Start a local DBOS environment
adk-fluent dev agent.py --backend dbos
# Starts: PostgreSQL + DBOS app
# (DBOS can also use SQLite, in which case: no Docker needed)
```

---

## 2. Architecture: How It Would Work

### 2.1 The Layered Approach

```
┌──────────────────────────────────────────┐
│  adk-fluent dev agent.py --backend X     │  ← User command
├──────────────────────────────────────────┤
│  Backend Detector                         │  ← Reads builder's .engine()
│  Determines: what infra is needed         │
├──────────────────────────────────────────┤
│  Infrastructure Manager                   │  ← Manages Docker containers
│  Starts/stops backend services            │
│  Health checks on dependent services      │
├──────────────────────────────────────────┤
│  Worker/App Process                       │  ← Hot-reloaded Python process
│  Connects to backend infra                │
│  Executes agent via compile → run path    │
├──────────────────────────────────────────┤
│  Protocol Gateway                         │  ← HTTP/WS/SSE endpoints
│  Same API regardless of backend           │
└──────────────────────────────────────────┘
```

### 2.2 Infrastructure Manager Design

The Infrastructure Manager uses Docker (via subprocess, not the Docker Python SDK — to avoid adding docker-py as a dependency).

```python
class InfraManager:
    """Manages local Docker infrastructure for backend services."""

    def start_temporal(self) -> InfraState:
        """Start Temporal server + PostgreSQL for local development."""
        # 1. Check if Docker is available
        # 2. Check if Temporal is already running (port 7233)
        # 3. If not, start via docker compose
        # 4. Wait for health check
        # 5. Return connection details

    def start_prefect(self) -> InfraState:
        """Start Prefect server + PostgreSQL."""
        # Similar pattern

    def start_dbos(self) -> InfraState:
        """Start PostgreSQL for DBOS (or use SQLite)."""
        # If SQLite mode: no Docker needed, return immediately
        # If PostgreSQL mode: start PG container

    def stop_all(self) -> None:
        """Clean shutdown of all managed containers."""

    def status(self) -> dict:
        """Check health of all managed services."""
```

### 2.3 The Docker Compose Files (Embedded)

Each backend's docker-compose.yml is embedded in the package as a template. When `adk-fluent dev --backend temporal` runs, it:

1. Renders the template to a temp directory
2. Runs `docker compose -f /tmp/adk-fluent-infra-{hash}/docker-compose.yml up -d`
3. Waits for health checks to pass
4. Starts the worker/app process connected to the infra
5. On exit: runs `docker compose down` (or leaves running with `--keep-infra`)

### 2.4 Per-Backend Infra Details

#### Temporal Local Stack

```yaml
# Embedded in adk_fluent/templates/infra/temporal-compose.yml
services:
  temporal-dev:
    image: temporalio/auto-setup:latest
    container_name: adk-fluent-temporal
    ports:
      - "${TEMPORAL_PORT:-7233}:7233"
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
      - POSTGRES_SEEDS=temporal-db
    depends_on:
      temporal-db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "tctl", "--address", "localhost:7233", "cluster", "health"]
      interval: 5s
      timeout: 3s
      retries: 10

  temporal-ui:
    image: temporalio/ui:latest
    container_name: adk-fluent-temporal-ui
    ports:
      - "${TEMPORAL_UI_PORT:-8233}:8080"
    environment:
      - TEMPORAL_ADDRESS=temporal-dev:7233

  temporal-db:
    image: postgres:16-alpine
    container_name: adk-fluent-temporal-db
    environment:
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: temporal
    volumes:
      - adk-fluent-temporal-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U temporal"]
      interval: 3s
      timeout: 2s
      retries: 5

volumes:
  adk-fluent-temporal-data:
```

**Key decisions:**
- **Named containers** with `adk-fluent-` prefix — easy to identify and manage
- **Named volumes** for data persistence between runs
- **Health checks** — `adk-fluent dev` waits for these before starting the worker
- **Temporal UI** included — opens at http://localhost:8233 for workflow inspection

#### Prefect Local Stack

```yaml
services:
  prefect-server:
    image: prefecthq/prefect:3-latest
    container_name: adk-fluent-prefect
    command: prefect server start --host 0.0.0.0
    ports:
      - "${PREFECT_PORT:-4200}:4200"
    environment:
      PREFECT_API_DATABASE_CONNECTION_URL: postgresql+asyncpg://prefect:prefect@prefect-db:5432/prefect
    depends_on:
      prefect-db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:4200/api/health')"]
      interval: 5s
      timeout: 3s
      retries: 10

  prefect-db:
    image: postgres:16-alpine
    container_name: adk-fluent-prefect-db
    environment:
      POSTGRES_USER: prefect
      POSTGRES_PASSWORD: prefect
      POSTGRES_DB: prefect
    volumes:
      - adk-fluent-prefect-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U prefect"]
      interval: 3s
      timeout: 2s
      retries: 5

volumes:
  adk-fluent-prefect-data:
```

**Prefect gotcha:** The Prefect server itself is heavy (~250 MB RAM). On machines with < 8 GB RAM, this may be uncomfortable alongside the agent process. We should print a warning.

#### DBOS Local Stack

DBOS is the simplest — it only needs PostgreSQL (or can use SQLite for development):

```yaml
services:
  dbos-db:
    image: postgres:16-alpine
    container_name: adk-fluent-dbos-db
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    environment:
      POSTGRES_USER: dbos
      POSTGRES_PASSWORD: dbos
      POSTGRES_DB: dbos
    volumes:
      - adk-fluent-dbos-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dbos"]
      interval: 3s
      timeout: 2s
      retries: 5

volumes:
  adk-fluent-dbos-data:
```

**SQLite mode:** For zero-Docker development:
```bash
adk-fluent dev agent.py --backend dbos --dbos-sqlite
# Uses SQLite instead of PostgreSQL — no Docker needed
# Data stored in .adk-fluent/dbos.sqlite
```

---

## 3. The UX Flow in Detail

### 3.1 First Run (Infrastructure Not Running)

```bash
$ adk-fluent dev agent.py --backend temporal

  adk-fluent dev v0.X.0

  Backend: temporal
  Infrastructure: starting...
    [1/3] Starting PostgreSQL...        ✓ (port 5432)
    [2/3] Starting Temporal Server...   ✓ (port 7233)
    [3/3] Starting Temporal UI...       ✓ (port 8233)

  Infrastructure ready in 12s

  Agent:     research_pipeline (3 agents, 2 tools)
  Worker:    compiling IR → Temporal workflow...
  Server:    http://localhost:8080

  Endpoints:
    POST /v1/ask       — execute workflow
    POST /v1/stream    — stream workflow events
    GET  /health       — health check

  Dashboards:
    http://localhost:8080/ui   — agent chat
    http://localhost:8233      — Temporal UI (workflow history)

  Watching agent.py for changes... (Ctrl+C to stop)
```

### 3.2 Subsequent Runs (Infrastructure Already Running)

```bash
$ adk-fluent dev agent.py --backend temporal

  adk-fluent dev v0.X.0

  Backend: temporal
  Infrastructure: already running ✓
    PostgreSQL:     localhost:5432 (healthy)
    Temporal:       localhost:7233 (healthy)
    Temporal UI:    localhost:8233 (healthy)

  Agent:     research_pipeline (3 agents, 2 tools)
  Server:    http://localhost:8080

  Watching agent.py for changes...
```

### 3.3 Cleanup

```bash
# Stop dev server but keep infra running (for quick restarts)
Ctrl+C
# Output: "Server stopped. Infrastructure still running. Use --stop-infra to tear down."

# Explicit teardown
adk-fluent infra stop
# Output: "Stopped: temporal, temporal-db, temporal-ui. Volumes preserved."

# Full cleanup including data
adk-fluent infra stop --volumes
# Output: "Stopped and removed all adk-fluent infrastructure and data."
```

### 3.4 Infrastructure Management Commands

```bash
# Check status of managed infrastructure
adk-fluent infra status

  adk-fluent infrastructure status:

  Service          Status    Port    Memory
  temporal         running   7233    120 MB
  temporal-ui      running   8233    45 MB
  temporal-db      running   5432    30 MB

  Total: 195 MB

# Start specific backend infra without running an agent
adk-fluent infra start temporal

# Stop all
adk-fluent infra stop

# View logs
adk-fluent infra logs temporal
```

---

## 4. Trade-offs and Design Decisions

### 4.1 Docker as a Dependency

**Decision:** Require Docker for local orchestrator development.

**Pros:**
- Docker is near-universal among developers
- Containers are reproducible and isolated
- Docker Compose handles multi-service orchestration well
- No need to install Temporal/Prefect/PostgreSQL natively

**Cons:**
- Docker Desktop is not free for large companies (> 250 employees, > $10M revenue)
- Docker Desktop on macOS uses ~2 GB RAM baseline
- Windows users on WSL2 have additional complexity
- CI environments may not have Docker easily available

**Mitigation:**
- Support Podman as an alternative (`DOCKER_HOST` env var)
- DBOS offers SQLite mode (zero Docker)
- Document the "native install" path for users who can't use Docker
- For CI, provide instructions for Docker-in-Docker or service containers

### 4.2 Subprocess vs. Docker SDK

**Decision:** Use `subprocess.run(["docker", "compose", ...])` not the `docker` Python package.

**Pros:**
- Zero new dependencies (docker-py is another 5 MB + requests + websocket-client)
- Works with any Docker-compatible CLI (Docker, Podman, nerdctl)
- The compose file format is the stable contract, not the Python API

**Cons:**
- Error handling is more complex (parse stdout/stderr)
- No programmatic container inspection (must parse `docker inspect` JSON)
- Path escaping on Windows needs care

**This is the right call.** Adding `docker-py` as a dependency would increase install size meaningfully and create version conflicts (docker-py pins specific `requests` versions).

### 4.3 Data Persistence Between Runs

**Decision:** Use Docker named volumes that survive `docker compose down`.

**Pros:**
- Temporal workflow history preserved between restarts
- Prefect flow run history preserved
- DBOS step records preserved (this is the whole point of durable execution)

**Cons:**
- Volumes grow over time (PostgreSQL WAL, etc.)
- Users may not realize data is persisting and get confused by stale state
- Need a cleanup command (`adk-fluent infra stop --volumes`)

### 4.4 Port Conflicts

**Decision:** Use configurable ports with sensible defaults.

| Service | Default Port | Env Override |
|---------|-------------|--------------|
| Agent server | 8080 | `PORT` |
| Temporal gRPC | 7233 | `TEMPORAL_PORT` |
| Temporal UI | 8233 | `TEMPORAL_UI_PORT` |
| Prefect server | 4200 | `PREFECT_PORT` |
| PostgreSQL | 5432 | `POSTGRES_PORT` |

If a port is in use, `adk-fluent dev` should detect this and suggest an alternative:
```
Port 7233 is in use. Temporal may already be running.
  Use existing? [Y/n]:
  Or specify different port: TEMPORAL_PORT=7234 adk-fluent dev ...
```

### 4.5 Memory Budget

Total memory footprint for local development:

| Setup | Memory |
|-------|--------|
| ADK backend (no infra) | ~400 MB (Python + google-adk) |
| Temporal backend | ~600 MB (Python + Temporal server + PostgreSQL) |
| Prefect backend | ~850 MB (Python + Prefect server + PostgreSQL) |
| DBOS backend (PostgreSQL) | ~600 MB (Python + PostgreSQL) |
| DBOS backend (SQLite) | ~400 MB (Python only) |

On an 8 GB machine, any of these is comfortable. On 4 GB, Prefect may be tight. We should document memory requirements.

---

## 5. The "Production-Like" vs. "Fast" Trade-off

### 5.1 The minikube Lesson

minikube offers profiles:
- `minikube start` — single-node, minimal, fast
- `minikube start --cpus 4 --memory 8g` — more realistic
- `minikube start --kubernetes-version v1.28` — specific version

We should offer similar flexibility:

```bash
# Fast mode: minimal infra, quick startup
adk-fluent dev agent.py --backend temporal
# Uses: temporalio/auto-setup (all-in-one), SQLite

# Production-like: separate services, PostgreSQL
adk-fluent dev agent.py --backend temporal --production-like
# Uses: separate temporal-server, temporal-frontend, temporal-history,
#        temporal-matching, elasticsearch, postgresql

# Specify versions
adk-fluent dev agent.py --backend temporal --temporal-version 1.24
```

**Default:** Fast mode. Production-like mode is for debugging production issues.

### 5.2 The Temporal-Specific Challenge

Temporal's `auto-setup` Docker image bundles everything into one container. This is great for development but different from production, where Temporal runs as 4 separate services (frontend, history, matching, worker).

**Decision:** Use `auto-setup` for `adk-fluent dev` (fast, simple). Generate separate services for `adk-fluent package --target temporal` (production-like).

### 5.3 The Prefect-Specific Challenge

Prefect 3's server has two modes:
1. **In-process** (`prefect server start`) — runs in the same Python process, uses SQLite
2. **Docker** — runs in a container with PostgreSQL

For `adk-fluent dev`, the in-process mode is tempting (no Docker needed!) but problematic:
- It blocks the terminal
- It shares the Python process with the agent worker
- Import conflicts between adk-fluent deps and Prefect deps

**Decision:** Use Docker-based Prefect server for `adk-fluent dev`. It's isolated and predictable.

**Exception:** If Prefect is already running locally (detected via API health check), use it instead of starting a new container.

---

## 6. Comparison: How Other Tools Handle Local Dev

### 6.1 Temporal CLI (`temporal server start-dev`)

The Temporal CLI includes a built-in dev server. No Docker needed:
```bash
temporal server start-dev
# Starts in-memory Temporal server on port 7233
# No PostgreSQL, no persistence between restarts
# UI at http://localhost:8233
```

**Pros:** Zero-dependency, instant start, no Docker.
**Cons:** No persistence. Workflow history lost on restart. Not suitable for testing durable execution.

We should detect if `temporal` CLI is available and offer this as a fast-start option:
```bash
$ adk-fluent dev agent.py --backend temporal

  Temporal CLI detected. Use lightweight dev server? [Y/n]
  Note: In-memory only, no persistence between restarts.
```

### 6.2 Prefect (`prefect server start`)

```bash
pip install prefect
prefect server start
# Starts Prefect server with SQLite on port 4200
```

**Pros:** No Docker needed, starts in ~5 seconds.
**Cons:** Runs in foreground (blocks terminal), heavy import (~250 MB RAM), SQLite has concurrency limits.

### 6.3 DBOS (`dbos start`)

```bash
pip install dbos
# Configure dbos-config.yaml with database_url
dbos start
```

**Pros:** Lightweight, can use SQLite for zero-infra dev.
**Cons:** Requires database configuration (either SQLite path or PostgreSQL URL).

### 6.4 Our Value-Add

None of these tools integrate the orchestrator setup with the agent development experience. The developer has to:
1. Start the orchestrator in terminal 1
2. Start the worker in terminal 2
3. Start the agent server in terminal 3
4. Open the orchestrator UI in a browser tab
5. Open the agent UI in another browser tab

`adk-fluent dev --backend X` collapses all 5 steps into one command.

---

## 7. The Docker-Free Path

### 7.1 For DBOS

DBOS with SQLite requires zero Docker and zero external services:
```bash
adk-fluent dev agent.py --backend dbos
# Automatically uses SQLite at .adk-fluent/dbos.sqlite
# No Docker needed, no PostgreSQL needed
# Durable execution works (stored in SQLite)
```

This is genuinely compelling. DBOS + SQLite gives you durable execution with zero infrastructure setup. The only limitation is that SQLite doesn't support concurrent workers (single-process only).

### 7.2 For Temporal

Use the Temporal CLI's in-memory dev server:
```bash
adk-fluent dev agent.py --backend temporal --dev-server
# Uses `temporal server start-dev` (in-memory, no persistence)
# Requires: Temporal CLI installed
```

### 7.3 For Prefect

Use Prefect's built-in server:
```bash
adk-fluent dev agent.py --backend prefect --in-process
# Starts Prefect server in a background thread
# Uses SQLite, lightweight but RAM-heavy
```

### 7.4 The Decision Matrix

```
Does user have Docker?
├── Yes → Use Docker-based infra (default, recommended)
│         Full persistence, production-like behavior
└── No
    ├── Backend is DBOS? → Use SQLite mode (zero deps)
    ├── Backend is Temporal? → Check for `temporal` CLI
    │   ├── CLI available → Use temporal server start-dev (in-memory)
    │   └── CLI not available → Error: "Install Docker or Temporal CLI"
    └── Backend is Prefect? → Use prefect server in-process
        └── (Warning: heavy RAM usage, ~250 MB)
```
