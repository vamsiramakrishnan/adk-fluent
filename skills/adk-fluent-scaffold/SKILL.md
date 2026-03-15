---
name: adk-fluent-scaffold
description: >
  Use when creating a new adk-fluent agent project from scratch.
  Project scaffolding — directory structure, agent.py setup, tool definition,
  testing setup, and integration with ADK CLI. Covers both minimal and
  production-ready project layouts.
metadata:
  license: Apache-2.0
  author: vamsiramakrishnan
  version: "0.12.1"
---

# Scaffold an adk-fluent Project

> **Two paths:** Minimal (pure adk-fluent) or Full (Agent Starter Pack + adk-fluent).
> Choose minimal for quick prototypes, full for production deployment.

---

## Step 1: Gather Requirements

Before scaffolding, understand:
1. **What problem** does the agent solve?
2. **What tools** does it need? (search, APIs, databases)
3. **Single agent or multi-agent?** (pipeline, fanout, routing)
4. **Deployment target?** (local only, Agent Engine, Cloud Run)
5. **Any constraints?** (latency, cost, safety, PII)

---

## Step 2: Choose Project Type

### Option A: Minimal adk-fluent Project

Best for: prototypes, single agents, learning.

```bash
mkdir my_agent && cd my_agent
uv init
uv add adk-fluent google-adk
```

Create the directory structure:

```
my_agent/
├── pyproject.toml
├── app/
│   ├── __init__.py
│   ├── agent.py          # root_agent definition
│   └── tools.py          # Tool functions
├── tests/
│   └── test_agent.py     # Tests with .mock()
└── eval/
    ├── evalset.json      # Eval cases
    └── eval_config.json  # Eval criteria
```

### Option B: Full Project (Agent Starter Pack)

Best for: production deployment with CI/CD, infrastructure, observability.

```bash
# Install Agent Starter Pack
pip install agent-starter-pack

# Create project (interactive)
agent-starter-pack create my-agent

# Or with options
agent-starter-pack create my-agent --deployment=cloud_run --prototype
```

Then add adk-fluent:

```bash
cd my-agent
uv add adk-fluent
```

Replace the native ADK agent definition with fluent builders.

---

## Step 3: Create agent.py

### Single agent

```python
"""Main agent definition."""
from adk_fluent import Agent, P, G

def search(query: str) -> str:
    """Search for information on a topic."""
    return f"Results for: {query}"

root_agent = (
    Agent("assistant", "gemini-2.5-flash")
    .instruct(
        P.role("Helpful research assistant")
        + P.task("Answer questions using available tools")
        + P.constraint("Always cite sources", "Be concise")
    )
    .tool(search)
    .guard(G.length(max=2000))
    .build()
)
```

### Pipeline

```python
"""Multi-step research pipeline."""
from adk_fluent import Agent, Pipeline, P, S

root_agent = (
    Pipeline("research_pipeline")
    .step(
        Agent("researcher", "gemini-2.5-flash")
        .instruct("Research the given topic thoroughly.")
        .tool(search)
        .writes("findings")
    )
    .step(
        Agent("writer", "gemini-2.5-flash")
        .instruct(
            P.task("Write a summary based on {findings}")
            + P.constraint("Be concise", "Use bullet points")
        )
        .reads("findings")
    )
    .build()
)
```

### Multi-agent with routing

```python
"""Customer support with routing."""
from adk_fluent import Agent, Route, P

billing_agent = (
    Agent("billing", "gemini-2.5-flash")
    .instruct("Handle billing inquiries.")
    .isolate()
)

tech_agent = (
    Agent("tech", "gemini-2.5-flash")
    .instruct("Handle technical issues.")
    .isolate()
)

general_agent = (
    Agent("general", "gemini-2.5-flash")
    .instruct("Handle general inquiries.")
    .isolate()
)

classifier = (
    Agent("classifier", "gemini-2.5-flash")
    .instruct("Classify the customer issue as: billing, technical, or general.")
    .writes("category")
)

root_agent = (
    classifier
    >> Route("category")
        .eq("billing", billing_agent)
        .eq("technical", tech_agent)
        .otherwise(general_agent)
).build()
```

---

## Step 4: Create tools.py

