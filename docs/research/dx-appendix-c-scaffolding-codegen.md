# Appendix C: Scaffolding and Codegen Architecture

> How template generation works, what we generate, and the engineering tradeoffs in codegen design.

---

## 1. The Codegen Philosophy

### 1.1 Principle: Generate Starting Points, Not Final Artifacts

Every generated file should be:
- **Readable** — a developer should understand it without documentation
- **Editable** — the user will customize it, so don't generate magic
- **Deletable** — if the user doesn't need it, removing it shouldn't break anything
- **Minimal** — generate the minimum that works, not the maximum that's possible

**Anti-pattern:** Rails-style generators that create 15 files, half of which the user never touches and can't safely delete. We've all seen `scaffold user` create controllers, views, helpers, assets, tests, and migration files — where deleting the helper breaks the controller.

**Our pattern:** Each generated file is self-contained. The Dockerfile doesn't reference a specific docker-compose.yml. The worker.py doesn't require a specific config file. Every file works independently.

### 1.2 Principle: Jinja2 Templates, Not String Concatenation

The existing worker codegen (temporal_worker.py, prefect_worker.py, dbos_worker.py) uses string concatenation:

```python
lines.append(f"@DBOS.step()")
lines.append(f"async def {safe_name}_step(")
```

This works for Python codegen where we're building AST-like structures. But for Dockerfiles, YAML manifests, and shell scripts, Jinja2 templates are clearer:

```dockerfile
# templates/docker/Dockerfile.j2
FROM python:{{ python_version }}-slim

WORKDIR /app

{% if use_uv %}
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
{% else %}
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
{% endif %}

COPY . .

RUN useradd --create-home agent
USER agent

EXPOSE {{ port }}
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:{{ port }}/health')"

CMD ["adk-fluent", "serve", "{{ agent_module }}", "--port", "{{ port }}"]
```

### 1.3 Principle: Templates Live in the Package, Not Downloaded

Templates ship as package data inside `adk_fluent/templates/`. They're version-locked to the adk-fluent version. No network calls to fetch templates.

**Directory structure:**
```
src/adk_fluent/
├── templates/
│   ├── docker/
│   │   ├── Dockerfile.j2
│   │   ├── docker-compose.j2
│   │   └── dockerignore.j2
│   ├── cloudrun/
│   │   ├── Dockerfile.j2
│   │   ├── cloudbuild.j2
│   │   ├── service.j2
│   │   └── deploy.sh.j2
│   ├── k8s/
│   │   ├── deployment.j2
│   │   ├── service.j2
│   │   ├── configmap.j2
│   │   └── hpa.j2
│   ├── temporal/
│   │   ├── docker-compose.j2
│   │   └── Dockerfile.j2
│   ├── prefect/
│   │   ├── prefect.yaml.j2
│   │   ├── docker-compose.j2
│   │   └── Dockerfile.j2
│   ├── dbos/
│   │   ├── dbos-config.yaml.j2
│   │   ├── docker-compose.j2
│   │   └── Dockerfile.j2
│   ├── scaffold/
│   │   ├── agent.py.j2
│   │   ├── tools.py.j2
│   │   ├── schemas.py.j2
│   │   ├── config.py.j2
│   │   ├── test_agent.py.j2
│   │   ├── eval_basic.py.j2
│   │   ├── pyproject.toml.j2
│   │   ├── env.example.j2
│   │   └── ci.yml.j2
│   └── shared/
│       ├── env.example.j2
│       └── requirements.txt.j2
```

---

## 2. The Scaffold Command in Detail

### 2.1 `adk-fluent scaffold` — Interactive Mode

```bash
$ adk-fluent scaffold my-research-agent

  adk-fluent scaffold v0.X.0

  Agent name: my-research-agent
  Model [gemini-2.5-flash]:
  Backend [adk]: temporal
  Include tools? [Y/n]: y
  Include eval suite? [Y/n]: y
  Deployment target [docker]: cloudrun

  Creating my-research-agent/...
    agent.py              — Agent definition (fluent API)
    tools.py              — Tool function stubs
    schemas.py            — Input/output Pydantic models
    config.py             — Configuration loader
    pyproject.toml        — Dependencies (adk-fluent[temporal])
    Dockerfile            — Production container
    docker-compose.yml    — Local dev stack (Temporal + PostgreSQL)
    worker.py             — Temporal worker (generated)
    .env.example          — Environment variable template
    tests/
      test_agent.py       — Unit tests with .mock()
      test_tools.py       — Tool function tests
    evals/
      basic.py            — Evaluation suite
    .github/workflows/
      ci.yml              — GitHub Actions (lint, test, eval)

  Done! Next steps:
    cd my-research-agent
    cp .env.example .env   # Fill in API keys
    docker compose up -d   # Start Temporal server
    adk-fluent dev agent.py    # Start developing
```

### 2.2 `adk-fluent scaffold` — Non-Interactive Mode

```bash
adk-fluent scaffold my-agent \
  --model gemini-2.5-pro \
  --backend adk \
  --no-tools \
  --no-evals \
  --target docker
```

