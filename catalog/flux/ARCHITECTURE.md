# flux — Architecture (Phase 1)

> **Status:** Phase-1 contract. Everything in this document is what W1–W5 will
> build. Anything not in this document is out of scope for 0.16.0.

flux is fluent's reference catalog for A2UI. It sits on top of the basic-catalog
(`a2ui/basic@0.10`) and adds:

1. A token system authors can target without knowing hex values.
2. A DSL (`.spec.ts`) that is the single source of truth for every component.
3. A codegen pipeline that turns specs into JSON Schema, Python helpers, TS
   helpers, React components, docs, and visual-runner goldens.
4. A React renderer wired into `shared/visual/` so every component has a
   pixel-perfect preview and screenshot diff baseline.
5. First-class fluent integration: `UI.theme("flux-dark")`, `with_catalog("flux")`,
   `T.a2ui(catalog="flux")`, component factories that type-check.

This document is the north star. If reality and this doc disagree, change this
doc first, then the code.

---

## 1. Goals

- **One source of truth.** Each component is defined exactly once, in a
  `.spec.ts` file. Everything else is generated.
- **Token-first.** Specs reference tokens (`$color.primary.solid`), never raw
  hex. Themes are swappable at runtime.
- **Fluent ergonomics.** An author writes `UI.button("Save", tone="primary")`
  in Python and gets an A2UI `FluxButton` with the right props, validated
  against the same schema the renderer consumes.
- **Basic-catalog fallback.** Every flux component declares a degradation
  path. Older renderers that only speak basic-catalog still render *something*
  useful.
- **LLM-first.** Every spec ships description, examples, anti-patterns, and
  budget hints consumed by `T.search`, `G.a2ui`, and prompt injection.
- **Reference, not framework.** flux is the *example* catalog. Anyone can
  fork it or author their own against the same contracts.

## 2. Non-goals (Phase 1)

- No runtime theme editor.
- No custom theming DSL for end-users (only fluent authors write tokens).
- No non-React renderer (SSR/React-DOM only). Native and Preact come later.
- No A11y audit automation beyond a11y-schema assertions.
- No animation system beyond CSS transitions on tokens.
- No visual editor / drag-drop surface builder.

