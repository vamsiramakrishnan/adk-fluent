# Agent Cloning with .clone()

_Source: `10_cloning.py`_

## Native ADK

```python
# Native ADK has no clone mechanism. You must manually copy all parameters:
#   base_args = dict(model="gemini-2.5-flash", instruction="Be helpful.")
#   math_agent = LlmAgent(name="math", **base_args, tools=[calculator])
#   code_agent = LlmAgent(name="code", **base_args, tools=[code_executor])
```

## adk-fluent

```python
from adk_fluent import Agent

base = Agent("base").model("gemini-2.5-flash").instruct("Be helpful.")

math_agent = base.clone("math").instruct("Solve math problems.")
code_agent = base.clone("code").instruct("Write Python code.")
```

## Equivalence

```python
# Clones are independent
assert math_agent._config["name"] == "math"
assert code_agent._config["name"] == "code"
assert math_agent._config["instruction"] == "Solve math problems."
assert code_agent._config["instruction"] == "Write Python code."
# Original is unchanged
assert base._config["name"] == "base"
assert base._config["instruction"] == "Be helpful."
```
