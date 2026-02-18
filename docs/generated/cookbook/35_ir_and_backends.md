# IR and Backends

*How to use the intermediate representation for inspection and compilation.*

_Source: n/a (v4 feature)_

::::{tab-set}
:::{tab-item} Native ADK
```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.apps.app import App

a = LlmAgent(name="a", model="gemini-2.5-flash", instruction="Step 1.")
b = LlmAgent(name="b", model="gemini-2.5-flash", instruction="Step 2.")
seq = SequentialAgent(name="pipeline", sub_agents=[a, b])
app = App(name="my_app", root_agent=seq)
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent, ExecutionConfig

pipeline = Agent("a").instruct("Step 1.") >> Agent("b").instruct("Step 2.")

# Inspect the IR tree (frozen dataclasses)
ir = pipeline.to_ir()

# Compile to native ADK App
app = pipeline.to_app(config=ExecutionConfig(app_name="my_app"))
```
:::
::::

## Equivalence

```python
from adk_fluent._ir_generated import SequenceNode, AgentNode

assert isinstance(ir, SequenceNode)
assert len(ir.children) == 2
assert isinstance(ir.children[0], AgentNode)
assert ir.children[0].name == "a"
assert ir.children[1].name == "b"
assert app.name == "my_app"
```

## IR Node Inspection

```python
from adk_fluent import Agent

# Every builder type has a corresponding IR node
agent_ir = Agent("helper").model("gemini-2.5-flash").to_ir()
assert agent_ir.name == "helper"
assert agent_ir.model == "gemini-2.5-flash"

# Nested builders produce nested IR trees
deep = Agent("a") >> (Agent("b") | Agent("c")) >> Agent("d") * 3
deep_ir = deep.to_ir()
assert len(deep_ir.children) >= 3
```

:::{seealso}
User guide: [IR and Backends](../user-guide/ir-and-backends.md)
:::
