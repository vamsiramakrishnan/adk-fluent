# A/B Testing Agent Variants -- Agent Cloning with .clone()

Demonstrates .clone() for creating independent agent variants from
a shared base configuration.  The scenario: A/B testing two customer
support agents -- one using a formal tone and one using a casual tone
-- while sharing the same underlying tool (order lookup).

:::{admonition} Why this matters
:class: important
A/B testing requires creating agent variants that differ in one dimension (prompt, model, temperature) while sharing everything else (tools, callbacks, middleware). Manual duplication is error-prone: change the base agent and forget to update one variant. `.clone()` creates independent copies from a shared base, so changes to the base automatically propagate to all variants. This pattern is essential for systematic prompt engineering and model evaluation.
:::

:::{warning} Without this
Without safe cloning, A/B testing requires manually duplicating constructor calls with copy-paste. Change the shared tool list in one variant but forget the other, and your experiment results are meaningless. The `.clone()` method guarantees independent copies that share the same base configuration, making experiments reproducible and maintainable.
:::

:::{tip} What you'll learn
How to create independent agent variants with .clone() for A/B testing.
:::

_Source: `10_cloning.py`_

::::{tab-set}
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent


def lookup_order(order_id: str) -> str:
    """Look up the status of a customer order by its ID."""
    return f"Order {order_id}: shipped, arriving Thursday"


base = (
    Agent("support_base")
    .model("gemini-2.5-flash")
    .instruct("You are a customer support agent. Help customers with order inquiries.")
    .tool(lookup_order)
)

variant_a = base.clone("formal_support").instruct(
    "You are a customer support agent. Use formal, professional language. "
    "Address the customer as Sir or Madam. Be thorough and precise."
)
variant_b = base.clone("casual_support").instruct(
    "You are a customer support agent. Use friendly, casual language. "
    "Be warm and personable. Use the customer's first name."
)
```
:::
:::{tab-item} Native ADK
```python
# Native ADK has no clone mechanism. You must manually duplicate all parameters:
#   from google.adk.agents.llm_agent import LlmAgent
#
#   def lookup_order(order_id: str) -> str:
#       return f"Order {order_id}: shipped, arriving Thursday"
#
#   formal = LlmAgent(
#       name="formal",
#       model="gemini-2.5-flash",
#       instruction="Use formal, professional language when helping customers.",
#       tools=[lookup_order],
#   )
#   casual = LlmAgent(
#       name="casual",
#       model="gemini-2.5-flash",
#       instruction="Use friendly, casual language when helping customers.",
#       tools=[lookup_order],
#   )
```
:::
::::

## Equivalence

```python
# Clones are independent with their own names
assert variant_a._config["name"] == "formal_support"
assert variant_b._config["name"] == "casual_support"
# Each clone has its own instruction
assert "formal" in variant_a._config["instruction"]
assert "casual" in variant_b._config["instruction"]
# Original base is unchanged
assert base._config["name"] == "support_base"
assert "order inquiries" in base._config["instruction"]
# Both clones inherited the tool
assert len(variant_a._lists["tools"]) == 1
assert len(variant_b._lists["tools"]) == 1
```
