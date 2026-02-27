# Multi-Department Ticket Routing via Dynamic Field Forwarding

*How to use dynamic field forwarding.*

_Source: `14_dynamic_forwarding.py`_

::::\{tab-set}
:::\{tab-item} Native ADK

```python
from google.adk.agents.llm_agent import LlmAgent

# A helpdesk ticket router that classifies and routes support tickets.
# The agent uses output_key to store the classification and include_contents
# to avoid forwarding raw ticket text to downstream agents.
agent_native = LlmAgent(
    name="ticket_router",
    model="gemini-2.5-flash",
    instruction="Classify incoming support tickets by department.",
    output_key="department",
    include_contents="none",
)
```

:::
:::\{tab-item} adk-fluent

```python
from adk_fluent import Agent

# Fields not explicitly aliased (like output_key, include_contents) still
# work via __getattr__ dynamic forwarding. The builder validates field names
# against the ADK LlmAgent class, catching typos at build time.
agent_fluent = (
    Agent("ticket_router")
    .model("gemini-2.5-flash")
    .instruct("Classify incoming support tickets by department.")
    .output_key("department")
    .include_contents("none")
    .build()
)
```

:::
::::

## Equivalence

```python
assert agent_native.output_key == agent_fluent.output_key
assert agent_native.include_contents == agent_fluent.include_contents
assert agent_fluent.name == "ticket_router"

# Typos are caught immediately -- no silent misconfiguration:
try:
    Agent("test").instuction("oops")  # typo: "instuction" instead of "instruct"
    assert False, "Should have raised AttributeError"
except AttributeError:
    pass  # Expected -- the builder validates field names
```
