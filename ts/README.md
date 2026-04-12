# adk-fluent-ts

TypeScript fluent builder API for Google's [Agent Development Kit (ADK)](https://github.com/google/adk). Mirrors the Python [`adk-fluent`](https://pypi.org/project/adk-fluent/) API surface with TypeScript idioms — immutable clones, method-chained operators, and camelCase.

Every `.build()` returns a real [`@google/adk`](https://www.npmjs.com/package/@google/adk) object, so anything built with `adk-fluent-ts` is fully compatible with ADK's runtime, deployment, and tooling.

## Status

Beta. The TypeScript port tracks the Python API surface feature-by-feature and is regenerated from a shared manifest via `just ts-generate`. The API surface is stable enough to build real agents, but minor breakages may still land before `1.0`.

## Install

```bash
npm install adk-fluent-ts @google/adk
```

`adk-fluent-ts` declares [`@google/adk`](https://www.npmjs.com/package/@google/adk) as a peer dependency — install it alongside in your consumer project.

## Quick Start

```ts
import { Agent } from "adk-fluent-ts";

const agent = new Agent("helper", "gemini-2.5-flash")
  .instruct("You are a helpful assistant.")
  .build();
```

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

| Python       | TypeScript                     | Returns    |
| ------------ | ------------------------------ | ---------- |
| `a >> b`     | `a.then(b)`                    | `Pipeline` |
| `a \| b`     | `a.parallel(b)`                | `FanOut`   |
| `a * 3`      | `a.times(3)`                   | `Loop`     |
| `a * until`  | `a.timesUntil(pred, { max })`  | `Loop`     |
| `a // b`     | `a.fallback(b)`                | `Fallback` |
| `a @ Schema` | `a.outputAs(Schema)`           | `Agent`    |

Sub-builders passed into workflow builders are auto-built — do **not** call `.build()` on individual steps.

```ts
import { Agent, Pipeline } from "adk-fluent-ts";

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

All nine namespaces from the Python API are available with TypeScript idioms — camelCase method names, method-chained composition (`.pipe()` / `.add()`), and options-object arguments:

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

JavaScript reserved words use a trailing underscore — `S.default_`, `C.default_`, `A.delete_`. See [`CLAUDE.md`](https://github.com/vamsiramakrishnan/adk-fluent/blob/main/ts/CLAUDE.md) for the full TypeScript namespace reference.

## Examples

Runnable recipes live in [`ts/examples/cookbook/`](https://github.com/vamsiramakrishnan/adk-fluent/tree/main/ts/examples/cookbook). Highlights:

- [`01_simple_agent.ts`](https://github.com/vamsiramakrishnan/adk-fluent/blob/main/ts/examples/cookbook/01_simple_agent.ts) — minimal agent
- [`04_sequential_pipeline.ts`](https://github.com/vamsiramakrishnan/adk-fluent/blob/main/ts/examples/cookbook/04_sequential_pipeline.ts) — `Pipeline` + `.then()`
- [`05_parallel_fanout.ts`](https://github.com/vamsiramakrishnan/adk-fluent/blob/main/ts/examples/cookbook/05_parallel_fanout.ts) — `FanOut` + `.parallel()`
- [`08_operator_composition.ts`](https://github.com/vamsiramakrishnan/adk-fluent/blob/main/ts/examples/cookbook/08_operator_composition.ts) — method-chain operator algebra
- [`12_guards.ts`](https://github.com/vamsiramakrishnan/adk-fluent/blob/main/ts/examples/cookbook/12_guards.ts) — `G.pii()`, `G.length()`, `G.schema()`
- [`18_review_loop_pattern.ts`](https://github.com/vamsiramakrishnan/adk-fluent/blob/main/ts/examples/cookbook/18_review_loop_pattern.ts) — `reviewLoop()` higher-order pattern

Clone the repo and run any example with `npx tsx ts/examples/cookbook/01_simple_agent.ts`.

## Documentation

The canonical docs site covers both Python and TypeScript — every guide has synchronized `:::{tab-item} :sync: python` / `:sync: ts` code blocks, so switching language once persists across the whole site.

- **Docs site:** <https://vamsiramakrishnan.github.io/adk-fluent/>
- **Getting started (TS):** <https://vamsiramakrishnan.github.io/adk-fluent/typescript.html>
- **LLM context (camelCase reference):** [`ts/CLAUDE.md`](https://github.com/vamsiramakrishnan/adk-fluent/blob/main/ts/CLAUDE.md)

## How It Works

`adk-fluent-ts` is **auto-generated** from the installed Google ADK via a shared scanner. The same manifest drives the Python builders — API parity between languages is enforced by construction, not by hand.

```
shared/scripts/scanner.py  ─►  shared/manifest.json
                                       │
                                       ▼
                         shared/scripts/generator.py --target typescript
                                       │
                                       ▼
                               ts/src/builders/*.ts
```

## Contributing

Contributions are welcome. The repo is a monorepo with Python (`python/`), TypeScript (`ts/`), and the shared codegen (`shared/`). To hack on the TS package:

```bash
git clone https://github.com/vamsiramakrishnan/adk-fluent
cd adk-fluent/ts
npm install
npm run build
npm test
```

Generated files (`ts/src/builders/*.ts`) are owned by `just ts-generate` and should not be hand-edited. Hand-written code lives under `ts/src/core/`, `ts/src/namespaces/`, `ts/src/patterns/`, `ts/src/primitives/`, `ts/src/routing/`, and `ts/src/a2a/`. See [`CONTRIBUTING.md`](https://github.com/vamsiramakrishnan/adk-fluent/blob/main/CONTRIBUTING.md) for the full workflow.

## Links

- **Repository:** <https://github.com/vamsiramakrishnan/adk-fluent>
- **Docs site:** <https://vamsiramakrishnan.github.io/adk-fluent/>
- **Python package (reference implementation):** [`adk-fluent` on PyPI](https://pypi.org/project/adk-fluent/)
- **Changelog:** <https://github.com/vamsiramakrishnan/adk-fluent/blob/main/CHANGELOG.md>
- **Issues:** <https://github.com/vamsiramakrishnan/adk-fluent/issues>

## License

Apache-2.0
