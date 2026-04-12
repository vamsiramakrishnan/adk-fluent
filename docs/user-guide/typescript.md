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

The Python API reference under [`generated/api/`](../generated/api/index.md) is auto-generated from Python introspection. For a symbol-level TypeScript reference, build the typedoc output from inside the `ts/` package:

```bash
cd ts
npm run docs     # writes HTML into ts/docs/api/
```

`typedoc` reads the TypeScript source directly and produces a fully-linked reference for all exported builders, namespaces, and types. We plan to stitch this into the Sphinx site once the TS package surface stabilizes; until then, treat `ts/docs/api/` as the authoritative symbol reference and the Sphinx site as the authoritative conceptual guide.

The shared `CLAUDE.md` files are also useful as a flat API reference:

- [`ts/CLAUDE.md`](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/ts/CLAUDE.md) — TypeScript LLM context, operator mapping, namespace-level API summary.
- [`CLAUDE.md`](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/CLAUDE.md) — top-level shared API reference, regenerated from `shared/manifest.json`.

## Feature parity

Both packages are regenerated from the same manifest, so builder coverage is identical by construction. Namespace coverage is close to parity but evolving — if you hit a feature that exists in Python but not yet in TypeScript, open an issue. Known areas where the TypeScript package is still catching up:

- The A2A server (`A2AServer` + middleware) is usable but less battle-tested than the Python implementation.
- The evaluation (`E`) namespace does not yet include a TS-native LLM judge — use `E.case` and `E.criterion` with custom predicates.
- Some cookbook recipes (70+, A2UI-heavy) do not yet have TypeScript equivalents.

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
