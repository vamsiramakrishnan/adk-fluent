# flux — adk-fluent A2UI catalog + design system

**flux** is adk-fluent's first-party A2UI catalog: a token-driven, component-rich
layer that sits on top of A2UI basic (v0.10) and provides production-grade
primitives without forking the protocol.

## What's in this directory

| Path                                | What it is                                                  |
| ----------------------------------- | ----------------------------------------------------------- |
| `ARCHITECTURE.md`                   | Authoritative design doc (READ THIS FIRST).                 |
| `WORKSTREAMS.md`                    | Hand-off briefs for the 6 implementer agents.               |
| `schema/tokens.schema.json`         | JSON Schema for a flux token pack.                          |
| `schema/component.schema.json`      | JSON Schema for one flux component.                         |
| `schema/catalog.schema.json`        | JSON Schema for the top-level flux catalog file.            |
| `dsl/types.ts`                      | Authoring DSL — what humans write.                          |
| `dsl/README.md`                     | One-page "how to author a component" guide.                 |
| `tokens/flux-light.json`            | Default light-mode token pack.                              |
| `tokens/flux-dark.json`             | Dark-mode counterpart.                                      |
| `specs/Button.spec.ts`              | Reference DSL file. Every other spec follows this template. |

## TL;DR

- A2UI basic ships 18 components. flux layers 10 *richer* primitives on top.
- Authors write one `.spec.ts` file per component in TypeScript.
- A single codegen emits: `catalog.json`, Python factories, TS factories,
  React renderer components, TS types, MDX docs, goldens.
- Every flux component extends A2UI basic via `"extends": "a2ui/basic@0.10"` —
  a basic-catalog renderer sees a semantically-valid fallback.

See `ARCHITECTURE.md` for the full spec.
