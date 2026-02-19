# Module: visibility

> `from adk_fluent._visibility import infer_visibility, VisibilityPlugin`

Event visibility controls which agent outputs are shown to end users in multi-agent pipelines.

## `infer_visibility(node, has_successor=False, policy="filtered") -> dict[str, str]`

Walk an IR tree and classify each agent's visibility.

**Parameters:**
- `node` — IR node (from `pipeline.to_ir()`)
- `has_successor` — Whether this node has a successor in the pipeline (default: False)
- `policy` — Visibility policy: `"filtered"`, `"transparent"`, or `"annotate"` (default: "filtered")

**Returns:** Dictionary mapping agent names to visibility classifications: `"user"`, `"internal"`, or `"zero_cost"`.

**Example:**
```python
ir = pipeline.to_ir()
vis = infer_visibility(ir)
# {"classifier": "internal", "handler": "user"}
```

## `VisibilityPlugin`

ADK `BasePlugin` that filters or annotates agent events based on visibility classification.

### Constructor

```python
VisibilityPlugin(visibility_map, mode="filter")
```

**Parameters:**
- `visibility_map` — Dict from `infer_visibility()`
- `mode` — `"filter"` (strip content from internal events) or `"annotate"` (add metadata tags)

### Behavior

- Runs on `on_event_callback` after each event is appended
- In `filter` mode: strips `content.parts` from internal agent events
- In `annotate` mode: adds `_visibility` key to event metadata
- Error events always pass through regardless of visibility

## Pipeline Policies

Builder methods on pipelines that configure visibility:

| Method | Effect |
|--------|--------|
| `.transparent()` | All agents user-facing |
| `.filtered()` | Only terminal agents user-facing |
| `.annotated()` | All events pass through with metadata |

## Per-Agent Overrides

| Method | Effect |
|--------|--------|
| `.show()` | Force agent events to be user-facing |
| `.hide()` | Force agent events to be internal |
