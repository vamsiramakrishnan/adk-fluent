# Graph Visualization

*How to use graph visualization with the fluent API.*

_Source: `48_visualization.py`_

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
mermaid = pipeline.to_mermaid()

# Build the pipeline for adk web
agent_fluent = pipeline.build()
```
:::
::::

## Equivalence

```python
assert "graph TD" in mermaid
assert "classifier" in mermaid
assert "resolver" in mermaid
assert "responder" in mermaid
assert "-->" in mermaid

# Parallel branches also produce valid Mermaid
fanout = Agent("a") | Agent("b") | Agent("c")
fanout_mermaid = fanout.to_mermaid()
assert "graph TD" in fanout_mermaid
```