### 2.3 What Each Scaffold File Contains

**agent.py** (the most important file):
```python
"""my-research-agent — Agent definition."""

from adk_fluent import Agent, Pipeline

# Define your agent pipeline using the fluent API.
# See: https://vamsiramakrishnan.github.io/adk-fluent/

researcher = (
    Agent("researcher", "gemini-2.5-flash")
    .instruct("Research the given topic thoroughly.")
    .tool(web_search)
    .writes("findings")
)

writer = (
    Agent("writer", "gemini-2.5-flash")
    .instruct("Write a comprehensive report based on: {findings}")
    .returns(ReportOutput)
)

# Pipeline: researcher → writer
pipeline = researcher >> writer

# For adk web / adk run compatibility:
root_agent = pipeline.build()
```

**Key design choice:** The scaffold generates both fluent API code AND the `root_agent = pipeline.build()` line. This means the generated project works with both `adk-fluent dev` and `adk web/run/deploy` out of the box.

**tools.py:**
```python
"""Tool functions for my-research-agent."""

from typing import Any


def web_search(query: str) -> str:
    """Search the web for information.

    Args:
        query: The search query.

    Returns:
        Search results as text.
    """
    # TODO: Implement your tool logic here.
    # Consider using:
    #   - Google Search API
    #   - SerpAPI
    #   - Built-in: from google.adk.tools import google_search
    raise NotImplementedError("Implement web_search")
```

**test_agent.py:**
```python
"""Tests for my-research-agent."""

from agent import researcher, writer, pipeline


def test_researcher_responds():
    """Test that the researcher agent produces output."""
    result = researcher.mock({"researcher": "Mock research findings."}).ask("Test topic")
    assert "Mock research findings" in result


def test_pipeline_end_to_end():
    """Test the full pipeline with mocked responses."""
    result = (
        pipeline
        .mock({
            "researcher": "The findings are X.",
            "writer": "Report: X is important.",
        })
        .ask("Test topic")
    )
    assert "Report" in result


def test_pipeline_validates():
    """Test that the pipeline passes validation."""
    pipeline.validate()  # Raises on error
```

### 2.4 The Template Context Object

Every template receives a structured context:

```python
@dataclass
class ScaffoldContext:
    # Project
    project_name: str           # "my-research-agent"
    project_slug: str           # "my_research_agent"
    python_version: str         # "3.12"

    # Agent
    model: str                  # "gemini-2.5-flash"
    backend: str                # "adk" | "temporal" | "prefect" | "dbos"
    agent_count: int            # Number of agents in scaffold

    # Features
    include_tools: bool
    include_evals: bool
    include_schemas: bool

    # Deployment
    target: str                 # "docker" | "cloudrun" | "k8s" | ...
    port: int                   # 8080

    # Dependencies
    extras: list[str]           # ["temporal", "rich"]
    adk_fluent_version: str     # ">=0.X.0"
    google_adk_version: str     # ">=1.20.0"
```

---

## 3. The Worker Codegen Pipeline

### 3.1 How It Works Today

```
builder.to_ir()
    → IR tree (frozen dataclasses)
        → backend.compile(ir)
            → Runnable (node_plan: list[dict])
                → generate_worker_code(runnable, config)
                    → Python source string
```

This is correct. The worker codegen takes a compiled plan and generates platform-specific Python code.

### 3.2 What We'd Add: CLI Integration

```bash
# Generate Temporal worker from agent definition
adk-fluent codegen worker agent.py --backend temporal --output worker.py

# Generate Prefect flow from agent definition
adk-fluent codegen worker agent.py --backend prefect --output flow.py

# Generate DBOS app from agent definition
adk-fluent codegen worker agent.py --backend dbos --output app.py
```

**Implementation:**
```python
def _cmd_codegen_worker(args):
    # 1. Import the module and find the builder
    module = importlib.import_module(args.module)
    builder = _find_builder(module, args.var)

    # 2. Compile to IR
    ir = builder.to_ir()

    # 3. Get backend and compile
    backend = get_backend(args.backend)
    runnable = backend.compile(ir)

    # 4. Generate code
    if args.backend == "temporal":
        from adk_fluent.backends.temporal_worker import generate_worker_code
        code = generate_worker_code(runnable)
    elif args.backend == "prefect":
        from adk_fluent.backends.prefect_worker import generate_flow_code
        code = generate_flow_code(runnable)
    elif args.backend == "dbos":
        from adk_fluent.backends.dbos_worker import generate_app_code
        code = generate_app_code(runnable)

    # 5. Write output
    Path(args.output).write_text(code)
```

### 3.3 The Codegen Quality Problem

**Current worker codegen generates code that looks generated.** Compare:

```python
# Generated (current temporal_worker.py output)
@activity.defn(name="researcher_step")
async def researcher_step(
    prompt: str,
    state: dict[str, Any],
    *,
    model_provider: Any = None,
) -> dict[str, Any]:
    """Activity for agent "researcher" (model: gemini-2.5-flash)."""
    if model_provider is None:
        raise RuntimeError("No model_provider for activity \"researcher\"")
    from adk_fluent.compute._protocol import GenerateConfig, Message
    messages = []
    instruction = state.get("_instruction_researcher", "")
    ...
```

