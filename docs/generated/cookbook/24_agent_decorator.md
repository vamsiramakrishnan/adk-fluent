# Domain Expert Agent via @agent Decorator

*How to use the agent decorator pattern.*

_Source: `24_agent_decorator.py`_

::::\{tab-set}
:::\{tab-item} Native ADK

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
:::\{tab-item} adk-fluent

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

:::\{seealso}
API reference: [Agent](../api/agent.md#builder-Agent)
:::
