# Domain Expert Agent via @agent Decorator

:::{admonition} Why this matters
:class: important
When an agent's tools and configuration are defined in the same file, the `@agent` decorator provides the most concise syntax -- the agent is defined as a decorated function that returns its instruction. This is ideal for domain-expert agents where tools, instructions, and configuration form a cohesive unit.
:::

:::{warning} Without this
Without the decorator pattern, agent definitions require explicit builder chains or constructor calls. For simple agents with co-located tools, this adds ceremony. The `@agent` decorator reduces a 5-line builder chain to a 3-line decorated function, keeping the agent's purpose front and center.
:::

:::{tip} What you'll learn
How to use the @agent decorator for concise agent definitions.
:::

_Source: `24_agent_decorator.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent.decorators import agent


@agent("pharma_advisor", model="gemini-2.5-flash")
def pharma_advisor():
    """You are a pharmaceutical advisor. Help healthcare professionals check drug interactions and dosage guidelines."""
    pass


@pharma_advisor.tool
def lookup_drug_interaction(drug_a: str, drug_b: str) -> str:
    """Check for known interactions between two drugs."""
    return f"Checking interaction between {drug_a} and {drug_b}"


@pharma_advisor.on("before_model")
def log_query(callback_context, llm_request):
    """Log every query for regulatory compliance."""
    pass


# The decorator returns a builder, not a built agent.
# Build when ready to deploy:
built = pharma_advisor.build()
```
:::
:::{tab-item} Native ADK
```python
# Native ADK:
#   from google.adk.agents.llm_agent import LlmAgent
#
#   def lookup_drug_interaction(drug_a: str, drug_b: str) -> str:
#       return f"Checking interaction between {drug_a} and {drug_b}"
#
#   agent = LlmAgent(
#       name="pharma_advisor",
#       model="gemini-2.5-flash",
#       instruction="You are a pharmaceutical advisor. Help healthcare professionals "
#                   "check drug interactions and dosage guidelines.",
#       tools=[lookup_drug_interaction],
#   )
```
:::
::::

## Equivalence

```python
from adk_fluent.agent import Agent as AgentBuilder

# Decorator produces a builder
assert isinstance(pharma_advisor, AgentBuilder)

# Docstring becomes instruction
assert "pharmaceutical advisor" in pharma_advisor._config["instruction"]

# Tools are registered
assert len(pharma_advisor._lists["tools"]) == 1

# Callbacks are registered via .on()
assert len(pharma_advisor._callbacks["before_model_callback"]) == 1

# Builds to a real ADK agent
from google.adk.agents.llm_agent import LlmAgent

assert isinstance(built, LlmAgent)
assert built.name == "pharma_advisor"
```

:::{seealso}
API reference: [Agent](../api/agent.md#builder-Agent)
:::
