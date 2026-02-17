# Dynamic Field Forwarding via __getattr__

*How to use dynamic field forwarding.*

_Source: `14_dynamic_forwarding.py`_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent

agent_native = LlmAgent(
    name="dynamic",
    model="gemini-2.5-flash",
    instruction="test",
    output_key="result",
    include_contents="none",
)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# Fields not explicitly aliased still work via __getattr__:
agent_fluent = (
    Agent("dynamic")
    .model("gemini-2.5-flash")
    .instruct("test")
    .output_key("result")
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

# Typos are caught:
try:
    Agent("test").instuction("oops")  # typo!
    assert False, "Should have raised AttributeError"
except AttributeError:
    pass  # Expected
```
