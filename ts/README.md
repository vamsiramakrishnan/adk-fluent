# adk-fluent-ts

TypeScript fluent builder API for Google's [Agent Development Kit (ADK)](https://github.com/google/adk). Mirrors the Python [`adk-fluent`](https://pypi.org/project/adk-fluent/) API surface with TypeScript idioms — immutable clones, method-chained operators, and camelCase.

> **Monorepo:** This is the TypeScript package in the [`adk-fluent` monorepo](../README.md). The Python package (the current reference implementation) lives in [`python/`](../python/). Shared manifests, seeds, and code generators live in [`shared/`](../shared/). Both packages are regenerated from the same ADK scan.

## Status

Beta. The TypeScript port tracks the Python API surface feature-by-feature and is regenerated from `shared/manifest.json` via `just ts-generate`. The package is not yet published to npm — consume it from the monorepo during beta.

## Install

```bash
# From inside the monorepo
cd ts
npm install
npm run build
```

`adk-fluent-ts` peer-depends on [`@google/adk`](https://www.npmjs.com/package/@google/adk) (the JavaScript port of Google ADK). Install it alongside `adk-fluent-ts` in your consumer project.

## Quick Start

```ts
import { Agent } from "adk-fluent-ts";

const agent = new Agent("helper", "gemini-2.5-flash")
  .instruct("You are a helpful assistant.")
  .build();
```

Every `.build()` returns a real `@google/adk` object — fully compatible with ADK's runtime, deployment, and tooling.

### Pipeline, FanOut, Loop

```ts
import { Agent, Pipeline, FanOut, Loop } from "adk-fluent-ts";

// Sequential
const pipeline = new Pipeline("research")
  .step(new Agent("searcher", "gemini-2.5-flash").instruct("Search for information."))
  .step(new Agent("writer", "gemini-2.5-flash").instruct("Write a summary."))
  .build();

// Parallel
const fanout = new FanOut("parallel_research")
  .branch(new Agent("web", "gemini-2.5-flash").instruct("Search the web."))
  .branch(new Agent("papers", "gemini-2.5-flash").instruct("Search papers."))
  .build();

// Iterative refinement
const loop = new Loop("refine")
  .step(new Agent("writer", "gemini-2.5-flash").instruct("Write draft."))
  .step(new Agent("critic", "gemini-2.5-flash").instruct("Critique."))
  .maxIterations(3)
  .build();
```

## Operators → Method Chains

JavaScript has no operator overloading, so `adk-fluent-ts` uses method calls. The mapping from the Python operator algebra is:

| Python      | TypeScript                            | Returns    |
| ----------- | ------------------------------------- | ---------- |
| `a >> b`    | `a.then(b)`                           | `Pipeline` |
| `a \| b`    | `a.parallel(b)`                       | `FanOut`   |
| `a * 3`    | `a.times(3)`                          | `Loop`     |
| `a * until` | `a.timesUntil(pred, { max })`         | `Loop`     |
| `a // b`    | `a.fallback(b)`                       | `Fallback` |
| `a @ Schema`| `a.outputAs(Schema)`                  | `Agent`    |

Sub-builders passed into workflow builders are auto-built — do **not** call `.build()` on individual steps.

```ts
import { Agent } from "adk-fluent-ts";

const writer = new Agent("writer", "gemini-2.5-flash")
  .instruct("Write a draft about {topic}.")
  .writes("draft");

const reviewer = new Agent("reviewer", "gemini-2.5-flash")
  .instruct("Review the draft: {draft}")
  .writes("feedback");

// Same thing, two styles:
const pipeline1 = new Pipeline("flow").step(writer).step(reviewer).build();
const pipeline2 = writer.then(reviewer).build();
```

## Namespaces

All nine Python namespaces are available:

```ts
import { S, C, P, T, G, M, A, E, UI } from "adk-fluent-ts";
import { tap, expect, gate, race, dispatch, join, Route } from "adk-fluent-ts";
import { reviewLoop, mapReduce, cascade, chain, conditional } from "adk-fluent-ts";
import { RemoteAgent, A2AServer, AgentRegistry } from "adk-fluent-ts";
```

| Namespace | What it does                                              |
| --------- | --------------------------------------------------------- |
| `S`       | State transforms (`S.pick`, `S.rename`, `S.compute`, ...) |
| `C`       | Context engineering (`C.window`, `C.fromState`, ...)      |
| `P`       | Prompt composition (`P.role`, `P.task`, ...)              |
| `T`       | Tool composition (`T.fn`, `T.googleSearch`, ...)          |
| `G`       | Output guards (`G.pii`, `G.length`, `G.schema`, ...)      |
| `M`       | Middleware (`M.retry`, `M.cost`, `M.cache`, ...)          |
| `A`       | Artifacts (`A.publish`, `A.snapshot`, ...)                |
| `E`       | Evaluation (`E.case`, `E.criterion`, `E.persona`, ...)    |
| `UI`      | A2UI — declarative agent UI composition                   |
| `H`       | Harness — build-your-own coding agent runtime             |

See [`CLAUDE.md`](CLAUDE.md) for the TypeScript-specific LLM context (operator mapping, namespace reference) and the [root `CLAUDE.md`](../CLAUDE.md) for the shared API reference — both are regenerated from the same manifest as the code.

## Examples

Runnable recipes live in [`examples/cookbook/`](examples/cookbook). Highlights:

- [`01_simple_agent.ts`](examples/cookbook/01_simple_agent.ts) — minimal agent
- [`04_sequential_pipeline.ts`](examples/cookbook/04_sequential_pipeline.ts) — `Pipeline` + `.then()`
- [`05_parallel_fanout.ts`](examples/cookbook/05_parallel_fanout.ts) — `FanOut` + `.parallel()`
- [`08_operator_composition.ts`](examples/cookbook/08_operator_composition.ts) — method-chain operator algebra
- [`12_guards.ts`](examples/cookbook/12_guards.ts) — `G.pii()`, `G.length()`, `G.schema()`
- [`18_review_loop_pattern.ts`](examples/cookbook/18_review_loop_pattern.ts) — `reviewLoop()` higher-order pattern

Run any example with `npx tsx examples/cookbook/01_simple_agent.ts`.

## Development

From the monorepo root, use the `just` recipes:

```bash
just ts-setup        # npm install inside ts/
just ts-generate     # Regenerate TS builders from shared/manifest.json + seeds
just ts-build        # tsc build
just ts-typecheck    # tsc --noEmit
just ts-lint         # eslint
just ts-test         # vitest run
```

Or work inside `ts/` directly:

```bash
cd ts
npm run build
npm run test
npm run lint
npm run typecheck
npm run docs        # typedoc → docs/api
```

Generated files (`ts/src/builders/*.ts`) are owned by `just ts-generate` and should not be hand-edited — changes there will be overwritten on the next regeneration. Hand-written code lives under `ts/src/core/`, `ts/src/namespaces/`, `ts/src/patterns/`, `ts/src/primitives/`, `ts/src/routing/`, and `ts/src/a2a/`.

## How It Works

`adk-fluent-ts` is **auto-generated** from the installed Google ADK via the shared generator:

```
shared/scripts/scanner.py  ─►  shared/manifest.json
                                       │
                                       ▼
                         shared/scripts/generator.py --target typescript
                                       │
                                       ▼
                               ts/src/builders/*.ts
```

The same manifest drives the Python builders — API parity between languages is enforced by construction.

## Links

- Monorepo README: [`../README.md`](../README.md)
- Python package: [`../python/README.md`](../python/README.md) — reference implementation
- LLM context (shared API reference): [`../CLAUDE.md`](../CLAUDE.md)
- Python docs site (most guides apply to both languages): <https://vamsiramakrishnan.github.io/adk-fluent/>
- Changelog: [`../CHANGELOG.md`](../CHANGELOG.md)

## License

Apache-2.0
