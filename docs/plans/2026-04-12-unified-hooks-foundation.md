# Unified Hooks Foundation

**Date**: 2026-04-12
**Status**: In progress
**Scope**: Foundational — new `adk_fluent._hooks` package + H namespace refactor

## Motivation

adk-fluent currently has two disjoint "hook" systems:

1. **System A — Agent-scoped callbacks**: `Agent.before_tool(fn)` / `.after_tool(fn)` /
   `.before_model(fn)` / `.after_model(fn)` / `.before_agent(fn)` / `.after_agent(fn)`.
   These are real ADK canonical callbacks with decision power. They only apply to
   the agent instance they are attached to — sub-agents and agent-tools do NOT
   inherit them unless the user threads them through manually.

2. **System B — Harness HookRegistry**: `H.hooks().on_edit("ruff check {file}")`.
   Shell-command-only, fire-and-forget, executed via `subprocess`. Cannot block
   a tool, cannot modify tool input, cannot inject a system message, cannot ask
   the user. It is a pure notification channel.

Claude Agent SDK, Claude Code, and Deep Agents all expose a single unified hook
surface that has **session scope** (applies invocation-wide across sub-agents)
AND **decision power** (allow / deny / ask / modify / replace / inject). We have
neither in one place.

This plan builds the missing foundation: a single `adk_fluent._hooks` package
that is session-scoped, subagent-inherited by construction, and can return real
decisions to the ADK runtime. The harness `H.hooks()` becomes a thin surface
over that foundation. No backwards-compatibility shim — the old shell-only
`HookRegistry` is deleted outright.

## Key discovery (primary-source verified)

The ADK `BasePlugin` in `google.adk.plugins.base_plugin` is already the exact
session-scoped, subagent-inherited callback layer we need. Plugins live on
`App.plugins` / `Runner.plugins`, are dispatched by `plugin_manager` BEFORE the
agent's canonical callbacks at every invocation point, and they see every tool
call / model call / agent run regardless of depth. We do not need to invent a
tree-walker; we build one plugin and install it once.

ADK Plugin callbacks (verified against source):

| Plugin method                       | Fires                                    |
|-------------------------------------|------------------------------------------|
| `on_user_message_callback`          | Session receives a user message          |
| `before_run_callback`               | Invocation starts (session_start-ish)    |
| `before_agent_callback`             | Before each agent runs                   |
| `after_agent_callback`              | After each agent runs                    |
| `before_model_callback`             | Before each LLM call                     |
| `after_model_callback`              | After each LLM call                      |
| `on_model_error_callback`           | LLM raised                               |
| `before_tool_callback`              | Before each tool call                    |
| `after_tool_callback`               | After each tool call                     |
| `on_tool_error_callback`            | Tool raised                              |
| `on_event_callback`                 | Every ADK Event yielded                  |
| `after_run_callback`                | Invocation completes (session_end-ish)   |

Semantics (verified in `flows/llm_flows/functions.py:480-560`,
`flows/llm_flows/base_llm_flow.py:985-1062`,
`agents/base_agent.py:440-539`):

- **Plugin runs first**, then agent-level canonical callbacks.
- **First truthy wins** — not first non-None. A plugin returning an empty dict
  `{}` is treated as "no decision".
- `function_args` is **mutable in-place**. A before_tool callback can mutate the
  dict and return `None` to rewrite the tool input.
- `before_agent` returning truthy content terminates the invocation
  (`ctx.end_invocation = True`).

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│ adk_fluent._hooks                     (new foundational pkg)   │
│                                                                │
│  _decision.py   HookDecision   allow/deny/ask/modify/replace/  │
│                                 inject — ADK-wire compatible   │
│  _events.py     HookEvent      canonical event names           │
│                 HookContext    normalized call context         │
│  _matcher.py    HookMatcher    event + tool-name regex + args  │
│  _registry.py   HookRegistry   .on() / .shell() / .merge() /   │
│                                 .as_plugin()                   │
│  _plugin.py     HookPlugin     ADK BasePlugin subclass that    │
│                                 dispatches registry entries    │
│  _channel.py    SystemMessage  reserved state key + auto-drain │
│                  Channel       before_model injector           │
└────────────────────────────────────────────────────────────────┘
                          ▲
                          │ re-export
┌────────────────────────────────────────────────────────────────┐
│ adk_fluent._harness._namespace                                 │
│  H.hooks(workspace=...)   → HookRegistry                       │
│  H.hook_decision          → HookDecision constructors          │
│  H.hook_match             → HookMatcher                        │
└────────────────────────────────────────────────────────────────┘
                          ▲
                          │ install
