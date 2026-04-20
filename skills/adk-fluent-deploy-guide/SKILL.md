---
name: adk-fluent-deploy-guide
description: >
  MUST READ before deploying any adk-fluent agent.
  Deployment guide — Agent Engine, Cloud Run, adk web, adk run, adk deploy,
  production configuration, and environment setup.
  adk-fluent agents are native ADK objects, so all ADK deployment methods work.
metadata:
  license: Apache-2.0
  author: vamsiramakrishnan
  version: "0.13.5"
---

# adk-fluent Deployment Guide

> **adk-fluent `.build()` returns real ADK objects.** Every ADK deployment
> method works unchanged — `adk web`, `adk run`, `adk deploy`.

## Key Principle

adk-fluent is a build-time convenience. At deployment time, you have a standard
ADK agent. All ADK deployment docs, tools, and infrastructure apply directly.

---

## Local Development

### adk web (interactive playground)

```python
# app/agent.py
from adk_fluent import Agent

root_agent = (
    Agent("assistant", "gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .tool(search_fn)
    .build()
)
```

```bash
adk web app/
```

The agent directory must contain an `agent.py` with a `root_agent` variable.

### adk run (CLI testing)

```bash
adk run app/
```

### Quick test without ADK CLI

```python
# Sync (blocking)
result = agent.ask("What is 2+2?")

# Async
result = await agent.ask_async("What is 2+2?")

# Streaming
async for chunk in agent.stream("Tell me a story"):
    print(chunk, end="")
```

---

## Deployment Targets

| Target | Auto-scaling | Session state | Complexity | Best for |
|--------|-------------|---------------|------------|----------|
| **Agent Engine** | Managed | Native | Low | Production, managed infra |
| **Cloud Run** | Configurable | External | Medium | Event-driven, containers |
| **GKE** | Full K8s | External | High | GPU, full control |

### Agent Engine (recommended)

```bash
adk deploy agent_engine --project=PROJECT --region=REGION app/
```

Agent Engine manages sessions automatically. Remove manual `session_type`
settings when deploying to Agent Engine.

### Cloud Run

```bash
adk deploy cloud_run --project=PROJECT --region=REGION app/
```

Default: `--no-allow-unauthenticated` (requires auth headers).

### Scaffolded projects (Agent Starter Pack)

If using `agent-starter-pack`, deployment is automated:

```bash
make deploy
```

See `/scaffold-project` for project creation.

---

## Production Configuration

### Environment variables

```bash
export GOOGLE_CLOUD_PROJECT=my-project
export GOOGLE_CLOUD_LOCATION=us-central1  # or global
export GOOGLE_API_KEY=...                  # for API key auth
# OR
export GOOGLE_APPLICATION_CREDENTIALS=...  # for service account
```

### Model-level config

```python
from google.genai.types import GenerateContentConfig

agent = (
    Agent("prod", "gemini-2.5-flash")
    .instruct("Production agent.")
    .generate_content_config(GenerateContentConfig(
        temperature=0.1,
        top_p=0.9,
        max_output_tokens=2048,
    ))
)
```

### Production middleware

```python
agent = (
    Agent("prod", "gemini-2.5-flash")
    .instruct("Production agent.")
    .middleware(
        M.retry(max_attempts=3)          # Retry on failures
        | M.timeout(seconds=30)          # Per-agent timeout
        | M.circuit_breaker(threshold=5)  # Circuit breaker
        | M.log()                        # Structured logging
        | M.cost()                       # Token tracking
        | M.latency()                    # Latency tracking
    )
    .guard(G.pii() | G.length(max=5000))  # Output safety
    .timeout(60)                          # Overall timeout
)
```

### Production guards

```python
from adk_fluent import G

agent.guard(
    G.pii(action="redact")                # Redact PII in output
    | G.toxicity(threshold=0.8)           # Block toxic content
    | G.length(max=5000)                  # Enforce length
    | G.topic(deny=["violence"])          # Topic blocking
)
```

---

## Agent Directory Structure

```
my_agent/
├── agent.py          # root_agent = Agent(...).build()
├── tools.py          # Tool functions
├── prompts.py        # Prompt compositions (P.role() | ...)
├── schemas.py        # Pydantic models for .returns()/.accepts()
├── requirements.txt  # Dependencies (include adk-fluent)
└── tests/
    ├── test_agent.py     # Unit tests with .mock()
    └── eval/
        ├── evalset.json      # Eval cases
        └── eval_config.json  # Eval criteria
```

### agent.py pattern

```python
"""Main agent definition."""
from adk_fluent import Agent, Pipeline, S, C, P, M, G
from .tools import search, fetch_data
from .schemas import OutputSchema

root_agent = (
    Agent("assistant", "gemini-2.5-flash")
    .instruct(
        P.role("Helpful assistant")
        | P.task("Answer questions using available tools")
        | P.constraint("Always cite sources")
    )
    .tool(search)
    .tool(fetch_data)
    .returns(OutputSchema)
    .middleware(M.retry() | M.log())
    .guard(G.pii() | G.length(max=2000))
    .build()
)
```

---

## Secrets Management

**Never** put API keys or secrets in code:

```python
# WRONG
agent.inject(api_key="sk-123...")

# CORRECT — use environment variables
import os
agent.inject(api_key=os.environ["API_KEY"])

# CORRECT — use GCP Secret Manager (production)
from google.cloud import secretmanager
client = secretmanager.SecretManagerServiceClient()
secret = client.access_secret_version(name="projects/P/secrets/S/versions/latest")
agent.inject(api_key=secret.payload.data.decode())
```

---

## Deployment Checklist

1. **Tests pass**: `uv run pytest tests/ -v --tb=short`
2. **Evaluation passes**: `adk eval` or `E.suite(agent).run()`
3. **No secrets in code**: API keys in env vars or Secret Manager
4. **Guards configured**: PII, toxicity, length limits
5. **Middleware configured**: Retry, timeout, circuit breaker, logging
6. **Model pinned**: Explicit model version, not "latest"
7. **requirements.txt updated**: Includes `adk-fluent` and `google-adk`
8. **Agent directory structure correct**: `agent.py` with `root_agent`
9. **Human approval obtained**: Never deploy without explicit approval

---

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Model 404 | Wrong `GOOGLE_CLOUD_LOCATION` | Try `global` or model-specific location |
| "Session not found" | App name mismatch | Ensure `App(name=)` matches directory name |
| Import error on deploy | Missing dependency | Add `adk-fluent` to `requirements.txt` |
| Agent timeout | No timeout configured | Add `.timeout(60)` and `M.timeout(30)` |
| Auth failure on Cloud Run | Missing auth header | Pass identity token in request |

---

## Critical Rules

- **Never deploy without explicit human approval** after evaluation passes
- **Never change the model** as a "fix" for deployment errors — fix the location
- **Always use `uv run`** for Python commands
- **Always run evaluation** before deployment (not just tests)
