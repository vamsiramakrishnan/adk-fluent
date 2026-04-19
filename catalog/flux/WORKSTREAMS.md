# flux — Phase-1 Workstreams

Five parallel-ish workstreams. W1 gates everything; W2 depends on W1;
W3/W4/W5 can run concurrently once W2 lands its scaffold stage.

Each brief is the *only* input an implementer agent needs. If something is
missing from the brief, stop and update this file before coding.

---

## W1 — Tokens, Schemas, DSL scaffold

**Owner contract.** Own `catalog/flux/schema/`, `catalog/flux/tokens/`, and
`catalog/flux/dsl/types.ts`. Make these bullet-proof — everything downstream
trusts them.

**Inputs.**
- `ARCHITECTURE.md` §1, §3, §4, §6.
- `specification/a2ui/components.json` (basic-catalog reference).
- Existing files: `schema/tokens.schema.json`, `schema/component.schema.json`,
  `schema/catalog.schema.json`, `tokens/flux-light.json`, `tokens/flux-dark.json`,
  `dsl/types.ts`, `dsl/README.md`, `specs/Button.spec.ts`.

**Outputs.**
1. Token packs validated against `tokens.schema.json` (pytest + vitest).
2. `specs/Button.spec.ts` type-checks against `dsl/types.ts`.
3. Test suite:
   - `tests/flux/test_token_packs.py` — load each JSON, assert schema valid.
   - `tests/flux/test_token_parity.py` — assert `flux-light` and `flux-dark`
     have identical keysets.
   - `ts/tests/flux/dsl.spec.ts` — call `defineComponent` with a malformed
     spec, assert invariants fire.

**Dependencies.** None.

**Definition of Done.**
- `uv run pytest tests/flux/ -v` green.
- `pnpm --filter ts vitest run flux` green.
- `ajv validate -s catalog/flux/schema/tokens.schema.json -d catalog/flux/tokens/flux-*.json` succeeds.
- Adding an unknown key to a token pack fails schema validation with a
  readable error.

**Test command.**
```sh
just flux-check
```

---

## W2 — DSL runtime + codegen pipeline

**Owner contract.** Implement `shared/scripts/flux/build.py` (stages 1..7 in
`ARCHITECTURE.md` §7). The TS-in-Python boundary is `ts-node --transpile-only
--esm <spec>` subprocess that dumps the default export as JSON to stdout.

**Inputs.**
- W1 outputs (frozen schemas + token packs).
- `shared/scripts/generator/` (copy patterns for codegen plumbing).
- `specs/Button.spec.ts` (canary spec — must round-trip through the pipeline).

**Outputs.**
1. `shared/scripts/flux/build.py` with sub-commands:
   `load | check | emit | py | ts | react | docs | all`.
2. `shared/scripts/flux/_loader.ts` — Node-side loader that imports a spec
   file and `JSON.stringify`s it.
3. `shared/scripts/flux/_emit_py.py` — template → `python/src/adk_fluent/_flux_gen.py`.
4. `shared/scripts/flux/_emit_ts.py` — template → `ts/src/flux/index.ts`.
5. `shared/scripts/flux/_emit_react.py` — per-component scaffold writer
   (idempotent: reads existing file, preserves hand-written body if
   `// flux:scaffold-user` marker present).
6. Justfile recipes: `flux`, `flux-check`, `flux-clean`.

**Dependencies.** W1 must be green.

**Definition of Done.**
- `just flux` runs end-to-end on the single-spec tree (Button only).
- Emitted `catalog.json` validates against `catalog.schema.json`.
- Emitted `_flux_gen.py` type-checks under `mypy --strict`.
- Emitted `ts/src/flux/index.ts` type-checks under `tsc --noEmit`.
- `just flux-check` fails loudly when the tree drifts (editing the spec
  without regen).
- Pipeline is idempotent: running twice produces byte-identical output.

**Test command.**
```sh
just flux && just flux-check
```

---

## W3 — Ten component specs

**Owner contract.** Author the nine missing specs. `Button.spec.ts` is the
template. Every spec must pass `just flux-check` individually.

**Inputs.**
- W1 outputs.
- W2 pipeline running on Button.
- `ARCHITECTURE.md` §13 (component list + rationale).

**Outputs.** Nine `.spec.ts` files:

1. `TextField.spec.ts` — `extends: TextField`, variants `size × state`,
   slots `leadingIcon | trailingIcon | helper`, `accessibility.label:
   required`, keyboard `Tab/Enter`, validation anti-patterns.
2. `Link.spec.ts` — `extends: Link`, variants `tone × underline`, slots none,
   `href` *xor* `action` invariant, anti-pattern: empty href.
3. `Banner.spec.ts` — `extends: Row`, variants `tone`, slot `action` (Button),
   slot `dismiss` (Button), budget `{children: 0, siblings: 3}`.
4. `Card.spec.ts` — `extends: Column`, slots `header | body | footer`,
   variants `emphasis (subtle | outline | elevated)`, compoundVariant `outline
   + emphasis=elevated`.