┌────────────────────────────────────────────────────────────────┐
│ adk_fluent.runtime.App.plugin(registry.as_plugin())            │
│ Agent.harness(..., hooks=registry)                             │
└────────────────────────────────────────────────────────────────┘
```

## HookDecision protocol

```python
class HookDecision:
    @staticmethod
    def allow() -> HookDecision: ...          # → None (ADK passthrough)
    @staticmethod
    def deny(reason: str) -> HookDecision: ... # before_tool: returns a dict
                                               # carrying an error the LLM sees
    @staticmethod
    def ask(prompt: str) -> HookDecision: ... # raises PermissionRequired; the
                                               # harness runtime catches it
    @staticmethod
    def modify(tool_input: dict) -> HookDecision: ...  # mutates function_args
    @staticmethod
    def replace(output: Any) -> HookDecision: ...      # short-circuits a call
    @staticmethod
    def inject(system_message: str) -> HookDecision: ... # appends to the
                                                          # SystemMessageChannel
```

Each decision has a method `to_adk(event)` that translates it to whatever the
caller expects at that particular ADK callback point:

| Event          | allow | deny          | modify        | replace           |
|----------------|-------|---------------|---------------|-------------------|
| pre_tool_use   | None  | {"error":...} | mutate + None | dict output       |
| post_tool_use  | None  | {"error":...} | —             | dict output       |
| pre_model      | None  | LlmResponse   | mutate + None | LlmResponse       |
| post_model     | None  | LlmResponse   | —             | LlmResponse       |
| pre_agent      | None  | Content       | —             | Content           |

## Event taxonomy

Canonical names used by `HookRegistry.on(event=...)`:

- `pre_tool_use`, `post_tool_use`, `tool_error`
- `pre_model`, `post_model`, `model_error`
- `pre_agent`, `post_agent`, `agent_error`
- `user_prompt_submit` → ADK `on_user_message_callback`
- `session_start`      → ADK `before_run_callback`
- `session_end`        → ADK `after_run_callback`
- `on_event`           → ADK `on_event_callback`
- `pre_compact`        (harness — fires before ContextCompressor runs)
- `permission_request` (harness — fires when a permission prompt is raised)
- `notification`       (harness — arbitrary messages from H primitives)

## HookMatcher

```python
HookMatcher(
    event="pre_tool_use",
    tool_name=r"^(edit_file|write_file)$",   # regex
    args={"file_path": "*.py"},              # fnmatch per key
)
```

`HookRegistry.on(event, fn, match=HookMatcher(...))` — matcher is evaluated
inside `HookPlugin.before_tool_callback` before the callable is invoked.

## SystemMessageChannel

A reserved state key `_adkf_hook_system_messages: list[str]`. Any hook that
returns `HookDecision.inject("…")` appends to this list. A built-in
`before_model` plugin callback drains the list and prepends the messages to the
outgoing `LlmRequest.contents` as a system turn. This gives hooks the Claude
Code "additional system prompt" affordance without patching the agent's static
instruction.

## Phase plan

1. **P1 — pure data**: `_decision.py`, `_events.py`, `_matcher.py`. Unit tests
   for the decision constructors, matcher glob, event enum.
2. **P2 — HookPlugin**: ADK `BasePlugin` subclass. Implements all 12 plugin
   callbacks, delegates to registry entries filtered by matcher, collapses
   multiple decisions using first-truthy-wins, translates via `decision.to_adk`.
3. **P3 — HookRegistry**: `.on(event, fn, match=)`, `.shell(event, cmd, match=)`,
   `.merge(other)`, `.as_plugin() -> HookPlugin`. Shell entries wrap a subprocess
   call inside a function that always returns `HookDecision.allow()` — shell
   hooks remain notification-only by design.
4. **P4 — SystemMessageChannel**: reserved state key constant + drain-inject
   before_model callback wired into `HookPlugin`.
5. **P5 — H surface**: replace `H.hooks()` body with `HookRegistry(workspace)`;
   expose `H.hook_decision` and `H.hook_match`. Delete `_harness/_hooks.py` and
   update all 9 import sites.
6. **P6 — docs**: write `docs/user-guide/hooks.md` end-to-end; update
   `docs/user-guide/harness.md` Layer 4 section to link to the new guide.
7. **P7 — tests**: decision protocol, matcher, plugin dispatch, shell fallback,
   system message channel, integration with `App.plugin(...)`.

## Non-goals

- No new hook points beyond what ADK already surfaces + the three harness
  extensions listed above.
- No async shell runner overhaul — shell hooks reuse the existing
  `asyncio.create_subprocess_shell` path but wrapped inside a function that
  always returns allow.
- No visual / UI rendering here — rendering stays in `_renderer.py`.

## Deletion list

- `python/src/adk_fluent/_harness/_hooks.py` (old shell-only HookRegistry)
- Import site updates in:
  - `python/src/adk_fluent/__init__.py`
  - `python/src/adk_fluent/__init__.pyi`
  - `python/src/adk_fluent/_harness/__init__.py`
  - `python/src/adk_fluent/_harness/_event_bus.py`
  - `python/src/adk_fluent/_harness/_namespace.py`
  - `python/src/adk_fluent/_harness/_repl.py`
  - `python/tests/manual/test_harness_modules.py`
