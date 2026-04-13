# Plan mode

The `adk_fluent._plan_mode` package is adk-fluent's **plan-then-execute
mechanism**. It consolidates three separate pieces that used to live
in different corners of the harness:

1. The *latch* — a three-state machine (`off` / `planning` /
   `executing`) that tracks whether the agent is currently describing
   a plan or executing it.
2. The *tools* — `enter_plan_mode` and `exit_plan_mode`, which the LLM
   calls to drive the latch.
3. The *enforcement* — a permission policy and an ADK plugin that
   deny mutating tool calls while the latch is in `planning`.

Claude Agent SDK ships the same split: a permission mode called
`"plan"` that denies mutations, and a runtime tool surface that lets
the model flip in and out of planning. adk-fluent unifies them so you
can wire the whole thing up in one line.

## The five pieces

| Type | Role | Mutable? |
| --- | --- | --- |
| `PlanMode` | Latch. Holds state + plan text + observers. | mutable |
| `MUTATING_TOOLS` | Default set of tool names treated as mutating. | frozen set |
| `plan_mode_tools(latch)` | Factory for `enter_plan_mode` / `exit_plan_mode`. | — |
| `PlanModePolicy` | Frozen wrapper that flips a `PermissionPolicy` to `plan` mode while the latch is planning. | frozen |
| `PlanModePlugin` | ADK `BasePlugin` that denies mutating tools via `before_tool_callback`. | wraps a latch |

## Quick start

### Direct wiring

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, H
from adk_fluent._permissions import PermissionPolicy

latch = H.plan_mode()

base_policy = PermissionPolicy(allow=frozenset({"read_file", "grep_search"}))
policy = H.plan_mode_policy(base_policy, latch)

agent = (
    Agent("planner", "gemini-2.5-pro")
    .instruct("Plan a refactor. Call enter_plan_mode, outline steps, then exit_plan_mode.")
    .tools(latch.tools() + [read_file, grep_search, edit_file])
    .build()
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, H, PermissionPolicy } from "adk-fluent-ts";

const latch = H.planMode();

const basePolicy = new PermissionPolicy({
  allow: new Set(["read_file", "grep_search"]),
});
const policy = H.planModePolicy(basePolicy, latch);

const agent = new Agent("planner", "gemini-2.5-pro")
  .instruct("Plan a refactor. Call enter_plan_mode, outline steps, then exit_plan_mode.")
  .tools([...latch.tools(), readFile, grepSearch, editFile])
  .build();
```
:::
::::

While `latch.is_planning`, `policy.check("edit_file")` returns a
`deny` decision with reason ``"Plan mode denies mutating tool
'edit_file'."`` Once the LLM calls `exit_plan_mode(plan=...)` the
latch flips to `executing` and the policy falls back to the base
behaviour.

### Session-wide plugin (recommended)

For multi-agent apps, install `PlanModePlugin` on the root app. It
installs a `before_tool_callback` that blocks mutating tools across
every agent in the invocation tree:

```python
from adk_fluent import App, H, Runner

plugin = H.plan_mode_plugin()

runner = (
    Runner()
    .app(
        App("coder")
        .root(my_agent)
        .plugin(plugin)
    )
    .build()
)

# Anywhere in the tree: the LLM flips the shared latch via its tool calls
my_agent.tools(plugin.latch.tools() + [...])
```

The plugin's `latch` is the single source of truth for the whole
session. Observers attached via `plugin.latch.subscribe(cb)` fire on
every transition.

## The latch

`PlanMode` owns three fields and fires observers on every change:

```python
from adk_fluent._plan_mode import PlanMode

latch = PlanMode()

def log(state: str, plan: str) -> None:
    print(f"transition -> {state} ({len(plan)} chars of plan)")

unsubscribe = latch.subscribe(log)

latch.enter()                # -> "planning"
latch.exit("1. Do X\n2. Done")  # -> "executing"
latch.reset()                # -> "off"
unsubscribe()                # stop observing
```

Observers that raise are caught and swallowed — the latch is a
critical control surface and must not be broken by downstream bugs.

## The policy wrapper

`PlanModePolicy` is a frozen dataclass that takes a base
`PermissionPolicy` and a `PlanMode` latch. It passes through `check`
calls to an *effective* policy that is re-derived on every call:

```python
from adk_fluent._permissions import PermissionPolicy
from adk_fluent._plan_mode import PlanMode, PlanModePolicy

base = PermissionPolicy(
    allow=frozenset({"read_file"}),
    ask=frozenset({"bash", "write_file"}),
)
latch = PlanMode()
policy = PlanModePolicy(base=base, latch=latch)

# Outside planning: behaves like base
assert policy.check("write_file").is_ask

# Planning: write_file is denied, read_file still allowed
latch.enter()
assert policy.check("write_file").is_deny
assert policy.check("read_file").is_allow

# Executing: back to base behaviour
latch.exit("plan")
assert policy.check("write_file").is_ask
```

The wrapper is cheap — there is no cached intermediate policy, so
toggling the latch is an O(1) operation.

## The plugin

`PlanModePlugin` is a `BasePlugin` that installs a
`before_tool_callback` hook. While the latch is `planning`, any
mutating tool call returns an error dict instead of invoking the
tool:

```python
plugin = H.plan_mode_plugin()
plugin.latch.enter()

# The LLM calls write_file; the plugin intercepts and returns:
# {
#     "error": "Plan mode denies mutating tool 'write_file'. "
#              "Call exit_plan_mode(plan) before touching the workspace.",
#     "plan_mode_state": "planning",
# }
```

Because `BasePlugin` is session-scoped, one plugin install covers the
whole invocation tree without per-agent wiring.

## Relationship to `PermissionMode.PLAN`

`PermissionMode.PLAN` is the declarative half — it is what
`PermissionPolicy` looks up when you say "run in plan mode
regardless". `PlanMode` (the latch) is the *dynamic* half — it flips
based on tool calls. `PlanModePolicy` is the glue that lets you write
one base policy and let the latch decide, per-check, whether to apply
`PermissionMode.PLAN` on top of it.

In practice you rarely set `PermissionMode.PLAN` directly. Instead
you build a base policy with your normal `allow`/`ask`/`deny` rules,
wrap it in a `PlanModePolicy`, and let the LLM drive the latch.
