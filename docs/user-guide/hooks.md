# Hooks — The Unified Observation and Intervention Layer

## What hooks are for

Hooks are the single, session-scoped extension point that every harness
mechanism builds on. They let you intercept ADK's execution at 12 lifecycle
points without writing a callback wrapper or a tree-walker:

| When | Event | Use case |
|---|---|---|
| Before a tool runs | `pre_tool_use` | Block dangerous commands, rewrite args, ask for approval |
| After a tool runs | `post_tool_use` | Lint an edit, checkpoint the workspace, log the result |
| On tool error | `tool_error` | Retry policy, structured error telemetry |
| Before a model call | `pre_model` | Strip secrets, inject system messages, budget check |
| After a model call | `post_model` | Parse structured output, capture usage, stream to UI |
| On model error | `model_error` | Fall back to cheaper model, surface quota errors |
| Before / after an agent turn | `pre_agent` / `post_agent` | Session setup, memory load/save |
| Session start / end | `session_start` / `session_end` | One-time init and cleanup |
| User prompt submitted | `user_prompt_submit` | Redact PII, add context, record turn |
| ADK event emitted | `on_event` | Custom event taps |
| Harness extensions | `pre_compact`, `permission_request`, `notification` | Plumbing for the rest of the harness foundations |

They fire **for every invocation in the tree**, not just the top-level agent.
Because they install as an ADK `BasePlugin`, adk-fluent does not have to walk
your agent hierarchy and attach callbacks to every sub-agent — ADK's plugin
manager does that automatically, including for dynamically-spawned subagents.

This is the **only** layer adk-fluent ships for intercepting runtime behavior.
Permissions, budgets, compression, plan mode — they all dispatch through this
foundation.

## The shape of a hook

Every hook is the same function: it takes a `HookContext` and returns a
`HookDecision`. Nothing else.

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import H
from adk_fluent._hooks import HookContext, HookDecision, HookEvent

def block_rm_rf(ctx: HookContext) -> HookDecision:
    command = (ctx.tool_input or {}).get("command", "")
    if "rm -rf" in command:
        return HookDecision.deny("rm -rf is forbidden in this workspace")
    return HookDecision.allow()

hooks = H.hooks("/project").on(HookEvent.PRE_TOOL_USE, block_rm_rf)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { H, HookContext, HookDecision, HookEvent } from "adk-fluent-ts";

function blockRmRf(ctx: HookContext): HookDecision {
  const command = (ctx.toolInput ?? {}).command ?? "";
  if (command.includes("rm -rf")) {
    return HookDecision.deny("rm -rf is forbidden in this workspace");
  }
  return HookDecision.allow();
}

const hooks = H.hooks("/project").on(HookEvent.PreToolUse, blockRmRf);
```
:::
::::

The decision types are fixed. There are six, and they compose — a `deny`
short-circuits the chain, a `modify` rewrites arguments and lets downstream
hooks see the new values, an `inject` queues a system message for the next
LLM call, and `allow` is the "no opinion" pass-through.

```
HookDecision.allow()                      # Pass through
HookDecision.deny(reason)                  # Short-circuit with an error
HookDecision.modify(tool_input=new_args)   # Rewrite tool arguments
HookDecision.replace(output=result)        # Short-circuit with a fake result
HookDecision.ask(prompt)                   # Surface a permission request
HookDecision.inject(system_message=text)   # Queue a transient system message
```

Return `None` from a hook and it is treated as `allow()`. Raising an
exception is treated as `deny(reason=str(exc))` — hook authors never have to
remember to wrap everything in a try/except.

## Registering hooks

`H.hooks(workspace=...)` returns a `HookRegistry`. All registration methods
are chainable.

```python
from adk_fluent import H
from adk_fluent._hooks import HookDecision, HookEvent, HookMatcher

hooks = (
    H.hooks("/project")
    # Callable hooks — full decision power
    .on(HookEvent.PRE_TOOL_USE, block_rm_rf,
        match=HookMatcher.for_tool(HookEvent.PRE_TOOL_USE, "bash"))
    .on(HookEvent.POST_TOOL_USE, lint_after_edit,
        match=HookMatcher.for_tool(
            HookEvent.POST_TOOL_USE, "edit_file", file_path="*.py"))
    # Shell hooks — notification-only, always allow
    .shell(HookEvent.POST_TOOL_USE, "ruff check {tool_input[file_path]}",
           match=HookMatcher.for_tool(HookEvent.POST_TOOL_USE, "edit_file"))
    .shell(HookEvent.SESSION_END, "echo 'session {session_id} ended'")
)
```

Callable hooks are the canonical way to intervene — they get the full
`HookContext` and return a `HookDecision`. Shell hooks are for side effects
you would otherwise script around a subprocess: lint-on-save, external
notifications, metrics push. They never block the tool call, and their exit
code does not affect the decision chain.

### Matchers

A `HookMatcher` filters which contexts a hook sees. The filter is layered:
event → tool name regex → per-argument glob → optional predicate. All layers
are ANDed.

```python
# Most specific: a regex on the tool name plus an fnmatch glob on an arg
HookMatcher(
    event=HookEvent.PRE_TOOL_USE,
    tool_name="edit_file",
    args={"file_path": "*.py"},
)

