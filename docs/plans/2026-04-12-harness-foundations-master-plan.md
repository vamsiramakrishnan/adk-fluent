# Harness Foundations — Master Plan

**Date**: 2026-04-12
**Status**: In progress (hooks foundation complete)
**Scope**: Build nine atomic, session-scoped foundations under `adk_fluent/`
that match Claude Agent SDK and Deep Agents SDK capabilities. Expose through
`H`. Port to TypeScript after the Python side lands. No back-compat shims.

## The nine mechanisms

| # | Package | What it provides | Depends on |
|---|---|---|---|
| 1 | `adk_fluent._hooks` | Unified hook foundation (done) | — |
| 2 | `adk_fluent._permissions` | Decision-based permission layer with modes | `_hooks` |
| 3 | `adk_fluent._fs` | Pluggable workspace backend (local / memory / remote) | — |
| 4 | `adk_fluent._subagents` | Dynamic subagent spawner + `task()` tool | `_hooks`, `_permissions` |
| 5 | `adk_fluent._budget` | Session-scoped token / turn / cost tracker | `_hooks` |
| 6 | `adk_fluent._compression` | Structured compression with `pre_compact` hook | `_hooks`, `_budget` |
| 7 | `adk_fluent._session` | Durable session store with fork / replay | — |
| 8 | `adk_fluent._usage` | Single unified usage + cost tracker | `_hooks` |
| 9 | `adk_fluent._plan_mode` | Plan-only execution policy (falls out of #2 + #4) | `_permissions`, `_subagents` |

Every package follows the same internal shape:

```
adk_fluent/_<name>/
    __init__.py           public re-exports
    _<core>.py            pure-data types (frozen dataclasses)
    _decision.py          structured decision protocol (where applicable)
    _policy.py            declarative policy / registry
    _plugin.py            ADK BasePlugin subclass (session-scoped dispatch)
    _<adapters>.py        backends, stores, etc.
```

And every package is surfaced through `H` with a small number of top-level
factory methods plus a family of helper shortcuts, mirroring how `H.hooks()`
returns `HookRegistry` and `H.hook_decision` / `H.hook_match` help build
policies.

## Principled subagent decision

The most delicate architectural call in this plan. adk-fluent already has two
subagent mechanisms:

- `.sub_agent(child)` — registers a child as a transfer target. The LLM
  decides when to hand off via ADK's `transfer_to_agent` tool. Full control
  handoff.
- `.agent_tool(child)` — wraps a child as a callable tool. Parent stays in
  control; child returns a single result.

**Both are agent-scoped and build-time.** The topology is baked in when you
call `.build()`. This is the correct primitive for **designed workflows** —
code review pipelines, multi-stage research, supervised loops.

Claude Agent SDK's `task()` and Deep Agents' `subagents=[{"name": ...}]` are
different: they let the agent spawn a *dynamic* subagent at runtime, with a
prompt and tool set decided by the parent LLM mid-turn, returning a single
terminal result. They address a different use case — **task delegation**,
where the parent doesn't know at build time which subagents it will invoke.

### The principled answer

**Do not replace `.sub_agent()` or `.agent_tool()`.** They are the right
primitives for their layer and rebuilding them would break the existing
workflow surface and add zero value. They model build-time topology, and no
part of the new mechanism wants to change that.

**Build `_subagents` as a dynamic spawner that composes with the existing
mechanisms, not replaces them.** The spawner:

1. Accepts a `SubagentSpec` (name, prompt, tools, model, turn budget, tool
   filter, inherit_permissions).
2. Instantiates a fresh adk-fluent `Agent` builder, configures it from the
   spec, calls `.build()`, and runs it through a fresh `Runner` with **the
   parent's plugins inherited** (HookPlugin, PermissionPlugin, BudgetPlugin).
3. Returns only the final textual output to the parent, plus usage stats.
4. Exposes itself as an LLM-callable tool (`task` / `spawn_subagent`) so the
   parent agent can invoke it mid-turn.

This gives us:

- **Static topology** via `.sub_agent()` / `.agent_tool()` — unchanged.
- **Dynamic spawning** via `H.subagents().spawn(...)` and the `task` tool.
- **Single runtime** — both paths use the same ADK `Runner` + plugin
  infrastructure, so hooks / permissions / budgets apply uniformly.
- **No duplication** — the spawner is a thin composer over the existing
  `Agent` builder, not a parallel agent implementation.

### What we explicitly don't build

- **A separate "subagent runtime"**. The spawner runs subagents through the
  same ADK `Runner` the parent uses, with the parent's plugins attached.
  Anything else is wasted complexity.
- **A dynamic version of `.sub_agent()`**. `.sub_agent()` is for structural
  handoff. Making it dynamic would muddy the semantic difference.
- **Subagent-scoped tool registries**. The spec's `tools` field just lists
  tool names from the parent registry plus any new ones added via the spec.
  No separate plugin system for subagents.

## Shared design rules

These apply to every mechanism in the plan. They are the reason this works at
100x speed: once the rules are internalized, each new package is a crank turn.

### Rule 1 — Session-scoped dispatch goes through ADK plugins

Every mechanism whose decisions need to apply to the whole invocation tree
(subagents included) installs as an ADK `BasePlugin`. Not as agent-level
callbacks. Not as tool wrappers. Not as tree walkers. The plugin manager is
already session-scoped and subagent-inherited — we use it.

### Rule 2 — Decisions are structured, not boolean

Every decision layer has its own frozen `Decision` dataclass with named
constructors. Compare to the old `PermissionPolicy.check()` which returned
a bare enum. Structured decisions let us fold multiple results
(allow / deny / modify / replace / inject / ask) into a single dispatch
without if-else pyramids.

### Rule 3 — One source of truth per concept

Usage is tracked once, in one tracker, in one session-scoped plugin. Budget
is counted once. Permissions have exactly one policy object. The old
divergence between `UsageTracker` and `M.cost()` is the anti-pattern we're
fixing — don't recreate it in any new module.

### Rule 4 — Policies are declarative, runtime is composable

The `HookRegistry` is a data structure; the `HookPlugin` is the runtime that
consumes it. Same pattern everywhere: `PermissionPolicy` + `PermissionPlugin`,
`BudgetPolicy` + `BudgetPlugin`, etc. Users compose policies without touching
the plugin layer; harness builders install plugins without touching policies.

### Rule 5 — Backends are pluggable, defaults are local

Anything touching the outside world (filesystem, shell, storage, remote
workspace) goes through a backend protocol. Local is the default. Remote is
opt-in via a constructor argument. This is how a harness ends up running on
Modal / Daytona / Docker without a rewrite.

### Rule 6 — No back-compat shims

User said no backwards compatibility. Old names are deleted outright. This
keeps the surface clean and avoids the "legacy module that everyone imports
from" anti-pattern.

### Rule 7 — Each package is importable standalone

`adk_fluent._permissions` does not depend on `adk_fluent._harness`. It may
depend on `adk_fluent._hooks` (decision protocol) and on core ADK
(`google.adk.plugins.base_plugin`). The harness namespace re-exports, it
does not own. This makes each package individually testable, portable to
TypeScript, and easy to reason about.

## Execution sequence

Commit after each numbered phase. Each phase ends with green tests.

1. **Hooks polish** — `docs/user-guide/hooks.md` + dedicated test module.
2. **_permissions** — foundation + plugin + H surface + docs + tests.
3. **_fs** — backend protocol + local backend + memory backend + sandbox
   decorator + workspace tool retrofit + docs + tests.
4. **_subagents** — spec + spawner + task tool + docs + tests.
5. **_budget** — tracker + policy + plugin + docs + tests.
6. **_compression** — strategy + plan + plugin firing `pre_compact` + docs + tests.
7. **_usage** — unified tracker + plugin + M.cost() retirement + docs + tests.
8. **_session** — store protocol + in-memory + fork / replay API + docs + tests.
9. **_plan_mode** — plan-mode permission policy + plan-mode tool filter + docs + tests.
10. **TypeScript port** — mirror each package under `ts/src/<name>/` and
    re-export through the existing TS `H` namespace.

## Integration points

Every new mechanism integrates at exactly these seams:

- **H namespace** (`adk_fluent._harness._namespace`) — one or two factory
  methods per mechanism, plus helper shortcuts (e.g. `H.permission_decision`,
  `H.budget_threshold`).
- **`.harness()` method** on the agent builder
  (`adk_fluent/agent.py`) — accepts the new policy/registry object and
  installs the plugin automatically.
- **Top-level `__init__.py` + `__init__.pyi`** — re-export the public types.
- **Docs** — `docs/user-guide/<mechanism>.md` plus a link in
  `docs/user-guide/harness.md`.

Nothing else should need to change. If a mechanism starts touching the agent
builder internals or the flow-control primitives, stop and reconsider — it
probably wants to be expressed as a plugin instead.

## What this plan deliberately skips

- Full rewrite of existing harness tool factories (`make_read_file`, etc.)
  until `_fs` lands. They keep working on local disk.
- Merging `_harness` into the new packages. `_harness` remains the
  user-facing namespace home for `H`, but the *implementations* of each
  mechanism migrate out.
- Deprecation machinery. There is none. Old names that move get deleted.
- Public API stability. adk-fluent pre-1.0; we're doing the clean rewrite
  before we lock the surface.

## Success criteria

At the end of this campaign:

1. Every capability from the Claude Agent SDK overview and the Deep Agents
   SDK overview that is not out-of-scope for ADK has a first-class atomic
   primitive in adk-fluent.
2. The cookbook `79_coding_agent_harness.py` compiles and runs against the
   new mechanisms with fewer lines than before, not more.
3. TypeScript mirrors the Python surface method-for-method.
4. Every mechanism has a user-guide chapter under `docs/user-guide/`.
5. The existing test suite still passes and each new package has its own
   dedicated test module.