## 3. Layered architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│ L6  Fluent API surface         UI.button(...), UI.theme("flux")      │  (Python + TS parity)
├──────────────────────────────────────────────────────────────────────┤
│ L5  Renderer                   React components in ts/src/flux/      │  (pixel output)
├──────────────────────────────────────────────────────────────────────┤
│ L4  Catalog JSON               catalog/flux/catalog.json             │  (emit artifact)
├──────────────────────────────────────────────────────────────────────┤
│ L3  Authoring DSL              catalog/flux/specs/*.spec.ts          │  (source of truth)
├──────────────────────────────────────────────────────────────────────┤
│ L2  Token packs                catalog/flux/tokens/*.json            │  (runtime theme)
├──────────────────────────────────────────────────────────────────────┤
│ L1  Contracts (schemas)        catalog/flux/schema/*.schema.json     │  (validation)
├──────────────────────────────────────────────────────────────────────┤
│ L0  A2UI basic@0.10            specification/components/...          │  (underlying protocol)
└──────────────────────────────────────────────────────────────────────┘
```

**Boundary rules.**

| Layer | May read | May write |
|-------|----------|-----------|
| L6    | L4 (catalog.json), L5 (types) | never writes other layers |
| L5    | L4 (catalog.json), L2 (tokens) | never writes other layers |
| L4    | L3, L2, L1                    | generated only |
| L3    | L2 token paths                 | authored |
| L2    | L1 schema                      | authored |
| L1    | none                           | authored |

Violating a boundary means a build-time error.

## 4. Token system

### 4.1 Scales

| Family       | Keyset                                                            |
|--------------|-------------------------------------------------------------------|
| color (raw)  | `color.<family>.1..12` for neutral / brand / success / warning / danger / info |
| color (alias)| `color.bg.{canvas,subtle,surface}`, `color.border.{default,focus,danger}`, `color.text.{primary,muted,onBrand,danger,link}`, `color.primary.{solid,solidHover,subtle,subtleHover}` |
| space        | 0, 0_5, 1, 1_5, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24 (4-px grid + half steps) |
| radius       | none, xs, sm, md, lg, xl, 2xl, full                               |
| shadow       | none, sm, md, lg, xl, focus                                       |
| motion       | `motion.duration.{fast,base,slow}`, `motion.easing.{standard,emphasized,decelerate}` |
| typography   | `typography.family.{sans,mono}`, `typography.size.{xs,sm,md,lg,xl,2xl,3xl,4xl,5xl}`, `typography.weight.{regular,medium,semibold,bold}`, `typography.lineHeight.{tight,normal,relaxed}` |
| z            | base, dropdown, sticky, overlay, modal, toast                     |

Alias tokens are the preferred author surface; raw `1..12` scales exist so
components with unique chromatic needs can still participate in theming
without inventing new semantic roles.

### 4.2 Dark-mode story

Two packs ship out of the box: `flux-light` and `flux-dark`. Both expose the
same keyset — values differ, keys do not. The renderer picks one via
`UI.theme(name)` (builder API) or a data attribute on the surface root.

Adding a new pack is *authoring only*: drop a JSON file in `tokens/`, add it
to `catalog.json#tokens`, done. No code changes required.

### 4.3 Token reference resolution

A spec value like `"$color.primary.solid"` is looked up, at build time, against
the **union** of keys in every declared pack. Missing in any pack = build
failure. Raw literals (`"0px"`, numbers, `"transparent"`) pass through.

At runtime, tokens resolve to CSS custom properties:

```
$color.primary.solid   →   var(--flux-color-primary-solid)
$space.4               →   var(--flux-space-4)
```

The renderer emits one `<style>` block per theme at surface root.

## 5. Catalog JSON format

Emitted to `catalog/flux/catalog.json`; validated against
`schema/catalog.schema.json`. Shape:

```jsonc
{
  "catalogId": "flux/components@1",
  "version":   "1.0.0",
  "extends":   ["a2ui/basic@0.10"],
  "tokens": {
    "flux-light": "./tokens/flux-light.json",
    "flux-dark":  "./tokens/flux-dark.json"
  },
  "components": {
    "FluxButton":  { /* component.schema.json shape */ },
    "FluxCard":    { ... }
  },
  "fallbacks": {
    "FluxButton":  { "component": "Button",  "map": { "label": "child" } },
    "FluxMarkdown":{ "component": "Text",    "map": { "source": "text" } }
  }
}
```

The `fallbacks` map mirrors per-component `renderer.fallback` for renderers
that only speak basic-catalog — it lets a renderer switch on a single table
rather than crawling every component block.

## 6. Authoring DSL

See `dsl/README.md` for the 5-minute tour and `specs/Button.spec.ts` for the
reference. Summary:

- One file per component. Default export is `defineComponent({...})`.
- `name` must start with `Flux`.
- `extends` must be one of the 18 basic components (determines fallback shape).
- `schema` is Zod; emitted as JSON Schema into `catalog.json`.
- `variants` follows Chakra / Stitches shape: `{ dim: { variantName: StyleObject } }`.
- `compoundVariants` apply styles when multiple dims match.
- `slots` are named insertion points typed by child component kind.
- `accessibility.label` is `"required"` for interactive extends (enforced at
  `defineComponent` call time — fails at `tsc`).
- `llm` metadata is mandatory (non-empty `examples`, explicit `budget`).
- `renderer.fallback` is mandatory.

## 7. Codegen pipeline

Implemented under `shared/scripts/flux/`:

```
flux build
  ├── 1. load   → read every specs/*.spec.ts via ts-node in-process
  ├── 2. check  → validate each spec's token refs against pack union
  ├── 3. emit   → catalog.json (+ catalog.schema.json re-validation)
  ├── 4. py     → python/src/adk_fluent/_flux_gen.py (factories + types)
  ├── 5. ts     → ts/src/flux/index.ts (factories + types)
  ├── 6. react  → ts/src/flux/renderer/*.tsx scaffolds (idempotent, no clobber)
  ├── 7. docs   → docs/flux/components/*.md (one page per component)
  └── 8. gold   → shared/visual/goldens/flux/*.png via visual runner
```

Each stage is a pure function of its inputs — re-running with no spec change
is a no-op. The `react` stage writes *scaffolds only*: a `// flux:scaffold`
marker tells the generator to leave hand-written renderers alone.

`just flux` runs 1..7. `just flux-check` runs 1..3 and asserts no drift in
emitted artifacts — this is what CI gates on.

## 8. Rendering contract

```ts
interface FluxNode {
  component: string;          // "FluxButton"
  id:        string;
  [prop: string]: unknown;    // variant dims, slots, schema-validated props
}

interface FluxRenderContext {
  theme:      TokenPack;       // loaded JSON
  catalog:    CatalogJson;     // loaded JSON
  renderers:  Record<string, FluxRenderer>;
  fallback:   (node: FluxNode) => JSX.Element;   // basic-catalog degrade path
}

interface FluxRenderer {
  (node: FluxNode, ctx: FluxRenderContext): JSX.Element;
}
```

Every `FluxX.tsx` exports a default renderer function with that signature.
Unknown `component` kinds fall through to `ctx.fallback(node)`.

## 9. Fluent integration

**Python (`adk_fluent/_ui.py`):**

```python
UI.theme("flux-dark")                  # sets surface theme attribute
UI.button("Save", tone="primary")      # emits FluxButton node
UI.with_catalog("flux")                # switches factory overloads
```

**TypeScript (`ts/src/namespaces/ui.ts`):**

Typed overloads per component, generated from `.spec.ts` schemas; kept in
sync by `just flux`.

**T.a2ui(catalog=):** Accepts `"basic"` (default) or `"flux"`. When `flux`,
the toolset exposes flux factories + anti-pattern validators to the LLM.

**v0.15.0 wedge preservation:** `.ui(spec, *, llm_guided=, validate=, log=)`
keeps exactly the shape shipped in 0.15.0 — flux is additive only.

## 10. Malleability levers

From least to most invasive, the override surfaces are:

1. **theme** — ship a new token pack.
2. **variant** — add a variant value in a spec.
3. **slot** — provide a different child by id.
4. **component override** — register a renderer in `ctx.renderers` before build.
5. **`extends`** — fork one component, keep the rest.
6. **full fork** — clone `catalog/flux/` to `catalog/mine/`, edit freely; all
   code paths are catalog-id-addressed.

None of these require touching fluent internals.

## 11. LLM-first metadata

Every component ships:

- `llm.description` — one paragraph, agent-audience.
- `llm.tags` — free-form, used by `T.search`.
- `llm.examples` — ≥1 realistic use. Used by `G.a2ui` as positive anchors.
- `llm.antiPatterns` — common misuses with reasons. Used by `G.a2ui` to reject.
- `llm.budget` — `{children, siblings, depth?}`. Prevents runaway trees.

The toolset sends these to the model as tool descriptions + JSON Schema
`description` fields. No prompt hand-crafting required.

## 12. Versioning & federation

Phase 1 minimum: `catalogId` is `<author>/<name>@<major>`. Breaking changes
bump major. `extends` is an array because catalogs may extend multiple
upstream catalogs in the future — Phase 1 only uses one entry.

Federation (hosting multiple catalogs in one surface) is out of scope for
0.16.0 but the JSON format is forward-compatible: the renderer dispatches on
fully-qualified `component` name (`flux/components@1:FluxButton`) when
ambiguity arises; Phase 1 accepts short names.

## 13. Phase-1 component list

Ten components chosen because they (a) cover the 80% of agent surfaces and
(b) exercise every DSL feature at least once.

| Component     | Extends     | Why                                    |
|---------------|-------------|----------------------------------------|
| FluxButton    | Button      | Reference — tone × size × emphasis     |
| FluxTextField | TextField   | Accessibility required; validation     |
| FluxLink      | Link        | Destination vs. action distinction     |
| FluxBanner    | Row         | Tone-driven layout; dismissible slot   |
| FluxCard      | Column      | Header/body/footer slot composition    |
| FluxStack     | Column/Row  | Spacing tokens; direction variant      |
| FluxBadge     | Text        | DSL minimum example                    |
| FluxProgress  | Slider      | Determinate vs. indeterminate          |
| FluxSkeleton  | Text        | Motion tokens; shimmer animation       |
| FluxMarkdown  | Text        | Renderer escape hatch; degrades to Text|

Rejected for Phase 1: FluxModal (focus trap is its own workstream),
FluxTable (DataGrid semantics), FluxTabs (ARIA roving tabindex).

## 14. Out of scope (explicit)

1. Theme editor UI.
2. Runtime token mutation API.
3. Non-React renderers.
4. Animation beyond CSS transitions.
5. Focus-trap / portal / modal infra.
6. Data-grid / virtualized list.
7. Tabs / accordion / disclosure widgets.
8. Visual builder / drag-drop authoring.
9. i18n message format (tokens stay keys; content stays in props).
10. Catalog federation beyond single-parent `extends`.

## 15. Workstream breakdown

See `WORKSTREAMS.md` for W1–W5 briefs with Owner contract / Inputs / Outputs
/ Dependencies / Definition of Done / Test command.
