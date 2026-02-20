# Visibility

In multi-agent pipelines, not every agent's output should be shown to the end-user. The visibility system lets you control which agents produce user-facing output and which remain internal.

## The Problem

When a 5-agent pipeline runs, the end-user sees all 5 responses by default. Only the final agent's output typically matters. Intermediate agents produce internal reasoning noise that clutters the user experience.

## Topology-Inferred Visibility

`infer_visibility` walks the pipeline IR and classifies each agent automatically. Terminal agents (those with no successor) are marked `"user"`, intermediate agents are marked `"internal"`:

```python
from adk_fluent import Agent
from adk_fluent._visibility import infer_visibility

pipeline = (
    Agent("classifier").model("m").instruct("Classify.")
    >> Agent("handler").model("m").instruct("Handle.")
)
vis = infer_visibility(pipeline.to_ir())
# {"classifier": "internal", "handler": "user"}
```

## Policies Reference

| Policy               | Behavior                                               |
| -------------------- | ------------------------------------------------------ |
| `filtered` (default) | Terminal agents = user-facing, intermediate = internal |
| `transparent`        | All agents user-facing (useful for debugging)          |
| `annotate`           | All events pass through with metadata tags             |

## Pipeline-Level Policies

Set a policy on the entire pipeline with a single method call:

```python
pipeline = (
    Agent("a").model("m").instruct("Step 1.")
    >> Agent("b").model("m").instruct("Step 2.")
)
pipeline.transparent()  # Debug: see everything
pipeline.filtered()     # Production: only terminal output
pipeline.annotated()    # Monitoring: tag events with visibility metadata
```

## Per-Agent Overrides

Override the topology-inferred classification on individual agents:

```python
# Force an intermediate agent to be user-facing
agent = Agent("logger").model("m").instruct("Log progress.").show()

# Force a terminal agent to be internal
agent = Agent("cleaner").model("m").instruct("Clean up.").hide()
```

Overrides take precedence over both the inferred topology and the pipeline-level policy.

## VisibilityPlugin

`VisibilityPlugin` is an ADK `BasePlugin` that runs on event callbacks. It reads the inferred visibility map and either annotates or filters events:

- **annotate mode** -- all events pass through with `adk_fluent.visibility` and `adk_fluent.is_user_facing` metadata attached.
- **filter mode** -- internal events have their content stripped so they never reach the user.

Error events always pass through regardless of mode.

```python
from adk_fluent._visibility import infer_visibility, VisibilityPlugin

vis_map = infer_visibility(pipeline.to_ir())
plugin = VisibilityPlugin(vis_map, mode="filter")
```

## Complete Example

A 3-agent draft-review-edit pipeline where only the editor's output is shown to the user:

```python
from adk_fluent import Agent
from adk_fluent._visibility import infer_visibility

pipeline = (
    Agent("drafter")
        .model("gemini-2.5-flash")
        .instruct("Write a first draft.")
    >> Agent("reviewer")
        .model("gemini-2.5-flash")
        .instruct("Review the draft and suggest improvements.")
    >> Agent("editor")
        .model("gemini-2.5-flash")
        .instruct("Apply the review feedback and produce the final text.")
)

vis = infer_visibility(pipeline.to_ir())
# {"drafter": "internal", "reviewer": "internal", "editor": "user"}

# Production mode -- only the editor's output reaches the user
pipeline.filtered()

# Debug mode -- see all three agents' output
# pipeline.transparent()
```
