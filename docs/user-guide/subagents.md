# Subagents

The `adk_fluent._subagents` package is adk-fluent's dynamic specialist-spawning
mechanism. It mirrors Claude Agent SDK's Task tool pattern: a parent LLM keeps
control of the conversation and, when it needs focused work done, calls a
`task(role, prompt)` tool that dispatches a fresh specialist, waits for the
answer, and folds the result back into the parent's context window.

A subagent is **not** a long-running teammate — it is a short-lived worker with
its own instruction, its own toolset, and a disposable context. The parent
never sees the specialist's scratchpad, only its final output.

## Why subagents?

Static sub-agents (`.sub_agent()`) commit the parent to a fixed topology at
build time. Subagents invert that: the parent carries a **registry of roles**
and decides at runtime which specialist to invoke and with what brief. That
gives you three properties you cannot get from a static topology:

- **Context isolation** — the specialist burns its own tokens and returns a
  short summary, so the parent's context stays lean.
- **Dynamic routing** — the parent LLM picks the role based on the actual
  task, not a hand-wired predicate.
- **Parallel scaling** — the same registry can be invoked concurrently from
  multiple turns without any topology duplication.

## Quick start

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import (
    Agent,
    FakeSubagentRunner,
    H,
    SubagentSpec,
)

registry = H.subagent_registry(
    [
        H.subagent_spec(
            role="researcher",
            instruction="Find three authoritative papers and summarise them.",
            description="Deep research specialist",
        ),
        H.subagent_spec(
            role="reviewer",
            instruction="Critique the draft for factual errors.",
            description="Technical critic",
        ),
    ]
)

task = H.task_tool(registry, FakeSubagentRunner())

coordinator = (
    Agent("coordinator", "gemini-2.5-flash")
    .instruct("Coordinate specialists. Use the `task` tool to delegate.")
    .tool(task)
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import {
  Agent,
  FakeSubagentRunner,
  H,
  SubagentSpec,
} from "adk-fluent-ts";

const registry = H.subagentRegistry([
  H.subagentSpec({
    role: "researcher",
    instruction: "Find three authoritative papers and summarise them.",
    description: "Deep research specialist",
  }),
  H.subagentSpec({
    role: "reviewer",
    instruction: "Critique the draft for factual errors.",
    description: "Technical critic",
  }),
]);

const task = H.taskTool(registry, new FakeSubagentRunner());

const coordinator = new Agent("coordinator", "gemini-2.5-flash")
  .instruct("Coordinate specialists. Use the `task` tool to delegate.")
  .tool(task);
```
:::
::::

The generated `task` callable has a docstring that enumerates every registered
role, so the parent LLM gets an accurate menu when it decides who to call.

## Core types

### `SubagentSpec`

A frozen dataclass describing one specialist. Fields:

| Field | Purpose |
| --- | --- |
| `role` | Unique identifier the parent uses to invoke it. |
| `instruction` | System instruction handed to the specialist at spawn time. |
| `description` | One-line summary shown in the parent's tool docstring. |
| `model` | Optional model override (defaults to the runner's default). |
| `tool_names` | Tuple of tool names the specialist is allowed to use. |
| `permission_mode` | Optional permission mode (see [permissions](permissions.md)). |
| `max_tokens` | Optional token ceiling for the specialist. |
| `metadata` | Free-form dict for runner-specific extensions. |

Specs are immutable; the registry rejects empty roles and empty instructions up
front.

### `SubagentRegistry`

An ordered catalogue of specs with explicit mutation semantics:

- `.register(spec)` — add a new role, raising on duplicates.
- `.replace(spec)` — overwrite an existing role (or add it).
- `.unregister(role)` — silent no-op if absent.
- `.get(role)` / `.require(role)` — lookup, returning `None` or raising.
- `.roles()` — insertion-ordered role list.
- `.roster()` — human-readable catalogue that the task tool embeds in its
  docstring so the parent LLM can pick a specialist.

### `SubagentResult`

What runners return. Carries `role`, `output`, `usage`, `artifacts`,
`metadata`, and an optional `error`. Two conveniences:

- `.is_error` — `True` if the `error` field is set.
- `.to_tool_output()` — formats as `[role] output` or `[role:error] reason`
  for return from the task tool.

### `SubagentRunner`

The runtime contract. A `@runtime_checkable` Protocol with one method:

```python
def run(
    self,
    spec: SubagentSpec,
    prompt: str,
    context: dict[str, Any] | None = None,
) -> SubagentResult: ...
```

Runners are deliberately **not** coupled to ADK — you can wire in a local
`Runner`, an A2A endpoint, or canned responses in tests. The ship-included
`FakeSubagentRunner` is a deterministic runner that:

- Defaults to echoing the prompt.
- Accepts a custom `responder` callable.
- Accepts `error_for_role` to simulate failures per role.
- Records every invocation in `.calls` for assertions.
- Catches responder exceptions and surfaces them as error results.

### `make_task_tool`

```python
task = make_task_tool(
    registry,
    runner,
    *,
    context_provider=lambda: {"turn": ctx.turn},
    tool_name="task",
)
```

Returns a callable with signature `task(role: str, prompt: str) -> str`. The
generated function:

- Looks up the spec and returns a structured error for unknown roles (with the
  list of known roles).
- Calls `context_provider()` once per invocation and threads the result into
  the runner.
- Catches runner exceptions and converts them into `[role:error] …` strings.
- Has its `__doc__` rewritten at build time to list every registered role so
  the parent LLM sees an accurate menu.

Use `tool_name=` to expose the tool under a different identifier — handy when
you want multiple dispatch tools in the same agent.

## H namespace sugar

```python
H.subagent_spec(role, instruction, ...)
H.subagent_registry(specs)
H.task_tool(registry, runner, *, context_provider=None, tool_name="task")
```

These mirror the underlying classes 1:1 but keep imports short when you stay
inside the fluent surface.

## Testing

`FakeSubagentRunner` is the canonical test double. Because `make_task_tool`
returns a plain callable, you can unit-test dispatch without touching ADK:

```python
registry = H.subagent_registry([H.subagent_spec("r", "instruction")])
runner = FakeSubagentRunner(responder=lambda spec, prompt, ctx: "ok")
task = H.task_tool(registry, runner)

assert task("r", "hi") == "[r] ok"
assert task("missing", "hi").startswith("Error: unknown subagent role")
```

## Design notes

- Specs are frozen dataclasses — you can hash them, diff them, and share them
  across threads without worrying about accidental mutation.
- The registry's `roster()` is intentionally plain text: the parent LLM reads
  a tool docstring, not a schema, and Markdown rendering is the responsibility
  of whoever embeds the menu.
- Runners are synchronous. If your backend is async, wrap it in a runner that
  drives the event loop; the task tool never awaits.
- The parent LLM is always in charge. A subagent cannot transfer control
  sideways or spawn its own subagents unless its own toolset includes a task
  tool — which you control.