5. `Stack.spec.ts` — `extends: Column`, variants `direction × gap × align`,
   no slots (children pass through), budget `{children: 20, siblings: 12}`.
6. `Badge.spec.ts` — already sketched in `dsl/README.md`; finalize.
7. `Progress.spec.ts` — `extends: Slider`, variants `tone × size`,
   `determinate` boolean, motion tokens for indeterminate shimmer.
8. `Skeleton.spec.ts` — `extends: Text`, variants `shape (text | circle |
   rect) × size`, motion duration/easing tokens wired into `@keyframes shimmer`.
9. `Markdown.spec.ts` — `extends: Text`, schema accepts `source: string`,
   `renderer.fallback.component: Text` with `map.source: text`, anti-pattern:
   raw HTML.

**Dependencies.** W2 pipeline working for Button.

**Definition of Done.**
- All 10 specs in the catalog.
- `just flux` emits 10 blocks in `components` + 10 entries in `fallbacks`.
- Every spec ships ≥2 `examples` and ≥1 `antiPattern`.
- Every spec's token refs resolve in both packs.
- `G.a2ui` validator rejects each anti-pattern with the declared reason.

**Test command.**
```sh
just flux && uv run pytest tests/flux/test_catalog_shape.py -v
```

---

## W4 — Fluent integration (Python + TS parity)

**Owner contract.** Surface flux to users via `UI.*`, `T.a2ui(catalog=)`,
and `with_catalog("flux")`. Maintain 1:1 parity between Python and TS.

**Inputs.**
- W2 generated files (`_flux_gen.py`, `ts/src/flux/index.ts`).
- `python/src/adk_fluent/_ui.py` (existing `UI` namespace).
- `ts/src/namespaces/ui.ts` (existing TS mirror).
- `shared/seeds/seed.toml` (authoritative signature source).

**Outputs.**

Python side:
1. `UI.theme(name: str)` — attaches theme id to current surface builder.
2. `UI.with_catalog(name: str)` — context manager / explicit setter switching
   factory dispatch.
3. `UI.button`, `UI.text_field`, etc. — when `flux` catalog is active,
   emit `FluxX` nodes with kw-only variant dims; otherwise emit basic nodes.
4. `T.a2ui(catalog="flux")` — wires the toolset with flux metadata.

TS side: same shape, same names.

Seed updates:
- `shared/seeds/seed.toml` gains entries for new `UI` methods so
  `just generate` produces matching Python + TS + YAML.
- `shared/seeds/seed.manual.toml` mirrors until fully machine-generated.

**Dependencies.** W2 done; W3 not blocking (empty catalog still works).

**Definition of Done.**
- `uv run pytest tests/ui/test_flux_integration.py -v` green.
- `pnpm --filter ts vitest run namespaces/ui.flux` green.
- `just check-gen` green (no seed<>emit drift).
- `python -c "from adk_fluent import UI; UI.with_catalog('flux'); UI.button('hi', tone='primary')"` runs.

**Test command.**
```sh
just check-gen && uv run pytest tests/ui/ -v && pnpm --filter ts vitest run
```

---

## W5 — React renderer + visual runner

**Owner contract.** Turn catalog.json into pixels. One React file per
component, wired into `shared/visual/` so screenshots exist and regressions
fail CI.

**Inputs.**
- W3 emitted specs.
- W2 scaffold stage (React files exist with TODO bodies).
- `shared/visual/runner/` (existing Playwright baseline infra).

**Outputs.**
1. `ts/src/flux/renderer/FluxButton.tsx` … `FluxMarkdown.tsx` — 10 React
   components, each consuming `FluxRenderContext` from §8 of `ARCHITECTURE.md`.
2. `ts/src/flux/renderer/index.ts` — re-export map consumed by the visual runner.
3. `ts/src/flux/renderer/theme.css.ts` — emits CSS custom properties from
   token pack JSON at bundle time (Vite / esbuild plugin).
4. `shared/visual/fixtures/flux/*.json` — one fixture per component (two
   for Button: primary-solid-md, danger-outline-sm).
5. `shared/visual/goldens/flux/*.png` — Playwright-generated baselines.
6. `shared/visual/specs/flux.spec.ts` — runs every fixture through both
   themes (light + dark) and compares to goldens.

**Dependencies.** W2 scaffold done; W3 specs finalized.

**Definition of Done.**
- `pnpm --filter shared test:visual -- --project=flux` green.
- Both themes render every component without console warnings.
- `FluxMarkdown` fallback (`Text`) tested against a renderer that does NOT
  have flux registered — assert it still produces readable text.
- A11y smoke: `@axe-core/playwright` zero violations on every fixture.

**Test command.**
```sh
just visual-flux
```

---

## Execution order

```
W1 ──▶ W2 ──┬──▶ W3 ──┐
            ├──▶ W4 ──┼──▶ release gate (just all + just flux)
            └──▶ W5 ──┘
```

W3/W4/W5 fan out after W2 lands scaffolds. Release gate is `just all`
succeeding with no diff against HEAD — i.e., regeneration is a fixed point.
