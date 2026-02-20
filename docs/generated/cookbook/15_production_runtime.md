# Deploying a Chatbot to Production

*How to configure agents for production runtime.*

_Source: `15_production_runtime.py`_

::::\{tab-set}
:::\{tab-item} Native ADK

```python
# Native ADK production setup requires assembling multiple objects:
#   from google.adk.agents.llm_agent import LlmAgent
#   from google.adk.runners import Runner
#   from google.adk.sessions.in_memory_session_service import InMemorySessionService
#
#   agent = LlmAgent(
#       name="store_assistant",
#       model="gemini-2.5-flash",
#       instruction="You are a helpful e-commerce assistant. Help customers "
#                   "find products, check order status, and answer FAQs.",
#       description="Production e-commerce chatbot with order tracking and FAQ support.",
#   )
#   session_service = InMemorySessionService()
#   runner = Runner(
#       agent=agent, app_name="ecommerce_app", session_service=session_service
#   )
```

:::
:::\{tab-item} adk-fluent

```python
from adk_fluent import Agent

# The fluent API collapses runtime setup into a single chain.
# .describe() adds metadata visible to monitoring and admin dashboards.
agent = (
    Agent("store_assistant")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a helpful e-commerce assistant. Help customers find products, check order status, and answer FAQs."
    )
    .describe("Production e-commerce chatbot with order tracking and FAQ support.")
)
```

:::
::::

## Equivalence

```python
assert agent._config["name"] == "store_assistant"
assert agent._config["model"] == "gemini-2.5-flash"
assert "e-commerce assistant" in agent._config["instruction"]
assert "Production e-commerce chatbot" in agent._config["description"]
```

:::\{seealso}
API reference: [Runner](../api/runtime.md#builder-Runner)
:::
