# adk-fluent-ts

TypeScript fluent builder API for Google's [Agent Development Kit (ADK)](https://github.com/google/adk). Mirrors the Python [`adk-fluent`](https://pypi.org/project/adk-fluent/) API surface with TypeScript idioms — immutable clones, method-chained operators, and camelCase.

Every `.build()` returns a real [`@google/adk`](https://www.npmjs.com/package/@google/adk) object, so anything built with `adk-fluent-ts` is fully compatible with ADK's runtime, deployment, and tooling.

<!-- Package -->
<p>
  <a href="https://www.npmjs.com/package/adk-fluent-ts"><img alt="npm" src="https://img.shields.io/npm/v/adk-fluent-ts?logo=npm&logoColor=white&label=npm&color=CB3837"></a>
  <a href="https://www.npmjs.com/package/adk-fluent-ts"><img alt="npm downloads" src="https://img.shields.io/npm/dm/adk-fluent-ts?logo=npm&logoColor=white&label=downloads%20/month"></a>
  <a href="https://www.npmjs.com/package/adk-fluent-ts"><img alt="npm total downloads" src="https://img.shields.io/npm/dt/adk-fluent-ts?logo=npm&logoColor=white&label=downloads"></a>
  <a href="https://www.npmjs.com/package/adk-fluent-ts"><img alt="Node" src="https://img.shields.io/node/v/adk-fluent-ts?logo=node.js&logoColor=white&label=Node"></a>
  <a href="https://www.typescriptlang.org/"><img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-5.7-3178C6?logo=typescript&logoColor=white"></a>
  <a href="https://github.com/vamsiramakrishnan/adk-fluent/blob/master/LICENSE"><img alt="License" src="https://img.shields.io/npm/l/adk-fluent-ts?color=informational"></a>
</p>

<!-- Bundle & types -->
<p>
  <a href="https://bundlephobia.com/package/adk-fluent-ts"><img alt="Bundle size (minzip)" src="https://img.shields.io/bundlephobia/minzip/adk-fluent-ts?label=minzip&logo=webpack&logoColor=white"></a>
  <a href="https://bundlephobia.com/package/adk-fluent-ts"><img alt="Bundle size (min)" src="https://img.shields.io/bundlephobia/min/adk-fluent-ts?label=minified&logo=webpack&logoColor=white"></a>
  <a href="https://packagephobia.com/result?p=adk-fluent-ts"><img alt="Install size" src="https://badgen.net/packagephobia/install/adk-fluent-ts"></a>
  <a href="https://www.npmjs.com/package/adk-fluent-ts"><img alt="Tree-shakeable" src="https://badgen.net/bundlephobia/tree-shaking/adk-fluent-ts"></a>
  <a href="https://www.npmjs.com/package/adk-fluent-ts"><img alt="TS types" src="https://img.shields.io/npm/types/adk-fluent-ts?logo=typescript&logoColor=white"></a>
  <a href="https://arethetypeswrong.github.io/?p=adk-fluent-ts"><img alt="Are the types wrong?" src="https://img.shields.io/badge/attw-pass-2EA043?logo=typescript&logoColor=white"></a>
</p>

<!-- Engineering & ecosystem -->
<p>
  <a href="https://github.com/vamsiramakrishnan/adk-fluent/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/vamsiramakrishnan/adk-fluent/ci.yml?branch=master&logo=github&label=CI"></a>
  <a href="https://vitest.dev"><img alt="Tested with Vitest" src="https://img.shields.io/badge/tested_with-vitest-6E9F18?logo=vitest&logoColor=white"></a>
  <a href="https://prettier.io"><img alt="Prettier" src="https://img.shields.io/badge/code_style-prettier-F7B93E?logo=prettier&logoColor=black"></a>
  <a href="https://eslint.org"><img alt="ESLint" src="https://img.shields.io/badge/lint-eslint-4B32C3?logo=eslint&logoColor=white"></a>
  <a href="https://www.npmjs.com/package/@google/adk"><img alt="peer: @google/adk" src="https://img.shields.io/badge/peer-%40google%2Fadk%20%E2%89%A50.6-4285F4?logo=google&logoColor=white"></a>
  <a href="https://vamsiramakrishnan.github.io/adk-fluent/"><img alt="Docs" src="https://img.shields.io/badge/docs-latest-E65100?logo=readthedocs&logoColor=white"></a>
</p>

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
  .step(
    new Agent("searcher", "gemini-2.5-flash").instruct(
      "Search for information.",
    ),
  )
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

| Python       | TypeScript                    | Returns    |
| ------------ | ----------------------------- | ---------- |
| `a >> b`     | `a.then(b)`                   | `Pipeline` |
| `a \| b`     | `a.parallel(b)`               | `FanOut`   |
| `a * 3`      | `a.times(3)`                  | `Loop`     |
| `a * until`  | `a.timesUntil(pred, { max })` | `Loop`     |
| `a // b`     | `a.fallback(b)`               | `Fallback` |
| `a @ Schema` | `a.outputAs(Schema)`          | `Agent`    |

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
import {
  reviewLoop,
  mapReduce,
  cascade,
  chain,
  conditional,
} from "adk-fluent-ts";
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

## Harness (H Namespace)

The `H` namespace provides a Claude-Code-style coding agent harness — hooks, permissions, plan mode, session tape, budget tracking, and filesystem abstraction:

```ts
import { Agent, H } from "adk-fluent-ts";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";

const workspace = mkdtempSync(`${tmpdir()}/my-agent-`);
const harness = H.codingAgent(workspace, {
  allowMutations: true,
  allowNetwork: false,
});

const coder = new Agent("coder", "gemini-2.5-pro")
  .instruct("You are a senior engineer. Use tools to ship.")
  .tools(harness.tools)
  .build();
```

Nine sub-packages: hooks, permissions, planMode, session, subagents, usage, budget, compression, fs. See [cookbook 74](examples/cookbook/74_harness_and_skills.ts) and [75](examples/cookbook/75_coding_agent_harness.ts) for comprehensive examples.

## Examples

75 runnable recipes live in [`ts/examples/cookbook/`](https://github.com/vamsiramakrishnan/adk-fluent/tree/main/ts/examples/cookbook). See the full [Cookbook INDEX](examples/cookbook/INDEX.md). Highlights by category:

**Basics:** [01 Simple Agent](examples/cookbook/01_simple_agent.ts) | [02 Tools](examples/cookbook/02_agent_with_tools.ts) | [03 Callbacks](examples/cookbook/03_callbacks.ts) | [11 Typed Output](examples/cookbook/11_typed_output.ts)

**Workflows:** [04 Pipeline](examples/cookbook/04_sequential_pipeline.ts) | [05 FanOut](examples/cookbook/05_parallel_fanout.ts) | [06 Loop](examples/cookbook/06_loop_agent.ts) | [08 Operators](examples/cookbook/08_operator_composition.ts)

**Routing:** [09 Route](examples/cookbook/09_route_branching.ts) | [10 Fallback](examples/cookbook/10_fallback_operator.ts) | [32 Capture & Route](examples/cookbook/32_capture_and_route.ts) | [45 Support Triage](examples/cookbook/45_customer_support_triage.ts)

**Namespaces:** [34 M Module](examples/cookbook/34_m_module_composition.ts) | [35 T Module](examples/cookbook/35_t_module_tools.ts) | [41 G Module](examples/cookbook/41_g_module_guards.ts) | [65 Builtin Middleware](examples/cookbook/65_builtin_middleware.ts)

**A2UI:** [58 UI Basics](examples/cookbook/58_ui_basics.ts) | [68 A2UI Basics](examples/cookbook/68_a2ui_basics.ts) | [71 LLM-Guided](examples/cookbook/71_a2ui_llm_guided.ts) | [73 Dynamic](examples/cookbook/73_a2ui_dynamic.ts)

**Harness:** [23 Coding Harness](examples/cookbook/23_coding_harness.ts) | [74 Harness & Skills](examples/cookbook/74_harness_and_skills.ts) | [75 Full Harness](examples/cookbook/75_coding_agent_harness.ts)

**Patterns:** [18 Review Loop](examples/cookbook/18_review_loop_pattern.ts) | [19 Map-Reduce](examples/cookbook/19_map_reduce.ts) | [25 Deep Research](examples/cookbook/25_deep_research_capstone.ts) | [47 Full Algebra](examples/cookbook/47_full_algebra.ts)

Clone the repo and run any example with `npx tsx ts/examples/cookbook/01_simple_agent.ts`.

## Visual Cookbook Runner

Test any TS cookbook agent interactively with the visual runner:

```bash
# Configure credentials
cp ts/visual/.env.example ts/visual/.env
# Edit with your API key

# Launch (default port 8099, or specify your own)
just visual-ts
just visual-ts 3000
```

The shared SPA auto-discovers all 75 TS cookbooks, lets you chat with any agent, and renders A2UI surfaces live. A **TypeScript** badge distinguishes it from the Python runner (`just visual-py`). See [`ts/visual/README.md`](visual/README.md) for details.

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
