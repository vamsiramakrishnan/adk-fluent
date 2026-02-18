# Graph Visualization

*How to generate visual diagrams of agent pipelines.*

_Source: n/a (v4 feature)_

::::{tab-set}
:::{tab-item} Native ADK
```python
# Native ADK has no built-in visualization.
# Agent trees must be manually diagrammed.
```
:::
:::{tab-item} adk-fluent
```python
from adk_fluent import Agent

# Any builder can generate a Mermaid diagram
pipeline = Agent("classifier") >> Agent("resolver") >> Agent("responder")
print(pipeline.to_mermaid())
```
:::
::::

## Equivalence

```python
from adk_fluent import Agent

mermaid = (Agent("a") >> Agent("b")).to_mermaid()
assert "graph TD" in mermaid
assert "a" in mermaid
assert "b" in mermaid
assert "-->" in mermaid
```

## Complex Topologies

```python
from adk_fluent import Agent

# Parallel branches
fanout = Agent("a") | Agent("b") | Agent("c")
print(fanout.to_mermaid())

# Loop
loop = Agent("writer") * 3
print(loop.to_mermaid())

# Mixed: sequence with parallel and loop
complex_pipeline = (
    Agent("classifier")
    >> (Agent("web") | Agent("scholar"))
    >> Agent("writer") * 3
)
print(complex_pipeline.to_mermaid())
```

```python
mermaid = complex_pipeline.to_mermaid()
assert "graph" in mermaid
```

## Data-Flow Annotations

When agents have `.produces()` or `.consumes()`, the diagram includes contract annotations:

```python
from pydantic import BaseModel
from adk_fluent import Agent

class Intent(BaseModel):
    category: str

pipeline = Agent("classifier").produces(Intent) >> Agent("resolver").consumes(Intent)
mermaid = pipeline.to_mermaid()
```

```python
assert "Intent" in mermaid
```

:::{seealso}
User guide: [IR and Backends - Visualization](../user-guide/ir-and-backends.md#visualization)
:::
