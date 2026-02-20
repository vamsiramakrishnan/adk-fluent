# Email Classifier Agent -- Simple Agent Creation

Demonstrates creating a minimal LLM agent using both native ADK and
the fluent builder.  The scenario: an agent that classifies incoming
customer emails into categories (billing, technical, general).

*How to create a basic agent with the fluent API.*

_Source: `01_simple_agent.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent

agent_native = LlmAgent(
    name="email_classifier",
    model="gemini-2.5-flash",
    instruction=(
        "You are an email classifier for a SaaS company. "
        "Read the incoming email and classify it as one of: "
        "billing, technical, or general."
    ),
    description="Classifies customer emails by intent",
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

agent_fluent = (
    Agent("email_classifier")
    .model("gemini-2.5-flash")
    .instruct(
        "You are an email classifier for a SaaS company. "
        "Read the incoming email and classify it as one of: "
        "billing, technical, or general."
    )
    .describe("Classifies customer emails by intent")
    .build()
)
```
:::
::::

## Equivalence

```python
assert type(agent_native) == type(agent_fluent)
assert agent_native.name == agent_fluent.name
assert agent_native.model == agent_fluent.model
assert agent_native.instruction == agent_fluent.instruction
assert agent_native.description == agent_fluent.description
```

:::{seealso}
API reference: [Agent](../api/agent.md#builder-Agent)
:::
