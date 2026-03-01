# Senior Architect Delegates to Junior Specialists (LLM-Driven Routing)

*How to delegate tasks between agents.*

_Source: `27_agent_tool_pattern.py`_

### Architecture

```mermaid
graph TD
    c["senior_architect"]
    d0["database_specialist"]
    c -.->|delegates| d0
    d1["frontend_specialist"]
    c -.->|delegates| d1
```

::::\{tab-set}
:::\{tab-item} Native ADK

```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.agent_tool import AgentTool

# Native: manually create an AgentTool for each specialist
database_specialist = LlmAgent(
    name="database_specialist",
    model="gemini-2.5-flash",
    instruction=(
        "You are a database architecture specialist. Design schemas, "
        "optimize queries, and recommend indexing strategies."
    ),
)

coordinator_native = LlmAgent(
    name="tech_lead",
    model="gemini-2.5-flash",
    instruction=(
        "You are a senior tech lead. Analyze architecture requests and agent_tool to the appropriate specialist."
    ),
    tools=[AgentTool(agent=database_specialist)],
)
```

:::
:::\{tab-item} adk-fluent

```python
from adk_fluent import Agent

# Junior specialists — each focused on a specific domain
db_expert = (
    Agent("database_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a database architecture specialist. Design schemas, "
        "optimize queries, and recommend indexing strategies."
    )
)

frontend_expert = (
    Agent("frontend_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a frontend architecture specialist. Design component "
        "hierarchies, state management patterns, and performance optimizations."
    )
)

# .agent_tool() wraps each agent as AgentTool — the senior architect's LLM
# decides when to agent_tool (LLM-driven routing, unlike Route which is deterministic)
senior_architect = (
    Agent("senior_architect")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a senior software architect. Analyze incoming architecture "
        "requests and agent_tool to the appropriate specialist based on the "
        "technical domain involved."
    )
    .agent_tool(db_expert)
    .agent_tool(frontend_expert)
)
```

:::
::::

## Equivalence

```python
# agent_tool adds to tools list
assert len(senior_architect._lists["tools"]) == 2

# Each tool is an AgentTool wrapping the built specialist
built = senior_architect.build()
assert len(built.tools) == 2
assert all(isinstance(t, AgentTool) for t in built.tools)

# --- T Module equivalent ---
# T.agent() wraps agents as AgentTool, composable with | operator
from adk_fluent._tools import T

coordinator_t = (
    Agent("senior_architect_t")
    .model("gemini-2.5-flash")
    .instruct("Coordinate the team.")
    .tools(T.agent(db_expert) | T.agent(frontend_expert))
)
ir_t = coordinator_t.to_ir()
assert len(ir_t.tools) == 2
assert all(isinstance(t, AgentTool) for t in ir_t.tools)
```

:::\{seealso}
API reference: [FunctionTool](../api/tool.md#builder-FunctionTool)
:::
