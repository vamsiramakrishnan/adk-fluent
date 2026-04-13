# TypeScript (adk-fluent-ts)

:::{note} Python is the reference implementation
These docs are **Python-first**. Conceptual chapters (context engineering, patterns, prompts, guards, evaluation, deployment, architecture) describe the shared model, and almost every code sample is available as a synced **Python / TypeScript** tab. Pick "TypeScript" on any tab and the rest of the site remembers the choice.

This page is the home base for TS developers: install, the operator → method-chain mapping, imports, and where to find TS-specific assets.
:::

## Install

`adk-fluent-ts` lives in [`ts/`](https://github.com/vamsiramakrishnan/adk-fluent/tree/master/ts) in the monorepo. It is not yet published to npm; during beta, consume it from the repo.

```bash
cd ts
npm install
npm run build
```

`adk-fluent-ts` peer-depends on [`@google/adk`](https://www.npmjs.com/package/@google/adk) — the JavaScript port of Google ADK. Install it in your consumer project alongside `adk-fluent-ts`.

## Imports

```ts
import { Agent, Pipeline, FanOut, Loop, Fallback } from "adk-fluent-ts";
import { S, C, P, T, G, M, A, E, UI } from "adk-fluent-ts";
import { tap, expect, gate, race, dispatch, join, Route } from "adk-fluent-ts";
import { reviewLoop, mapReduce, cascade, chain, conditional } from "adk-fluent-ts";
import { RemoteAgent, A2AServer, AgentRegistry } from "adk-fluent-ts";
```

All nine namespaces (`S`, `C`, `P`, `T`, `G`, `M`, `A`, `E`, `UI`) plus the `H` harness namespace are available. The surface is regenerated from the same `shared/manifest.json` that drives the Python package, so parity is enforced at generation time.

## Harness (`H` namespace)

`adk-fluent-ts` ships a full TypeScript port of the `H` harness namespace —
the building blocks for autonomous coding agents. The TS package lives at
[`ts/src/namespaces/harness/`](https://github.com/vamsiramakrishnan/adk-fluent/tree/master/ts/src/namespaces/harness)
and mirrors the nine Python sub-packages with camelCase names:

| Python | TypeScript | Concept |
| ------ | ---------- | ------- |
| `H.workspace("/p")` | `H.workspace("/p")` | Sandboxed workspace tools (read, edit, write, glob, grep, bash, ls) |
| `H.web()` | `H.web()` | URL fetch + web search tools |
| `H.permissions()` / `H.auto_allow(...)` | `H.permissions()` / `H.autoAllow(...)` | 5-mode permission policy |
| `H.plan_mode()` / `H.plan_mode_policy(p)` | `H.planMode()` / `H.planModePolicy(p)` | Plan-then-execute latch with mutating-tool gating |
| `H.hooks("/p")` | `H.hooks("/p")` | 12-event hook registry with shell-command hooks |
| `H.session_store()` / `H.session_plugin()` | `H.sessionStore()` / `H.sessionPlugin()` | JSONL tape + named-branch fork manager |
| `H.subagent_registry()` / `H.task_tool(r, runner)` | `H.subagentRegistry()` / `H.taskTool(r, runner)` | Dynamic specialist dispatch |
| `H.usage()` / `H.usage_plugin(t)` | `H.usage()` / `H.usagePlugin(t)` | Per-agent token + USD cost tracking |
| `H.budget_monitor(n)` / `H.budget_plugin(m)` | `H.budgetMonitor(n)` / `H.budgetPlugin(m)` | Threshold-triggered token budget |
| `H.compressor(threshold=...)` | `H.compressor({ threshold })` | Pre-compact hook integration |
| `H.git(workspace)` | `H.git(workspace)` | Workspace git checkpointer |
| `H.processes(...)` | `H.processes(...)` | Background process lifecycle |
| `H.repl(agent, ...)` | `H.repl(agent, ...)` | Interactive REPL with rendering + compression |

```ts
import { Agent, H } from "adk-fluent-ts";

const agent = new Agent("coder", "gemini-2.5-pro")
  .tools([
    ...H.workspace("/project", { diffMode: true }),
    ...H.web(),
    ...H.gitTools("/project"),
  ])
  .harness({
    permissions: H.autoAllow("read_file", "grep_search").merge(
      H.askBefore("edit_file", "bash"),
    ),
    sandbox: H.workspaceOnly("/project"),
    usage: H.usage(),
  });

const repl = H.repl(agent.build(), {
  compressor: H.compressor({ threshold: 100_000 }),
});
await repl.run();
```

See the [harness guide](harness.md) for the full five-layer architecture.
The sub-package guides ([hooks](hooks.md), [permissions](permissions.md),
[plan-mode](plan-mode.md), [session](session.md), [subagents](subagents.md),
[usage](usage.md), [budget](budget.md), [compression](compression.md)) are
shared between Python and TypeScript — the API shape is parallel, the method
names differ only in case.

## Operators → method chains

JavaScript has no operator overloading, so `adk-fluent-ts` uses method calls. This is the single most important mapping to internalize when reading the rest of these docs:

| Python           | TypeScript                        | Returns    |
| ---------------- | --------------------------------- | ---------- |
| `a >> b`         | `a.then(b)`                       | `Pipeline` |
| `a \| b`         | `a.parallel(b)`                   | `FanOut`   |
| `a * 3`          | `a.times(3)`                      | `Loop`     |
| `a * until(...)` | `a.timesUntil(pred, { max })`     | `Loop`     |
| `a // b`         | `a.fallback(b)`                   | `Fallback` |
| `a @ Schema`     | `a.outputAs(Schema)`              | `Agent`    |
| `S.pick("k")`    | `S.pick("k")`                     | `STransform` |
| `C.window(5)`    | `C.window(5)`                     | `CTransform` |

Sub-builders passed into workflow builders are **auto-built** in both languages — do not call `.build()` on individual steps.

Also:

- TypeScript uses **camelCase** builder methods where Python uses snake_case: `.maxIterations(3)` vs `.max_iterations(3)`, `.beforeModel(fn)` vs `.before_model(fn)`, `.agentTool(agent)` vs `.agent_tool(agent)`.
- `new` is required when constructing builders in TS: `new Agent("name", "gemini-2.5-flash")`.
- Generic type parameters on `.outputAs<Schema>()` replace Python's `@ Schema` decorator-style typing.

## Quick start

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent, Pipeline

pipeline = (
    Pipeline("research")
    .step(Agent("searcher", "gemini-2.5-flash").instruct("Search for information."))
    .step(Agent("writer", "gemini-2.5-flash").instruct("Write a summary."))
    .build()
)
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent, Pipeline } from "adk-fluent-ts";

const pipeline = new Pipeline("research")
  .step(new Agent("searcher", "gemini-2.5-flash").instruct("Search for information."))
  .step(new Agent("writer", "gemini-2.5-flash").instruct("Write a summary."))
  .build();
```
:::
::::

::::{tab-set}
:::{tab-item} Python
:sync: python

```python
from adk_fluent import Agent

pipeline = (
    Agent("web", "gemini-2.5-flash").instruct("Search web.").writes("web_data")
    >> Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}.")
).build()
```
:::
:::{tab-item} TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const pipeline = new Agent("web", "gemini-2.5-flash")
  .instruct("Search web.")
  .writes("web_data")
  .then(
    new Agent("analyst", "gemini-2.5-flash").instruct("Analyze {web_data}."),
  )
  .build();
```
:::
::::

## Running examples

Runnable recipes live in [`ts/examples/cookbook/`](https://github.com/vamsiramakrishnan/adk-fluent/tree/master/ts/examples/cookbook). Highlights:

| File | What it shows |
| ---- | ------------- |
| `01_simple_agent.ts`         | Minimal agent, `.build()` returns a native `@google/adk` LlmAgent |
| `04_sequential_pipeline.ts`  | `Pipeline` + `.then()` — sequential composition |
| `05_parallel_fanout.ts`      | `FanOut` + `.parallel()` — concurrent branches |
| `06_loop_agent.ts`           | `Loop` + `.times()` — bounded iteration |
| `08_operator_composition.ts` | The full method-chain operator algebra on one page |
| `12_guards.ts`               | `G.pii()`, `G.length()`, `G.schema()` — output validation |
| `17_primitives.ts`           | `tap`, `expect`, `gate`, `race`, `dispatch`, `join` |
| `18_review_loop_pattern.ts`  | `reviewLoop()` higher-order pattern |
| `20_cascade_fallback.ts`     | `cascade()` — model fallback chains |

Run any example with:

```bash
cd ts
npx tsx examples/cookbook/01_simple_agent.ts
```

## TypeScript API reference

The Python API reference under [`generated/api/`](../generated/api/index.md) is auto-generated from Python introspection. The TypeScript equivalent is produced by [`typedoc`](https://typedoc.org/) from the TS source and is published alongside this Sphinx site at **[`/ts-api/`](../../ts-api/index.html)** (linked from the top of GH Pages).

```bash
# Local build:
cd ts
npm run docs     # writes HTML into ts/docs/api/

# Or from the repo root — this is what CI runs:
just ts-docs     # regenerates typedoc
just docs-build  # builds Sphinx and copies ts/docs/api/ → docs/_build/html/ts-api/
```

`typedoc` reads the TypeScript source directly and produces a fully-linked reference for all exported builders, namespaces, and types. The GH Pages deploy ships both the Sphinx conceptual guide and the typedoc symbol reference in the same site under `/latest/` and `/v{version}/`.

The shared `CLAUDE.md` files are also useful as a flat API reference:

- [`ts/CLAUDE.md`](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/ts/CLAUDE.md) — TypeScript LLM context, operator mapping, namespace-level API summary.
- [`CLAUDE.md`](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/CLAUDE.md) — top-level shared API reference, regenerated from `shared/manifest.json`.

## Feature parity

Both packages are regenerated from the same manifest, so builder coverage is identical by construction. Namespace coverage is close to parity but evolving — if you hit a feature that exists in Python but not yet in TypeScript, open an issue. Known areas where the TypeScript package is still catching up:

- The A2A server (`A2AServer` + middleware) is usable but less battle-tested than the Python implementation.
- The evaluation (`E`) namespace does not yet include a TS-native LLM judge — use `E.case` and `E.criterion` with custom predicates.
- Some cookbook recipes (70+, A2UI-heavy) do not yet have TypeScript equivalents.

### Documentation coverage

**Runtime and code parity is tight.** Documentation tab coverage is still catching up — most conceptual guides were written Python-first and have not yet been backfilled with a synced TS tab. If a page is missing a `:tab-item: TypeScript` block, mentally translate using:

- **Operators → method chains** (`>>` → `.then()`, `|` → `.parallel()`, `*` → `.times()`, `//` → `.fallback()`, `@` → `.outputAs()`).
- **Builder methods → camelCase** (`.before_model(fn)` → `.beforeModel(fn)`, `.max_iterations(n)` → `.maxIterations(n)`, `.agent_tool(a)` → `.agentTool(a)`).
- **H namespace methods → camelCase** (`H.plan_mode()` → `H.planMode()`, `H.session_store()` → `H.sessionStore()`, `H.subagent_registry()` → `H.subagentRegistry()`).
- **Namespace factories → options objects** (`G.length(max=500)` → `G.length({ max: 500 })`, `H.compressor(threshold=100_000)` → `H.compressor({ threshold: 100_000 })`).
- **Composition operators in namespaces → `.pipe()`** (`G.pii() | G.length()` → `G.pii().pipe(G.length(...))`).

The typedoc reference under [`/ts-api/`](../../ts-api/index.html) is authoritative for the TS symbol-level API; this guide and the sub-package guides ([harness](harness.md), [hooks](hooks.md), [permissions](permissions.md), [plan-mode](plan-mode.md), [session](session.md), [subagents](subagents.md), [usage](usage.md), [budget](budget.md), [compression](compression.md)) are the authoritative conceptual guides shared between both languages.

## Development

From the monorepo root, drive the TS package with the `just ts-*` recipes:

```bash
just ts-setup        # npm install inside ts/
just ts-generate     # Regenerate TS builders from shared/manifest.json + seeds
just ts-build        # tsc build
just ts-typecheck    # tsc --noEmit
just ts-lint         # eslint
just ts-test         # vitest run
just test-all        # Python + TypeScript test suites together
just generate-all    # Regenerate Python and TypeScript builders from one manifest
```

Generated TS files (`ts/src/builders/*.ts`) are owned by `just ts-generate`. Hand-written code lives in `ts/src/core/`, `ts/src/namespaces/`, `ts/src/patterns/`, `ts/src/primitives/`, `ts/src/routing/`, and `ts/src/a2a/`. Formatters and lint only touch hand-written files.

## Where to next

- **New to adk-fluent?** Start with {doc}`../getting-started` — every code sample is available as a Python / TypeScript tab.
- **Want the full operator reference?** Read {doc}`expression-language` with the TypeScript tab active.
- **Building production systems?** Walk {doc}`patterns`, {doc}`context-engineering`, {doc}`guards`, and {doc}`middleware` — all shared conceptually between languages.
- **Deploying an agent?** {doc}`execution-backends` and {doc}`execution` cover the shared execution model. Deployment is Python-first today; the TS equivalent is tracked in [ts/README.md](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/ts/README.md).
