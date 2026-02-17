# Delegate Pattern: LLM-Driven Routing

*How to delegate tasks between agents.*

_Source: `27_delegate_pattern.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.agent_tool import AgentTool

specialist = LlmAgent(
    name="math_expert",
    model="gemini-2.5-flash",
    instruction="You solve math problems step by step.",
)

# Native: manually create AgentTool and add to tools list
coordinator_native = LlmAgent(
    name="coordinator",
    model="gemini-2.5-flash",
    instruction="Route tasks to the right specialist.",
    tools=[AgentTool(agent=specialist)],
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

math = Agent("math_expert").model("gemini-2.5-flash").instruct("You solve math problems step by step.")
code = Agent("code_expert").model("gemini-2.5-flash").instruct("You write Python code.")

# .delegate() wraps each agent as AgentTool — the coordinator's LLM
# decides when to delegate (LLM-driven routing, unlike Route which is deterministic)
coordinator_fluent = (
    Agent("coordinator")
    .model("gemini-2.5-flash")
    .instruct("Route tasks to the right specialist.")
    .delegate(math)
    .delegate(code)
)
```
:::
::::

## Equivalence

```python
# delegate adds to tools list
assert len(coordinator_fluent._lists["tools"]) == 2

# Each tool is an AgentTool wrapping the built specialist
built = coordinator_fluent.build()
assert len(built.tools) == 2
assert all(isinstance(t, AgentTool) for t in built.tools)
```