# Shorthand
HookMatcher.for_tool(HookEvent.PRE_TOOL_USE, "edit_file", file_path="*.py")

# Or the equivalent H factory
H.hook_match(HookEvent.PRE_TOOL_USE, "edit_file", file_path="*.py")
```

A matcher with no filter fires for every context of its declared event — the
normal case for session-wide hooks.

### Shell placeholders

Shell hook commands support template substitution from the context:

| Placeholder | Value |
|---|---|
| `{event}` | The firing event name |
| `{tool_name}` | Tool name (for tool events) |
| `{agent_name}` | Agent name |
| `{session_id}` | ADK session id |
| `{invocation_id}` | ADK invocation id |
| `{user_message}` | Raw user prompt (for `user_prompt_submit`) |
| `{model}` | Model name (for model events) |
| `{error}` | Error string (for `*_error` events) |
| `{tool_input[key]}` | Value of `ctx.tool_input[key]` |

All substituted values are `shlex.quote`'d so spaces, quotes, and shell
metacharacters do not break the command. The context is also exported as
`ADKF_HOOK_*` environment variables for scripts that prefer env access over
argv.

## Installing the registry

The registry produces an ADK `BasePlugin` via `registry.as_plugin()`. Install
it on the `App` or `Runner` that drives your agent:

```python
from google.adk.apps import App
from google.adk.runners import Runner

app = App(name="coder", root_agent=agent.build())
runner = Runner(app=app, plugins=[hooks.as_plugin()])
```

Because the plugin is installed at the App/Runner layer, it is session-scoped
and inherited by every subagent in the invocation tree automatically — no
tree-walking, no per-agent wrapping.

## Decision semantics in detail

### `allow`

Pass-through. Equivalent to returning `None` from an ADK callback. This is
the "no opinion" decision — downstream hooks keep firing and the wrapped call
proceeds normally. If you are unsure what to return, return `allow()`.

**Never** return an empty dict from a raw ADK callback. ADK uses
"first-truthy-wins" semantics for callback chains — an empty dict counts as
"I made a decision, stop calling". The `HookDecision` layer handles this for
you; always use the decision constructors.

### `deny(reason)`

Short-circuit the wrapped call with a failure. For tool events, the plugin
synthesises a tool response dict containing the error so the LLM sees why the
tool did not run. For model events, it builds an `LlmResponse` with
`error_message=reason`. For agent events, it builds a model `Content` with
the reason text.

After a deny, subsequent hooks for the same event are **not** called. Deny is
terminal.

### `modify(tool_input=new_args)`

Only meaningful for `pre_tool_use`. The plugin mutates the ADK
`function_args` dict in place (ADK passes it by reference) and returns
`None`, letting the tool proceed with the rewritten arguments. Downstream
hooks in the same dispatch see the rewritten args — this is how redaction
chains work.

### `replace(output)`

Short-circuit the wrapped call and pretend the tool, model, or agent produced
`output` directly. For tools, `output` should be a dict (mapped to the tool
response). For models, an `LlmResponse` (used as-is). For agents, a
`Content` object. For scalars, the plugin wraps them in the smallest sensible
container.

Replace is terminal.

### `ask(prompt)`

Raise a permission request. The plugin raises a `HookAsk` exception carrying
the prompt; the harness runtime (`H.repl()`, permission plugin, etc.) catches
it and surfaces the prompt to the user. Until the runtime supplies an
approval path the call terminates cleanly as a tool error — the LLM sees the
prompt and can retry.

Ask is terminal.

### `inject(system_message=text)`

Append a transient system message to the session's `SystemMessageChannel`.
The channel is a reserved-key list (`_adkf_hook_system_messages`) on the ADK
session state. On the next `before_model` callback, the plugin drains the
channel and prepends the drained messages to `llm_request.contents` as a
`[system] ...` user-role turn.

Inject is a side effect — it does **not** short-circuit the chain. You can
return `inject` from a `post_tool_use` hook to tell the model what just
changed, while still letting the wrapped call complete normally. Multiple
injects in the same dispatch are concatenated in order.

## Folding multiple hooks

When several hooks match the same event, they run in registration order. The
registry folds their decisions:

1. `allow` hooks are skipped — they have no effect.
2. `inject` decisions are collected into a pending list and attached to the
   final decision as `metadata["pending_injects"]`.
3. `modify` rewrites `ctx.tool_input` in place and the chain continues — the
   next hook sees the rewritten args.
4. The first `deny`, `replace`, or `ask` is terminal — iteration stops and
   that decision becomes the final one, with any pending injects still
   attached so they run as side effects.

This means a redactor + an approval gate + a usage tracker can all coexist on
the same event without knowing about each other, and the harness author does
not have to decide a priori how conflicts resolve.

## Cookbook

### Block destructive commands

```python
def block_destructive(ctx):
    command = (ctx.tool_input or {}).get("command", "")
    banned = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };:"]
    for needle in banned:
        if needle in command:
            return HookDecision.deny(f"blocked: {needle!r}")
    return HookDecision.allow()

