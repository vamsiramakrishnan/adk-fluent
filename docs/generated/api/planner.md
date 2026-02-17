# Module: `planner`

# BasePlanner

> Fluent builder for `google.adk.planners.base_planner.BasePlanner`

Abstract base class for all planners.

## Constructor

```python
BasePlanner(args, kwargs)
```

| Argument | Type |
|----------|------|
| `args` | `Any` |
| `kwargs` | `Any` |

## Terminal Methods

### `.build() -> BasePlanner`

Resolve into a native ADK BasePlanner.

---

# BuiltInPlanner

> Fluent builder for `google.adk.planners.built_in_planner.BuiltInPlanner`

The built-in planner that uses model's built-in thinking features.

## Constructor

```python
BuiltInPlanner(thinking_config)
```

| Argument | Type |
|----------|------|
| `thinking_config` | `types.ThinkingConfig` |

## Terminal Methods

### `.build() -> BuiltInPlanner`

Resolve into a native ADK BuiltInPlanner.

---

# PlanReActPlanner

> Fluent builder for `google.adk.planners.plan_re_act_planner.PlanReActPlanner`

Plan-Re-Act planner that constrains the LLM response to generate a plan before any action/observation.

## Constructor

```python
PlanReActPlanner(args, kwargs)
```

| Argument | Type |
|----------|------|
| `args` | `Any` |
| `kwargs` | `Any` |

## Terminal Methods

### `.build() -> PlanReActPlanner`

Resolve into a native ADK PlanReActPlanner.
