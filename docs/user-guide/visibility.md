# Visibility

In multi-agent pipelines, not every agent's output should be shown to the end-user. A 5-agent pipeline that streams all 5 responses creates a confusing, noisy experience. The visibility system lets you control which agents produce user-facing output and which remain internal.

## The Real Problem

Consider a customer support pipeline:

```
classifier >> router >> specialist >> responder >> auditor
```

Without visibility control, the user sees:
1. "I classified this as a billing issue" (classifier -- internal reasoning)
2. "Routing to billing specialist" (router -- infrastructure noise)
3. "The customer's account shows..." (specialist -- internal analysis)
4. "Dear customer, we've resolved..." (responder -- **this is what the user should see**)
5. "Audit: compliant" (auditor -- internal)

Only response #4 matters. The rest is internal noise that confuses users and leaks implementation details.

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

| Policy | Behavior | Use case |
|---|---|---|
| `filtered` (default) | Terminal agents = user-facing, intermediate = internal | Production: clean user experience |
| `transparent` | All agents user-facing | Debugging: see every agent's output |
| `annotate` | All events pass through with metadata tags | Monitoring: log everything, decide later |

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
# Force an intermediate agent to be user-facing (e.g., progress updates)
agent = Agent("progress").model("m").instruct("Report progress.").show()

# Force a terminal agent to be internal (e.g., cleanup step)
agent = Agent("cleaner").model("m").instruct("Clean up.").hide()
```

Overrides take precedence over both the inferred topology and the pipeline-level policy.

## VisibilityPlugin

`VisibilityPlugin` is an ADK `BasePlugin` that runs on event callbacks. It reads the inferred visibility map and either annotates or filters events:

- **annotate mode** -- all events pass through with `adk_fluent.visibility` and `adk_fluent.is_user_facing` metadata attached
- **filter mode** -- internal events have their content stripped so they never reach the user

Error events always pass through regardless of mode.

```python
from adk_fluent._visibility import infer_visibility, VisibilityPlugin

vis_map = infer_visibility(pipeline.to_ir())
plugin = VisibilityPlugin(vis_map, mode="filter")
```

## Interplay with Other Modules

### Visibility + Transfer Control

Visibility and transfer control work on different axes:

- **Visibility** controls what the *user* sees
- **Transfer control** controls what *agents* can do (`.isolate()`, `.stay()`, `.no_peers()`)

They compose independently:

```python
from adk_fluent import Agent

# This agent is hidden from the user AND can't transfer to other agents
internal_validator = (
    Agent("validator")
    .model("gemini-2.5-flash")
    .instruct("Validate the output.")
    .hide()       # User doesn't see validation reasoning
    .isolate()    # Validator can't hand off to other agents
)
```

See [Transfer Control](transfer-control.md).

### Visibility + Context Engineering

Context engineering controls what the *LLM* sees. Visibility controls what the *user* sees. They're complementary:

```python
from adk_fluent import Agent, C

# Classifier: hidden from user, sees no conversation history
classifier = (
    Agent("classifier")
    .model("gemini-2.5-flash")
    .instruct("Classify the intent.")
    .context(C.none())   # LLM doesn't see history
    .hide()              # User doesn't see classification
)
```

A common pattern: intermediate agents should both `.hide()` (from user) and use `C.none()` or `C.from_state()` (from LLM). This prevents noise in both directions.

See [Context Engineering](context-engineering.md).

### Visibility + Streaming

When using `.stream()`, visibility determines which agents' chunks reach the stream:

- **`filtered`**: only terminal agents' chunks appear
- **`transparent`**: all agents' chunks appear (useful for debugging)
- **`annotate`**: all chunks appear with metadata tags

```python
# Only the final agent's output streams to the user
pipeline = (
    Agent("analyzer").instruct("Analyze.").hide()
    >> Agent("writer").instruct("Write.").show()
)

async for chunk in pipeline.stream("Explain quantum computing"):
    print(chunk, end="")  # Only writer's output
```

See [Execution](execution.md).

### Visibility + Middleware

Middleware sees all agents regardless of visibility. `M.log()` captures events from hidden agents too -- visibility only affects user-facing output:

```python
from adk_fluent._middleware import M

pipeline = (
    Agent("hidden").instruct("Internal.").hide()
    >> Agent("visible").instruct("User-facing.")
).middleware(M.log())
# M.log() captures both hidden and visible agents' events
```

See [Middleware](middleware.md).

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

## Best Practices

1. **Default to `filtered` in production.** Users should only see the final, polished output
2. **Use `transparent` during development.** Seeing every agent's reasoning helps debug pipeline logic
3. **Use `.show()` for progress agents.** If an intermediate agent reports progress ("Searching 3 sources..."), make it user-facing explicitly
4. **Use `.hide()` for cleanup/audit agents.** Terminal agents that perform validation or logging shouldn't be user-facing
5. **Pair `.hide()` with `C.none()` for utility agents.** If an agent is hidden from the user, it probably shouldn't see conversation history either

:::{seealso}
- [Transfer Control](transfer-control.md) -- `.isolate()`, `.stay()`, `.no_peers()` for agent handoff control
- [Context Engineering](context-engineering.md) -- controlling what the LLM sees
- [Execution](execution.md) -- `.stream()` and how visibility affects streaming
- [Middleware](middleware.md) -- middleware sees all agents regardless of visibility
:::