hooks.on(
    HookEvent.PRE_TOOL_USE,
    block_destructive,
    match=HookMatcher.for_tool(HookEvent.PRE_TOOL_USE, "bash"),
)
```

### Redact secrets before every tool call

```python
import re

SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|password)\s*[:=]\s*\S+")

def redact_secrets(ctx):
    command = (ctx.tool_input or {}).get("command")
    if command and SECRET_RE.search(command):
        new = dict(ctx.tool_input or {})
        new["command"] = SECRET_RE.sub(r"\1=***", command)
        return HookDecision.modify(new)
    return HookDecision.allow()

hooks.on(HookEvent.PRE_TOOL_USE, redact_secrets)
```

### Lint-on-save with a shell hook

```python
hooks.shell(
    HookEvent.POST_TOOL_USE,
    "ruff check {tool_input[file_path]}",
    match=HookMatcher.for_tool(
        HookEvent.POST_TOOL_USE, "edit_file", file_path="*.py"
    ),
)
```

### Tell the LLM what just happened

```python
def nudge_after_edit(ctx):
    path = (ctx.tool_input or {}).get("file_path")
    return HookDecision.inject(
        f"You just edited {path}. Consider running the test suite next."
    )

hooks.on(
    HookEvent.POST_TOOL_USE,
    nudge_after_edit,
    match=HookMatcher.for_tool(HookEvent.POST_TOOL_USE, "edit_file"),
)
```

### Stub an expensive tool in tests

```python
def fake_search(ctx):
    return HookDecision.replace({"results": [{"title": "stub", "url": ""}]})

hooks.on(
    HookEvent.PRE_TOOL_USE,
    fake_search,
    match=HookMatcher.for_tool(HookEvent.PRE_TOOL_USE, "web_search"),
)
```

### Ask the user before running anything destructive

```python
def gate_destructive(ctx):
    tool = ctx.tool_name or ""
    if tool in {"edit_file", "delete_file", "bash"}:
        return HookDecision.ask(f"Allow {tool} with args {ctx.tool_input}?")
    return HookDecision.allow()

hooks.on(HookEvent.PRE_TOOL_USE, gate_destructive)
```

## Relationship to ADK callbacks

If you already use raw ADK callbacks (`before_tool_callback`,
`before_model_callback`, etc.), hooks are the replacement. They give you:

- A structured decision type instead of the subtle first-truthy-wins return
  contract ADK documents but is easy to get wrong.
- One API for every lifecycle point instead of learning each callback's
  argument shape and return type.
- Matcher-based filtering instead of per-hook name and arg checks.
- Automatic session-scoping and subagent inheritance via the plugin manager.
- A first-class `inject` channel for transient system messages.

Hooks and raw callbacks can coexist — the plugin does not interfere with
agent-level callbacks you still want to write by hand — but anything new
should be written as a hook.

## API reference

```python
from adk_fluent import H
from adk_fluent._hooks import (
    HookAction,          # String constants: "allow" / "deny" / ...
    HookContext,         # Normalized context passed to every hook
    HookDecision,        # Structured return type
    HookEvent,           # Canonical event names (PRE_TOOL_USE, etc.)
    HookMatcher,         # Event + regex + arg glob + predicate filter
    HookPlugin,          # ADK BasePlugin that dispatches a registry
    HookRegistry,        # User-facing registry (chainable)
    HookEntry,           # Single registered hook (callable or shell)
    ALL_EVENTS,          # frozenset of every valid event name
    SystemMessageChannel,            # Transient system message queue
    SYSTEM_MESSAGE_STATE_KEY,        # Reserved session state key
)
```

| Factory | Returns |
|---|---|
| `H.hooks(workspace=None)` | A new `HookRegistry` |
| `H.hook_decision()` | The `HookDecision` class (for `H.hook_decision().deny(...)`) |
| `H.hook_match(event, tool_name=None, **args)` | A `HookMatcher` |

| Method | Effect |
|---|---|
| `registry.on(event, fn, match=None, name=None)` | Register a callable hook |
| `registry.shell(event, command, match=None, timeout=30, blocking=False)` | Register a shell hook |
| `registry.merge(other)` | Combine two registries (new instance) |
| `registry.as_plugin(name="adkf_hook_plugin")` | Produce the ADK `BasePlugin` |
| `registry.dispatch(ctx)` | Fire all matching hooks for `ctx` (async) |
| `registry.entries_for(event)` | List of registered `HookEntry` for an event |

See the master plan at `docs/plans/2026-04-12-harness-foundations-master-plan.md`
for where hooks fit in the nine-mechanism foundation, and
`tests/manual/test_hooks_modules.py` for the exhaustive test module.