```python
"""Agent tools."""


def search(query: str) -> str:
    """Search the web for information.

    Args:
        query: The search query.

    Returns:
        Search results as text.
    """
    # Replace with real implementation
    return f"Results for: {query}"


def fetch_data(url: str) -> str:
    """Fetch data from a URL.

    Args:
        url: The URL to fetch.

    Returns:
        The page content.
    """
    import urllib.request
    with urllib.request.urlopen(url) as response:
        return response.read().decode()[:5000]
```

**Tool rules:**
- Docstrings become the tool description for the LLM — write them clearly
- Type annotations on parameters are required
- Use `.inject()` for infrastructure deps (DB clients, API keys)

---

## Step 5: Create tests

```python
"""Agent tests."""
import pytest
from adk_fluent import Agent, check_contracts


class TestAgent:
    def test_basic_response(self):
        from app.agent import root_agent  # or rebuild with mock
        agent = (
            Agent("test", "gemini-2.5-flash")
            .instruct("Answer questions.")
            .mock(["The answer is 42."])
        )
        result = agent.ask("What is the answer?")
        assert "42" in result

    def test_pipeline_contracts(self):
        a = Agent("a").writes("x")
        b = Agent("b").reads("x")
        pipeline = a >> b
        assert not check_contracts(pipeline)

    def test_agent_validates(self):
        from app.agent import root_agent
        # root_agent is already built, so test the builder instead
        agent = Agent("test", "gemini-2.5-flash").instruct("Hello.")
        assert not agent.validate()
```

```bash
uv run pytest tests/ -v --tb=short
```

---

## Step 6: Create eval cases

### eval/evalset.json

```json
{
  "eval_set_id": "basic_eval",
  "eval_cases": [
    {
      "eval_id": "basic_search",
      "conversation": [
        {
          "invocation_id": "inv_1",
          "user_content": { "parts": [{ "text": "Search for Python tutorials" }] },
          "final_response": {
            "role": "model",
            "parts": [{ "text": "Here are Python tutorials..." }]
          },
          "intermediate_data": {
            "tool_uses": [
              { "name": "search", "args": { "query": "Python tutorials" } }
            ]
          }
        }
      ],
      "session_input": { "app_name": "app", "user_id": "test", "state": {} }
    }
  ]
}
```

### eval/eval_config.json

```json
{
  "criteria": {
    "tool_trajectory_avg_score": {
      "threshold": 1.0,
      "match_type": "IN_ORDER"
    },
    "final_response_match_v2": {
      "threshold": 0.5
    }
  }
}
```

```bash
adk eval app/ eval/evalset.json --config_file_path=eval/eval_config.json --print_detailed_results
```

---

## Step 7: Verify

```bash
# Test
uv run pytest tests/ -v --tb=short

# Interactive playground
adk web app/

# Evaluate
adk eval app/ eval/evalset.json --config_file_path=eval/eval_config.json
```

---

## Project Templates

### Minimal chatbot

```python
from adk_fluent import Agent

root_agent = Agent("chatbot", "gemini-2.5-flash").instruct("You are a friendly chatbot.").build()
```

### RAG agent

```python
from adk_fluent import Agent, P, C

root_agent = (
    Agent("rag", "gemini-2.5-flash")
    .instruct(
        P.role("Knowledge assistant")
        + P.task("Answer questions using the retrieval tool")
        + P.constraint("Only answer based on retrieved content", "Say 'I don't know' if unsure")
    )
    .tool(retrieve_documents)
    .context(C.window(n=3))
    .build()
)
```

### Multi-model fallback

```python
from adk_fluent import Agent

root_agent = (
    Agent("fast", "gemini-2.5-flash").instruct("Answer concisely.")
    // Agent("strong", "gemini-2.5-pro").instruct("Answer thoroughly.")
).build()
```

### Supervised pipeline

```python
from adk_fluent.patterns import review_loop
from adk_fluent import Agent

root_agent = review_loop(
    Agent("writer", "gemini-2.5-flash").instruct("Write a draft."),
    Agent("reviewer", "gemini-2.5-flash").instruct("Review and approve or request changes."),
    quality_key="review", target="APPROVED", max_rounds=3,
).build()
```

---

## Next Steps

After scaffolding:
1. Load `/dev-guide` for development workflow
2. Load `/cheatsheet` for API reference while coding
3. Load `/eval-agent` before running evaluations
4. Load `/deploy-agent` before deploying