```python
# What a human would write
@activity.defn
async def research(prompt: str, state: dict) -> dict:
    """Research the topic using the configured LLM."""
    response = await llm.generate(
        system="Research the topic thoroughly.",
        user=prompt,
    )
    state["findings"] = response.text
    return state
```

**Trade-off:** Generated code needs to be generic (handles any IR shape). Human-readable code is specific. We should aim for the middle: generated code that's correct and readable, even if not minimal.

**Improvement:** Add comments explaining what each block does, use descriptive variable names, and format the output with `black` or `ruff format`.

---

## 4. The `package` Command Architecture

### 4.1 The Generation Pipeline

```
adk-fluent package agent.py --target docker
    │
    ├── 1. Import module, find builder
    ├── 2. Introspect builder (model, backend, tools, schemas)
    ├── 3. Resolve template context (ScaffoldContext)
    ├── 4. Load templates from adk_fluent/templates/{target}/
    ├── 5. Render templates with Jinja2
    ├── 6. Write output files
    └── 7. Print summary with next steps
```

### 4.2 Builder Introspection

`adk-fluent package` needs to understand what the builder uses:

```python
def introspect_builder(builder) -> BuilderIntrospection:
    return BuilderIntrospection(
        name=builder._config.get("name", "agent"),
        model=builder._config.get("model", "gemini-2.5-flash"),
        backend=builder._config.get("_engine", "adk"),
        has_tools=bool(builder._lists.get("tools")),
        has_schemas=bool(builder._config.get("output_schema")),
        has_sub_agents=bool(builder._lists.get("sub_agents")),
        tool_names=[t.__name__ for t in builder._lists.get("tools", []) if callable(t)],
        extras_needed=_infer_extras(builder),
    )
```

### 4.3 Dependency Detection

The package command should auto-detect which pip extras are needed:

```python
def _infer_extras(builder) -> list[str]:
    extras = []
    engine = builder._config.get("_engine")
    if engine == "temporal":
        extras.append("temporal")
    elif engine == "prefect":
        extras.append("prefect")
    elif engine == "dbos":
        extras.append("dbos")

    # Detect tool dependencies
    for tool in builder._lists.get("tools", []):
        if hasattr(tool, "__module__"):
            if "google_search" in tool.__module__:
                pass  # Built into google-adk
            if "mcp" in tool.__module__:
                extras.append("mcp")

    return extras
```

---

## 5. Template Maintenance Strategy

### 5.1 The Rot Problem

Templates will break when:
- Cloud Run YAML schema changes
- Kubernetes API versions deprecate (e.g., `apps/v1beta1` → `apps/v1`)
- Temporal docker-compose defaults change
- Prefect deployment manifest format evolves
- Python version support changes

### 5.2 The Mitigation Plan

**1. Version-pin platform targets in templates:**
```yaml
# k8s/deployment.j2
apiVersion: apps/v1  # Stable since K8s 1.9
kind: Deployment
```

**2. Test generated artifacts in CI:**
```yaml
# .github/workflows/template-test.yml
jobs:
  test-docker-template:
    runs-on: ubuntu-latest
    steps:
      - run: adk-fluent package examples/basic.py --target docker --output /tmp/out
      - run: docker build /tmp/out  # Verify Dockerfile builds
      # Don't run the container (needs API keys)

  test-k8s-template:
    runs-on: ubuntu-latest
    steps:
      - run: adk-fluent package examples/basic.py --target k8s --output /tmp/out
      - run: kubectl apply --dry-run=client -f /tmp/out/k8s/  # Validate YAML
```

**3. User-overridable templates:**
```bash
# Use custom Dockerfile template
adk-fluent package agent.py --target docker --template-dir ./my-templates/

# my-templates/docker/Dockerfile.j2 overrides the built-in
```

**4. Minimum support matrix:**

| Template Target | Minimum Tested Version | Notes |
|----------------|----------------------|-------|
| Docker | Docker 24+ | Multi-platform builds |
| Cloud Run | gcloud 450+ | Gen2 execution environment |
| Kubernetes | 1.27+ | apps/v1 stable |
| Temporal | temporalio 1.7+ | Auto-setup docker image |
| Prefect | prefect 3.0+ | V3 deployment format |
| DBOS | dbos 2.0+ | Python SDK |

---

## 6. What We Explicitly Don't Generate

1. **CI/CD pipelines** beyond a basic scaffold template — every team's CI is different
2. **Terraform / Pulumi / CDK** infra-as-code — that's a different tool's job
3. **Monitoring dashboards** — Grafana JSON, Datadog config, etc. Too fragile.
4. **Load test scripts** — users know their traffic patterns better than we do
5. **Production tuning** — memory limits, CPU requests, autoscaling thresholds. We provide sensible defaults with comments explaining how to tune.
