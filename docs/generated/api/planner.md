# Module: `planner`

## Builders in this module

| Builder | Description |
|---------|-------------|
| [BasePlanner](builder-BasePlanner) | Abstract base class for all planners. |
| [BuiltInPlanner](builder-BuiltInPlanner) | The built-in planner that uses model's built-in thinking features. |
| [PlanReActPlanner](builder-PlanReActPlanner) | Plan-Re-Act planner that constrains the LLM response to generate a plan before any action/observation. |

(builder-BasePlanner)=
## BasePlanner

> Fluent builder for `google.adk.planners.base_planner.BasePlanner`

Abstract base class for all planners.

**Quick start:**

```python
from adk_fluent import BasePlanner

result = (
    BasePlanner("args_value", "kwargs_value")
    .build()
)
```

### Constructor

```python
BasePlanner(args: Any, kwargs: Any)
```

| Argument | Type |
|----------|------|
| `args` | `Any` |
| `kwargs` | `Any` |

### Control Flow & Execution

#### `.build() -> BasePlanner`

Resolve into a native ADK BasePlanner.

---

(builder-BuiltInPlanner)=
## BuiltInPlanner

> Fluent builder for `google.adk.planners.built_in_planner.BuiltInPlanner`

The built-in planner that uses model's built-in thinking features.

**Quick start:**

```python
from adk_fluent import BuiltInPlanner

result = (
    BuiltInPlanner("thinking_config_value")
    .build()
)
```

### Constructor

```python
BuiltInPlanner(thinking_config: types.ThinkingConfig)
```

| Argument | Type |
|----------|------|
| `thinking_config` | `types.ThinkingConfig` |

### Control Flow & Execution

#### `.build() -> BuiltInPlanner`

Resolve into a native ADK BuiltInPlanner.

---

(builder-PlanReActPlanner)=
## PlanReActPlanner

> Fluent builder for `google.adk.planners.plan_re_act_planner.PlanReActPlanner`

Plan-Re-Act planner that constrains the LLM response to generate a plan before any action/observation.

**Quick start:**

```python
from adk_fluent import PlanReActPlanner

result = (
    PlanReActPlanner("args_value", "kwargs_value")
    .build()
)
```

### Constructor

```python
PlanReActPlanner(args: Any, kwargs: Any)
```

| Argument | Type |
|----------|------|
| `args` | `Any` |
| `kwargs` | `Any` |

### Control Flow & Execution

#### `.build() -> PlanReActPlanner`

Resolve into a native ADK PlanReActPlanner.
