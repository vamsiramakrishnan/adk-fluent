# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`R` namespace — reactors native to the fluent builder** (Python + TypeScript parity). Signals and rules are now first-class builder concerns, matching the weight of `S` / `C` / `M`. The 100x move is a registry-backed facade that turns signals into name-addressed cells and predicates into name-addressed factories, plus `Builder.on(predicate, handler?, opts?)` for declarative rule attachment and `R.compile(builders, {bus})` for tree-walking compilation across `Pipeline` / `FanOut` / `Loop`:

    ```python
    # before — hand-built sequence of four distinct objects
    bus  = EventBus()
    temp = Signal("temp", 72).attach(bus)
    r    = Reactor()
    r.when(temp.rising.where(lambda v: v > 90), handler, priority=10)
    r.start()

    # after — name-addressed, declarative, composable
    temp   = R.signal("temp", 72)
    cooler = (Agent("cooler", "gemini-2.5-flash")
              .instruct("Plan a cool-down.")
              .on(R.rising("temp").where(lambda v: v > 90),
                  handler, priority=10))
    reactor = R.compile([cooler], bus=bus); reactor.start()
    ```

  Both ports ship with an end-to-end cookbook example (`81_reactor_native.py` / `.ts`) and 21 tests apiece (`test_reactor_namespace.py` / `reactor-namespace.test.ts`).

- **`SignalRegistry`** — thread-safe (Python) / async-safe (TS) name→signal map backing the `R` facade. One per session. Exposes `.signal(name, initial)`, `.get(name)`, `.has(name)`, `.names()`, `.rule(...)`, `.attach(bus)`, `.clear()`. `R.scope()` returns a fresh isolated registry for tests and multi-tenant workflows.
- **`RuleSpec`** — frozen declarative rule record (`{predicate, handler, name, priority, preemptive}`) stored on builders via `.on()` and materialised into live `ReactorRule` instances by `R.compile()`. Stored as `builder._reactor_rules` (read-only view).
- **`ReactorPlugin`** — owns the reactor's lifecycle as an ADK `BasePlugin`. `on_session_start` starts the reactor, `on_session_end` stops it. Drop-in replacement for manual `reactor.start()/stop()` calls.
- **`R.computed(name, fn)`** — derived signal with auto-tracked dependencies. Reads via `Signal.get()` inside `fn` are transparently subscribed; the computed signal recomputes when any dep changes. Exported as `computed` at the package root in TS.

### Changed

- **`SignalPredicate.debounce(ms)` / `.throttle(ms)` are now immutable** (Python + TS). Previously both methods mutated `self` and returned `self` — calling `base.debounce(50)` silently rewrote every other user of `base`. They now return a fresh `SignalPredicate` with the updated window and leave the receiver untouched. This is a quiet correctness fix: any code that chained `.debounce()/.throttle()` onto a throw-away predicate continues to work; code that intentionally shared a base predicate now gets the correct isolation.
- **Harness re-exports** — `R`, `SignalRegistry`, `RuleSpec`, `ReactorPlugin`, `computed`, `make_rule_spec` / `makeRuleSpec` are now exported from the top-level package in both Python (`from adk_fluent import R, SignalRegistry, ...`) and TypeScript (`import { R, SignalRegistry, ... } from "adk-fluent-ts"`).

### Documentation

- **`CLAUDE.md` + `ts/CLAUDE.md` regenerated** — the auto-generated reactor section in `shared/scripts/llms_generator.py` (`_TS_HARNESS_PACKAGES`) now documents the `R` namespace, `Builder.on()`, the `SignalRegistry` / `RuleSpec` / `ReactorPlugin` trio, and the debounce/throttle immutability fix. The same text flows through `just llms` to `docs/llms.txt`, `docs/llms-ts.txt`, `.clinerules/adk-fluent.md`, `.cursor/rules/adk-fluent.mdc`, `.github/instructions/adk-fluent.instructions.md`, and `.windsurfrules`.

## [0.16.2] - 2026-04-20

### Changed

- **Release flow** — cut this version through `just rel-prepare patch` rather than hand-editing `VERSION`/`_version.py`/`package.json` and writing the changelog section manually. The recipe bumps all three version files, promotes `[Unreleased]` to a dated section, and stages a single `release: v<version>` commit, keeping the master `push · VERSION` trigger on a consistent shape.

## [0.16.1] - 2026-04-20

### Changed

- **README hero** — consolidated the six-row, 30+ badge wall at the top of `README.template.md` into a single centered row of six essentials (PyPI, npm, Python, CI, Docs, License). The same template feeds `README.md`, `python/README.md` snippets, and the docs landing page, so every surface gets the cleaner look without a separate edit.

### Fixed

- **Release workflow startup failure** — `ts-npm-dry` declared `permissions: contents: read` only. GitHub validates the permission caps of every reusable-workflow caller at workflow parse time regardless of `if:` gating, so the `_publish-npm.yml` nested `publish` job's `id-token: write` request was rejected with `'id-token: write', but is only allowed 'id-token: none'`. Added `id-token: write` to the `ts-npm-dry` block; fresh dispatches now pass validation and reach the `plan → python-pypi + ts-npm → tag-release` stages.

## [0.16.0] - 2026-04-19

### Added

- **flux catalog v0.16.0** — reference A2UI catalog ten Phase-1 components strong (`FluxBadge`, `FluxBanner`, `FluxButton`, `FluxCard`, `FluxLink`, `FluxMarkdown`, `FluxProgress`, `FluxSkeleton`, `FluxStack`, `FluxTextField`). Every component targets WCAG 2.2 AA, ships a basic-catalog fallback, and extends the A2UI v0.10 schema without forking it. See `catalog/flux/ARCHITECTURE.md` for the contracts.
- **Token pack system** — Radix-grade tonal scales (1-12) with semantic aliases (`text`, `bg`, `surface`, `border`, `focus`, `danger`, `success`) in `catalog/flux/tokens/{light,dark}.json`. Validated against `shared/schemas/tokens.schema.json` via `test_token_packs.py`; a pack that skips a step fails CI.
- **Authoring DSL** — TypeScript component specs under `catalog/flux/specs/*.spec.ts` using `defineComponent()` with invariant checks (name prefix, a11y required, examples non-empty, `defaultVariants` references). One spec file per component; CI rejects a spec that omits `examples` or references a variant key that doesn't exist.
- **Codegen pipeline** — `shared/scripts/flux/build.py` (subcommands: `load | check | emit | py | ts | react | docs | all | clean`) lowers specs + tokens + schemas into JSON catalog, Python `_flux_gen.py`, TypeScript `flux/` bundle, React scaffold renderers, and `docs/flux/components/*.md`. Idempotence contract: two `just flux` runs produce byte-identical output — guarded by `test_pipeline_is_idempotent`.
- **Fluent integration** — `UI.theme(pack)` attaches a theme pack to a surface; `UI.with_catalog("flux")` (Python) / `UI.withCatalog("flux")` (TS) swaps the component factories for a lexical block. `T.a2ui(catalog="flux")` routes the toolset through the flux registry. Thirteen Python + twelve TS parity tests verify the dispatch.
- **React renderers + visual goldens** — one `<Flux*>` renderer per component under `ts/src/flux/renderer/`, a `theme.ts` CSS-var injector, and `shared/visual/` with Playwright golden screenshots (light + dark × sm + md + lg) plus axe a11y smoke tests.

### Changed

- **`UI.*` factories are catalog-aware** — when a `with_catalog("flux")` block is active, `UI.button(...)` resolves to `FluxButton`, etc. The basic catalog remains the default; unknown catalogs raise `A2UIError` instead of silently degrading.
- **`T.a2ui()` accepts `catalog=`** — `T.a2ui(catalog="flux")` returns a flux-scoped toolset; omitting the kwarg preserves basic-catalog behavior unchanged.

### Fixed

- **Generator non-determinism** — `_sort_and_group_imports` used `(not name.isupper(), name.lower())` as its isort key; collisions for siblings like `MCPTool` vs `McpTool` fell back to set iteration order (PYTHONHASHSEED-dependent), making `.pyi` output drift across runs. Added `name` as a case-sensitive tiebreaker so ties sort in ASCII order.
- **pyi stub trailing newline** — `__init__.pyi` carried a stray trailing blank line that the `end-of-file-fixer` hook stripped on every commit; re-generation then re-added it. Removed the extra `append("")` in the stub emitter.
- **flux renderer map formatting drift** — the React renderer index emitted quoted keys (`"FluxBadge": FluxBadge`) which prettier unquoted (valid JS identifiers don't need quotes), so each `just flux` run reintroduced a diff. The emitter now writes unquoted keys matching prettier's canonical form.
- **Version drift blocked release** — `VERSION` stayed at `0.15.0` while `python/src/adk_fluent/_version.py` and `ts/package.json` advanced to `0.16.0`, failing `release preflight --strict` and skipping PyPI + npm publishes for the 0.16.0 cut. Re-synced all three files to `0.16.0` so the release workflow can fire cleanly.
- **Release workflow startup failure** — `release.yml` declared `permissions: contents: read` at the workflow level but the jobs calling `_publish-python.yml` / `_publish-npm.yml` inherited that read-only cap. When the nested `publish` jobs requested `id-token: write` (PyPI Trusted Publishing + npm provenance) and `attestations: write` (PEP 740), GitHub rejected every dispatched run at validation with *"nested job 'publish' is requesting 'attestations: write, id-token: write', but is only allowed 'attestations: none, id-token: none'"* — so the 0.16.0 release never reached the publish step. Added per-job `permissions` blocks on the four reusable-workflow callers (`python-pypi`, `python-testpypi`, `ts-npm`, `ts-npm-dry`) to lift the cap to what each callee needs.

### Documentation

- **README badges refresh** — grouped badge block (Release, Reach, Engineering, Ecosystem, Community, Social) across `README.template.md`, `README.md`, and `python/README.md`. Adds npm + Node + TypeScript + Bundlephobia + Packagephobia + Codecov + CodeQL + OpenSSF Scorecard + Ruff + Prettier + DeepWiki + Codespaces + Gitpod alongside the existing PyPI signals. Footer gains a dark/light star-history chart and a contrib.rocks contributor ribbon.

## [0.15.0] - 2026-04-19

### Added

- **A2UI devex wedge**: `Agent.ui(spec, *, llm_guided=False, validate=True, log=False)` behavior matrix — single flag flips an agent into LLM-guided UI mode and auto-wires `T.a2ui()` + `G.a2ui()` (+ optional `M.a2ui_log()`) with build-time deduplication.
- **Schema-driven forms**: `UI.form(MyPydanticModel)` (Python) / `UI.form(z.object({...}))` (TS) generate a typed surface from a model — string/int/bool/Literal/EmailStr/HttpUrl/date all map to the right component with the right validation.
- **Reflective bindings**: `UI.paths(Schema)` returns a typed proxy — `paths.email` yields a two-way `UIBinding` to `/email`, with helpful errors on typos. Mirrored in TS.
- **A2UI exception hierarchy**: `A2UIError`, `A2UINotInstalled`, `A2UISurfaceError`, `A2UIBindingError` re-exported from the package root in both Python and TS.
- **Surface integrity validation**: `UISurface.validate()` catches duplicate component IDs, virtual-group roots, two-way bindings against undeclared data keys, and unhandled action events. Same fail-first order in Python and TS. Auto-runs at build time unless opted out via `Agent.ui(..., validate=False)`.
- **TS Zod v4 support**: `zod ^4.3.6` added as an optional peer dependency for `UI.form`/`UI.paths` schema introspection.

### Changed

- **`T.a2ui()` is now fail-loud**: raises `A2UINotInstalled` when the optional `a2ui-agent` package isn't installed (was a silent no-op that produced confusing downstream failures). `Agent.build()` rethrows as `BuilderError` (Python) / `Error` with descriptive prefix (TS).
- **`UI.form` overload**: `UI.form(SchemaCls)` is now the preferred path; the legacy `UI.form("title", fields={...})` dict form is preserved for back-compat.

## [0.14.0] - 2026-04-13

### Added

- **Monorepo restructure**: Python (`python/`), TypeScript (`ts/`), and shared codegen (`shared/`) now live in a single repo (#113)
- **TypeScript package (adk-fluent-ts)**: Full TS port with 135 builders, 9 namespaces, immutable builder pattern, and camelCase API (#113)
- **Unified hooks foundation**: Session-scoped, subagent-inherited hook system with 12 event types, `HookRegistry`, `HookPlugin` (#117)
- **Permissions sub-package**: Refactored `_permissions.py` into 6-module package with `PermissionPolicy`, `PermissionPlugin`, `ApprovalMemory` (#117)
- **Budget sub-package**: Extracted `BudgetMonitor` into `_budget/` with `BudgetPolicy`, `BudgetPlugin`, `Threshold` (#117)
- **Shared visual runner**: Language-agnostic SPA at `shared/visual/index.html` with auto-detected language badge, served by both Python and TS backends
- **TypeScript visual server**: Hono-based dev server (`ts/visual/server.ts`) implementing the same 4-endpoint API contract as Python
- **Configurable visual ports**: `just visual-py [port]` (default 8098), `just visual-ts [port]` (default 8099)
- **12 new TypeScript cookbooks** (64-75): middleware schema, builtin middleware, T module tools, G module guards, A2UI basics through dynamic, harness and skills, coding agent harness
- **TS cookbook doc generation**: `doc_generator.py` now handles `.ts` files (JSDoc parsing, `typescript` code fences); `just docs-cookbook-ts`
- **A2UI dynamic cookbook** (Python 77): LLM-guided UI generation example with golden test snapshots
- **Harness examples**: `coding_agent_harness`, `harness_and_skills`, `harness_coder` example agents

### Fixed

- **Keyword-only callback signatures**: All harness/budget/permissions callbacks updated to `*, **_kw` pattern for ADK compatibility (8 files)
- **`_ui_compile.py` crash**: Removed `config["_ui_spec"]` / `config["_ui_surface"]` that caused `LlmAgent(**config)` to fail with `extra='forbid'`
- **`visual/server.py` session service**: Use `runner.session_service` instead of standalone `InMemorySessionService`
- **Pyright errors in visual/server.py**: Added `None` guards for `spec`/`spec.loader`, typed `result` as `dict[str, Any]`, added return annotation to `_load_agent`

### Changed

- **Monorepo layout**: All Python code moved under `python/`, TypeScript under `ts/`, shared codegen under `shared/`
- **Hot-path optimizations**: Slots, hook table, tape, deepcopy improvements (#116)
- **Middleware resilience**: Restructured middleware primitives (#115)
- **Documentation**: Three-pathway architecture (Pipeline, Skills, Harness), harmonized for monorepo (#110, #111, #114)
- **TS README**: Expanded with H namespace showcase, 75-cookbook reference, visual runner section
- **TS cookbook INDEX.md**: Updated from 26 to 75 entries with A2A, A2UI, and advanced pattern sections

## [0.13.2] - 2026-03-17

### Added

- **Lazy import loading**: `import adk_fluent` now loads 1 module instead of ~1,468. ADK dependencies are deferred to `build()` time, reducing import-time memory from ~181 MB to near zero
- **`__init__.pyi` stub**: Generated type stub ensures pyright resolves all lazy exports correctly
- **Import budget CI test**: `tests/test_import_budget.py` guards against import-time regressions (module count < 200, no `google.adk.agents` at import time)
- **Subpackage shadow resolution**: `_fix_subpackage_shadows()` handles Python's auto-set of `parent.child = <module>` when a subpackage name matches an exported name (e.g. `compile`)

### Changed

- **`_base.py`**: Removed 37 primitive re-exports (`tap`, `gate`, `race`, `Route`, `Fallback`, etc.) that forced the full ADK import chain. Primitives now use deferred local imports in method bodies
- **Generated builder modules**: ADK class imports moved from module-level to inside `build()` methods. TYPE\_CHECKING blocks provide type resolution for pyright
- **`__init__.py`**: Replaced eager `from .module import Name` with `__getattr__`-based lazy loading and `_LAZY_IMPORTS` dict
- **Generator pipeline**: `orchestrator.py`, `imports.py`, `ir_builders.py`, `module_builder.py` updated to emit deferred imports and lazy `__init__.py`

## [0.13.1] - 2026-03-16

### Fixed

- **Broad exception handling** (M1): Replaced 10 `except Exception` sites in `_base.py` with specific types (`NotImplementedError`, `AttributeError`, `ImportError`)
- **Silent failures** (M4): Guards (`_LLMJudge`), artifacts (`_ToolFactory.load`), and asyncio backend now emit `warnings.warn()` instead of silently passing
- **Dispatch task cleanup** (M9): `JoinAgent` uses `try/finally` to prevent ContextVar task registry leaks
- **Silent issue type loss** (T4): `_convert_issues()` now preserves unknown issue types instead of dropping them
- **Contract pass count** (T2): Fixed docstring claiming 16 passes (actual: 15)
- **Broken example files**: Fixed syntax errors in 6 example agent files (corrupted imports, missing `BaseModel`, empty except blocks)
- **Sphinx warnings**: Added 10 missing research docs to toctree; fixed TOML lexer warning from `...` in code block
- **`_DictState` mutable default** (L7): Changed from shared class attribute to instance-only

### Added

- **Namespace composition operator symmetry** (H3):
  - `S` module: added `|` (pipe, alias for `>>`)
  - `C` module: added `>>` (chain, alias for `|`)
  - `P` module: added `>>` (chain, alias for `|`)
  - `A` module: added `>>` (chain via pipeline operator)
- **Parallel merge conflict detection** (M5): Asyncio backend logs a warning when parallel branches write the same state key
- **E namespace protocol properties** (M6): Added `_kind`, `_reads_keys`, `_writes_keys` to `EComposite`
- **Backend protocol typing** (M8): `Backend.capabilities` typed as `EngineCapabilities` via `TYPE_CHECKING` guard
- **ADK backend documentation** (H1): Class docstring now documents compile-only design
- **`_propagate_middlewares` helper** (M2): Extracted duplicated middleware merge logic from `__rshift__`/`__or__`
- **`backends/_utils.py`** (M3): Shared `safe_identifier()` utility (removed duplicate from `dbos_worker.py`)

### Deprecated

- `.dispatch(progress_key=)` now emits `DeprecationWarning` — use `stream_to=` instead (L5)

### Changed

- **`hasattr` → `getattr`** (L6): Standardized `_middlewares` access pattern across `_base.py`
- **`annotate_checkpoints`** (T6): Removed no-op placeholder from `run_passes()` (function retained for future use)
- Applied ruff formatting via pre-commit hooks across all hand-written files

## [0.13.0] - 2026-03-16

### Added

- **A2UI (Agent-to-UI) integration**: Declarative UI composition for agents
  - `UI` namespace with 18 component factories: `UI.text()`, `UI.button()`, `UI.text_field()`, `UI.image()`, `UI.row()`, `UI.column()`, and more
  - Expression operators: `|` (Row), `>>` (Column) for composing UI layouts
  - `UI.surface()` compilation root, `UI.auto()` for LLM-guided mode
  - Data binding (`UI.bind()`) and validation (`UI.required()`, `UI.email()`)
  - Preset surfaces: `UI.form()`, `UI.dashboard()`, `UI.wizard()`, `UI.confirm()`, `UI.table()`
  - Agent integration: `.ui()` builder method, `T.a2ui()` toolset, `G.a2ui()` guard, `P.ui_schema()` prompt helper
  - State bridges: `S.to_ui()`, `S.from_ui()` for bidirectional state-UI data flow
  - Context: `C.with_ui()` for including UI state in agent context
  - Middleware: `M.a2ui_log()` for surface operation logging
  - A2UI codegen pipeline: `scripts/a2ui/` scanner, seed generator, and code generator
  - A2UI specification files: `specification/v0_10/json/` (basic catalog, common types, client/server schemas)
  - 5 cookbook examples: basics (#70), agent integration (#71), operators (#72), LLM-guided (#73), pipeline (#74)
  - Full test coverage: `test_ui_core.py`, `test_ui_compile.py`, `test_ui_agent.py`, `test_ui_namespaces.py`, `test_ui_presets.py`, `test_ui_generated.py`
- **A2UI composition patterns**: Higher-order constructors in `patterns.py`
  - `ui_form_agent()`, `ui_dashboard_agent()`, `ui_wizard_agent()` for quick agent+UI scaffolding
- **Agent skills**: 6 distributable skills auto-synced to `.gemini/skills/`
  - cheatsheet, dev-guide, eval-guide, deploy-guide, observe-guide, scaffold
- **Documentation improvements**
  - A2UI user guide (`docs/user-guide/a2ui.md`)
  - A2A user guide (`docs/user-guide/a2a.md`)
  - DevEx Tooling Manifesto (`docs/devex-tooling-manifesto.md`)
  - Guards cookbook (#67) with full G module composition examples
  - Progressive disclosure and hero openings across documentation

### Changed

- **Codegen pipeline**: Extracted shared utilities into `scripts/shared.py`, eliminated `sys.argv` manipulation in generators
- **`just all` pipeline**: Now includes `a2ui` and `skills` stages (`scan → seed → generate → a2ui → docs → skills → docs-build`)
- **A2UI seed format**: Generated with `--json` flag for richer component metadata
- **Editor rules**: Regenerated `.clinerules`, `.cursor/rules`, `.windsurfrules`, `.github/instructions` with A2UI documentation

### Fixed

- **Pyright `typecheck-core`**: 9 type errors resolved
  - `_ui.py`: Restructured nested dict build to avoid narrowed type conflict
  - `_ui_generated.py`: Generator now emits `T | None = None` for optional params
  - `patterns.py`: Widened `ui_form_agent` `fields` param to match `UI.form` signature
- **Pre-commit hooks**: 3 failures resolved
  - UP038: `isinstance(value, (int, float))` → `isinstance(value, int | float)`
  - `end-of-file-fixer`: Fixed trailing blank line in `concepts_generator.py` output
  - `check-toml`: Excluded JSON-content `seeds/a2ui_seed.toml` from TOML validation
- **Ruff lint**: Fixed B011 (`assert False` → `pytest.raises`), F841 (unused variables), B007 (unused loop variable), SIM116 (consecutive if suppression)

## [0.12.1] - 2026-03-15

### Added

- **A2A protocol integration**: First-class support for Google's Agent-to-Agent protocol
  - `RemoteA2aAgent` builder for agents that communicate via A2A client
  - `A2aAgentExecutor` and `A2aAgentExecutorConfig` builders for A2A server-side execution
  - A2A Phase 2: state bridging between ADK sessions and A2A tasks, resilience middleware
  - A2A Phase 3: agent discovery, registry, and lifecycle management
  - `.skill()` method for A2A skill card declarations, `T.a2a()` for A2A tool composition
  - Example: `examples/a2a_remote_delegation/` with client, server, and patterns demo
- **`G` (Guards) module**: Input/output validation guard namespace
  - `G.guard(fn)` custom guard, `G.pii()` PII detection, `G.toxicity()` toxicity detection
  - `G.length()` response length guard, `G.schema()` schema validation
  - Guard compilation and IR integration with `.guard()` builder method
  - `GuardViolation`, `PIIDetector`, `ContentJudge` provider protocols
- **`E` (Eval) module**: Fluent agent evaluation namespace
  - `E.case()` evaluation cases, `E.criterion()` custom criteria, `E.persona()` personas
  - `LLMJudge` for LLM-powered evaluation, `E.gate()` enforcement
  - `EvalSuite`, `EvalReport`, `ComparisonReport` for structured evaluation
- **Namespace expansion**: 30+ new methods across existing namespaces
  - `S`: `accumulate`, `counter`, `history`, `validate`, `require`, `flatten`, `unflatten`, `zip`, `group_by`
  - `T`: `mock`, `confirm`, `timeout`, `cache`, `mcp`, `openapi`, `transform`
  - `M`: `circuit_breaker`, `timeout`, `cache`, `fallback_model`, `dedup`, `sample`, `trace`, `metrics`
- **`NamespaceSpec` protocol**: Uniform interface across all namespace modules (P, C, S, A, M, T, E, G)
- **Interactive visual references**: 5 standalone HTML reference pages with dark-theme design system
  - Data flow reference, delegation reference, execution modes reference
  - A2A topology reference, module lifecycle reference
- **Documentation overhaul**
  - 25-point visual audit: favicon, social cards, hover tooltips, 404 page, custom CSS/JS
  - Hero workflow cookbooks: deep research, customer support triage, code review agent, and more
  - Decision guide, best practices & anti-patterns guide, callbacks guide, execution guide
  - Expanded user guides for middleware, testing, memory, visibility, presets, expression language
  - Sequence diagram generation for module lifecycle
- **AI coding agent skills**: Auto-generated skills for Claude Code and Gemini CLI
  - 8 skills: develop-feature, codegen-pipeline, debug-builder, architect-agents, review-pr, add-cookbook, write-tests, upgrade-adk
  - Shared reference files and validation scripts
- **Editor rules**: Auto-generated `.clinerules`, `.cursor/rules`, `.windsurfrules`, `.github/instructions` from manifest
- **CI improvements**: N-5 backward compatibility matrix, composite `setup-env` action, optimized workflows

### Changed

- **Code generation pipeline**: New `optional_imports` mechanism on `ModuleNode` IR for optional dependencies — emits `if not TYPE_CHECKING: try/except` with `TYPE_CHECKING`-guarded imports for pyright compatibility
- **Code IR**: New `ForkAndAssign`, `AsyncForYield`, `DeprecationStmt` statement nodes; shared `split_at_commas` utility
- **DevEx audit refactors** (PR #69): Exception hierarchy (`_exceptions.py`), context provider extraction (`_context_providers.py`), improved error messages
- **Documentation site**: Redesigned CSS with Inter/JetBrains Mono fonts, card-based layouts, responsive grid
- **CI workflows**: Consolidated with reusable composite action, `just check-gen` replaces inline git diff

### Fixed

- **A2A SDK is now truly optional**: Generator pipeline emits `try/except` with `None` fallback for `google.adk.a2a.*` and `google.adk.agents.remote_a2a_agent` imports — no more `ModuleNotFoundError` when `a2a` SDK is not installed
- **Pyright `reportInvalidTypeForm`**: Optional import fallbacks (`_ADK_X = None`) guarded with `if not TYPE_CHECKING:` so pyright only sees real types from the `TYPE_CHECKING` block
- **Ruff SIM105**: Optional `import a2a.types` uses `contextlib.suppress` instead of `try/except/pass`
- **Docs build**: Suppress `hoverxref` deprecation warning, exclude architecture dir, fix Pygments lexer warnings
- **Stale stubs**: Regenerated `.pyi` stubs for config, plugin, tool modules
- **Deprecated API calls**: Replaced `.history("none")` with `.context(C.none())` across docs and cookbooks

## [0.11.0] - 2026-03-01

### Added

- **`A` module Phase 2+3**: Advanced artifact lifecycle operations
  - **Batch operations**: `A.publish_many()`, `A.snapshot_many()` for multi-artifact workflows
  - **LLM tool factories**: `A.tool()` factories for LLM-driven artifact interaction
  - **`A.for_llm()` CTransform**: Context transform for LLM-aware artifact loading
  - **Content transforms**: Pre-publish (`from_json`, `from_csv`, `from_markdown`) and post-snapshot (`as_json`, `as_csv`, `as_text`) content transforms
  - **`ArtifactSchema`**: Typed artifact declarations using `Annotated[type, Produces(...)]` and `Consumes(...)` annotations
  - **Contract checker Pass 16**: Validates artifact availability across pipeline stages
  - **Visualization**: Artifact node rendering and flow edges in Mermaid diagrams
  - `ArtifactSchema`, `Produces`, `Consumes` exported from prelude
- **Auto-generated API docs**: `doc_generator.py` now produces API reference pages for namespace modules (`P`, `C`, `S`, `A`, `M`, `T`)
- **DevEx improvements**: Standalone `quickstart.py`, `scripts/benchmark.py` for build overhead measurement, README rewritten with `.ask()` lead, ASCII operator diagrams, Common Errors section, When to Use guide, tiered cookbook, Performance section, ADK Compatibility matrix

### Changed

- `ci: sync-adk.yml` moved from repo root to `.github/workflows/` for activation
- README restructured: Quick Start leads with `.ask()` and visible output, Zero to Running section with AI Studio + Vertex AI paths

### Fixed

- `ToolRegistry.search` falls back to substring matching when BM25 scores zero

## [0.10.0] - 2026-03-01

### Added

- **`A` module Phase 1**: Artifact management surface, consistent with `P`/`C`/`S`/`M`/`T`
  - **`ATransform` descriptor**: Core factory methods (`A.publish()`, `A.snapshot()`, `A.save()`, `A.load()`, `A.list()`, `A.version()`, `A.delete()`) for artifact lifecycle
  - **`A.mime` constants**: MIME type classifiers for artifact content
  - **`ArtifactAgent` runtime**: Executes publish/snapshot/save/load/list/version/delete operations
  - **`ArtifactNode` IR**: Intermediate representation for artifact operations with `_fn_step` detection
  - **`.artifacts()` builder method**: Attach artifact transforms to agents via seed-generated method
  - **Contract checker Pass 15**: Validates artifact availability across pipeline stages
  - `A` and `ATransform` exported from prelude
- **`Fallback` builder**: Explicit builder for `//` operator — `.attempt()` method for adding fallback alternatives
- **Verb harmonization**: Consistent API naming across the entire surface
  - `delegate()` → `agent_tool()` (wraps sub-agent as tool)
  - `delegate_agent()` → `add_agent_tool()`
  - `guardrail()` → `guard()`
  - `retry_if()` → `loop_while()`
  - `inject_context()` → `prepend()`
  - `save_as()` retained as canonical (`.outputs()` deprecated in v0.8.0)
  - `_TimeoutBuilder` → `TimedAgent`, `_DispatchBuilder` → `BackgroundTask`

### Changed

- `.tools()` now always appends (consistent with other list methods)
- `C.template()` parameter alignment, `C.capture()` removed (use `S.capture()`)
- `Route` gains `.gte()`, `.lte()`, `.ne()` comparison predicates
- All cookbooks, README, and tests updated to use harmonized verb names

### Removed

- `.retry()` and `.fallback()` methods (use `loop_while()` and `//` operator)
- `C.capture()` (use `S.capture()` instead)

### Deprecated

- `.delegate()` — use `.agent_tool()` instead
- `.guardrail()` — use `.guard()` instead
- `.retry_if()` — use `.loop_while()` instead
- `.inject_context()` — use `.prepend()` instead

## [0.9.6] - 2026-03-01

### Added

- **`T` module**: Fluent tool composition surface, consistent with `P`/`C`/`S`/`M`
  - **`TComposite`**: Composable tool chain with `|` pipe operator — `T.fn(search) | T.fn(email) | T.google_search()`
  - **Factory methods**: `T.fn()` (wrap callable/BaseTool), `T.agent()` (wrap agent as AgentTool), `T.toolset()` (wrap MCPToolset etc.), `T.google_search()` (built-in), `T.schema()` (attach ToolSchema)
  - **`T.fn(fn, confirm=True)`**: Convenience for `require_confirmation` on FunctionTool
  - **`T.search(registry)`**: BM25-indexed dynamic tool loading with two-phase pattern
- **`ToolRegistry`**: BM25-indexed catalog for tool discovery — `register()`, `search()`, `get_tool()`, `from_tools()` factory
  - Optional `rank_bm25` dependency (`pip install adk-fluent[search]`); falls back to substring matching
- **`SearchToolset`**: Two-phase dynamic tool loading lifecycle
  - Phase 1 (Discovery): meta-tools (`search_tools`, `load_tool`, `finalize_tools`) for BM25-powered tool discovery
  - Phase 2 (Execution): frozen tool list for stable KV-cache performance
  - `always_loaded` and `max_tools` configuration
- **`search_aware_after_tool`**: Pre-built `after_tool` callback for search-aware agents — handles large result compression and error preservation
- **`compress_large_result`**: Helper to write large tool outputs to temp files, keeping context lean
- **Builder `.tools()` override**: Accepts `TComposite` chains, plain lists, or single tools/toolsets; extracts `_SchemaMarker` for contract checking
- New cookbook example: T module tools (#66) — 13 sections covering full T surface
- Updated cookbooks: #02 (agent with tools), #27 (delegate pattern), #58 (multi-tool agent) with T module alternatives

### Changed

- `pyproject.toml` adds `search` optional dependency group: `rank-bm25>=0.2.2`
- Prelude exports expanded with `T`, `TComposite`, `ToolRegistry`, `SearchToolset`, `search_aware_after_tool`

## [0.9.5] - 2026-03-01

### Added

- **Middleware v2**: Complete mechanism-level redesign of the middleware system
  - **`TraceContext`**: Per-invocation state bag (`request_id`, `elapsed`, key-value store) created once per run, passed as first arg to all hooks, propagates via ContextVar
  - **Per-agent scoping**: Middleware `agents` attribute filters hooks to specific agents — supports `str`, `tuple[str, ...]`, `re.Pattern`, and `Callable[[str], bool]`
  - **Topology hooks**: 6 new lifecycle hooks — `on_loop_iteration`, `on_fanout_start`/`on_fanout_complete`, `on_route_selected`, `on_fallback_attempt`, `on_timeout`
  - **Stream lifecycle hooks**: `on_stream_start`, `on_stream_end`, `on_backpressure`
  - **Controllable dispatch**: `DispatchDirective(cancel=True)` to skip dispatches, `LoopDirective(break_loop=True)` to exit loops from middleware
  - **Error boundary**: Middleware exceptions are caught and logged; `on_middleware_error` hook notifies other middleware
  - **Conditional middleware**: `M.when("stream", mw)` / `M.when(callable, mw)` / `M.when(PredicateSchema, mw)` with deferred evaluation
- **`M` module**: Fluent middleware composition surface, consistent with `P`/`C`/`S`
  - Factory methods: `M.retry()`, `M.log()`, `M.cost()`, `M.latency()`, `M.topology_log()`, `M.dispatch_log()`
  - Composition operators: `M.scope("agent", mw)`, `M.when(condition, mw)`, `|` pipe for chaining
  - Single-hook shortcuts: `M.before_agent(fn)`, `M.after_agent(fn)`, `M.before_model(fn)`, `M.after_model(fn)`, `M.on_loop(fn)`, `M.on_timeout(fn)`, `M.on_route(fn)`, `M.on_fallback(fn)`
  - `MComposite` composable chain class with `|` operator and `to_stack()` flattening
- **Built-in middleware**: `TopologyLogMiddleware` (structured topology event logging), `LatencyMiddleware` (per-agent timing), `CostTracker` (token usage accumulation)
- **`MiddlewareSchema`**: Typed middleware declarations using `Annotated[type, Reads(scope=...)]` and `Writes()` — declares state dependencies for contract checking
- **Contract checker Pass 14**: Validates scoped middleware schemas against pipeline state flow — reads must be satisfied by prior writes, writes promoted downstream
- **`M.when(PredicateSchema, mw)`**: Conditional middleware evaluated against session state at hook invocation time via `TraceContext.invocation_context`
- **Dispatch/join/stream primitives**: `dispatch()`, `join()`, `StreamRunner`, `Source` factories (`from_iter`, `from_async`, `poll`, `callback`/`Inbox`), `StreamStats`, configurable `task_budget()`
- **`P` namespace**: Structured prompt composition — `P.system()`, `P.user()`, `P.example()`, `P.constraint()`, `P.persona()`, with `|` composition
- **`S` state transforms**: `S.pick()`, `S.drop()`, `S.rename()`, `S.merge()`, `S.default()`, `S.transform()`, `S.compute()`, `S.guard()`, `S.log()`, `S.capture()` — all with `_reads_keys`/`_writes_keys` traceability
- **`DeclarativeMetaclass`**: Shared metaclass introspecting `Annotated` type hints into `DeclarativeField` objects — base for `ToolSchema`, `CallbackSchema`, `PredicateSchema`, `MiddlewareSchema`
- **Recipes quick-find tables**: "Quick find by primitive" and "Quick find by question" tables in recipes-by-use-case index
- **`.explain(format="json")`**: Structured dict output for programmatic consumption
- **`.explain(docs_url=...)`**: Appends API reference link; customizable via parameter or `ADKFLUENT_DOCS_URL` env var
- **`.explain(open_browser=True)`**: Opens API docs page in the default browser
- **`--diff-markdown` flag on scanner**: Generates a publishable API diff Markdown page
- **`just diff-md` command**: One-command API diff page generation
- **Copy-paste-run contract**: All examples document prerequisites; cookbook examples need no API key
- New cookbook examples: M module composition (#62), topology hooks (#63), MiddlewareSchema contracts (#64), built-in middleware (#65)

### Changed

- `_ConditionalMiddleware` rewritten to return guarded async wrappers (deferred evaluation) instead of returning `None` from `__getattr__`
- `SequenceNode` IR gains `middlewares` field for contract checker integration
- `_pipeline_to_ir()` now wires middleware from builders through to IR
- Recipes-by-use-case index reorganized with quick-find sections above the domain categories
- Runnable examples page rewritten with full prerequisites section
- Cookbook index includes "How to run these examples" section

## [0.9.4] - 2026-02-27

### Added

- **`.explain(format="json")`**: Structured dict output for programmatic consumption
- **`.explain(docs_url=...)`**: Appends API reference link; customizable via parameter or `ADKFLUENT_DOCS_URL` env var
- **`.explain(open_browser=True)`**: Opens API docs page in the default browser
- **`--diff-markdown` flag on scanner**: Generates a publishable API diff Markdown page
- **`just diff-md` command**: One-command API diff page generation
- **Recipes quick-find tables**: "Quick find by primitive" (25 entries) and "Quick find by question" (13 entries) tables in recipes-by-use-case index
- **Copy-paste-run contract**: Runnable examples page rewritten with full prerequisites section; cookbook index includes "How to run" section

## [0.9.3] - 2026-02-27

### Added

- **Error reference page**: New `docs/user-guide/error-reference.md` documents every error pattern (`BuilderError`, `AttributeError`, `ValueError`, `TypeError`, `NotImplementedError`) with causes, code examples, and fixes
- **Recipes by Use Case index**: New `docs/generated/cookbook/recipes-by-use-case.md` organizes all 58 cookbook examples into 9 domain categories (customer support, e-commerce, research, production, etc.)
- **Runnable Examples page**: New `docs/runnable-examples.md` indexes all 49 standalone `adk web`-compatible examples with setup instructions, descriptions, and run commands
- **Cookbook examples 55-58**: Generated documentation for deep research, customer support triage, code review agent, and multi-tool agent capstone examples

### Fixed

- **Stale docs changelog**: `docs/changelog.md` was stuck at v0.3.1 — now synced with root `CHANGELOG.md` covering all releases through v0.9.2

## [0.9.2] - 2026-02-27

### Added

- **Transform traceability**: All `S.*` state transform factories now carry `_reads_keys` and `_writes_keys` annotations, enabling the contract checker to trace data flow through `S.rename()`, `S.merge()`, `S.pick()`, etc.
- **`reads_keys` on TransformNode**: IR `TransformNode` now stores which state keys a transform reads, allowing precise data-flow analysis across transform boundaries
- **ParallelNode contract checking**: Detects `output_key` collisions and `writes_keys` overlaps between parallel branches (write isolation)
- **LoopNode contract checking**: Validates loop body sequences using the same 11-pass analysis as `SequenceNode`
- **Structured `.diagnose()` method**: Returns a `Diagnosis` dataclass with typed fields (`agents`, `data_flow`, `issues`, `topology`) for programmatic access to build-time analysis
- **`.doctor()` method**: Prints a human-readable diagnostic report and returns the formatted string
- **`format_diagnosis()` function**: Renders a `Diagnosis` into a formatted report with Agents, Data Flow, Issues, and Topology sections
- **New dataclasses**: `Diagnosis`, `AgentSummary`, `KeyFlow`, `ContractIssue` — all exported from `adk_fluent` and `adk_fluent.testing`
- **11-pass contract analysis**: Enhanced from 9 passes — adds transform-reads validation (Pass 10) and transform-writes tracing (integrated into Pass 2)
- 36 new tests: transform tracing (11), parallel/loop contracts (9), diagnosis module (16)

### Changed

- Contract checker now dispatches by node type (`SequenceNode`, `ParallelNode`, `LoopNode`) instead of only handling sequences
- `_FnStepBuilder.to_ir()` extracts `_reads_keys`/`_writes_keys` from annotated callables and stores them on `TransformNode`

## [0.9.1] - 2026-02-27

### Added

- **`context_spec` preservation in IR**: `AgentNode` now carries the `CTransform` descriptor (e.g., `C.user_only()`, `C.window(n=3)`, `C.from_state()`) through to IR, enabling context-aware diagnostics
- **Context-aware contract checking**: Passes 4 (channel duplication) and 6 (data loss) now consult `context_spec.include_contents` to avoid false positives when context is intentionally suppressed
- **9-pass contract analysis**: Enhanced from 7 passes — adds dead-key detection (Pass 8) and type-compatibility checking (Pass 9)
- **Rich `.explain()` output**: Rewritten to show model, instruction preview, template variables (required vs optional), data flow (reads/writes), context strategy, structured output, tools, callbacks, children, and inline contract issues with hints
- **Data flow edges in Mermaid**: `to_mermaid(show_data_flow=True)` renders dotted arrows showing key flow between producers and consumers
- **Context annotations in Mermaid**: `to_mermaid(show_context=True)` annotates nodes with their context strategy
- **Copy-on-Write frozen builders** (#7): Composition operators (`>>`, `|`, `*`, `@`, `//`) and `to_app()` now freeze the builder; subsequent mutations automatically fork a new clone. Backwards compatible — unfrozen chains still mutate in place.
- **`__dir__` override** (#8): `dir(Agent("x"))` now includes all fluent method names (aliases, callbacks, ADK model fields) for REPL/IDE autocomplete.
- **`BuilderError` exception** (#9): `.build()` failures now raise a structured `BuilderError` with per-field error messages instead of raw 30-line pydantic tracebacks. Exported from `adk_fluent`.
- **`.native(fn)` escape hatch** (#10): Register post-build hooks that receive the raw ADK object, allowing direct mutation without abstraction lock-in. Multiple hooks chain in order.
- **`adk-fluent visualize` CLI** (#12): New CLI tool renders any builder as a Mermaid diagram. Supports `--format html|mermaid`, `--var`, `--output`, and auto-detection of BuilderBase instances in a module.
- **Autocomplete stress tests** (#13): Pyright subprocess tests verify type resolution for chained methods, `.build()` return type, unknown method errors, and operator result types.
- **`typecheck-core` target** (#18): New justfile target runs pyright on hand-written code only. CI now runs both stub and core type checking.
- 40 new tests: context_spec IR (8), enhanced contracts (12), rich explain (13), enhanced viz (7)

### Changed

- `.explain()` output format now uses structured sections with capitalized labels (e.g., "Model:", "Instruction:", "Template vars:")
- `to_mermaid()` accepts new parameters: `show_contracts`, `show_data_flow`, `show_context`
- `CaptureNode` gets distinctive `([capture])` shape in Mermaid diagrams
- **Pyright config** (#18): `[tool.pyright]` now includes only hand-written modules and excludes generated files to eliminate false positives.
- **Code IR**: New `ForkAndAssign` statement node emits copy-on-write guards in all generated setter methods.
- **CI pipeline**: Added `typecheck-core` step and cookbook test run to `.github/workflows/ci.yml`.

### Fixed

- **Mutation corruption** (#7): `base = Agent("x").model("m"); a = base >> Agent("y"); b = base.instruct("z")` no longer corrupts `a` — `b` is an independent clone.

## [0.8.0] - 2026-02-25

### Added

- **`.save_as(key)` method**: Clearer name for storing agent response text in session state (replaces `.outputs()`)
- **`.stay()` method**: Prevent agent from transferring back to parent (positive alternative to `.disallow_transfer_to_parent(True)`)
- **`.no_peers()` method**: Prevent agent from transferring to sibling agents (positive alternative to `.disallow_transfer_to_peers(True)`)
- **`adk_fluent.prelude` module**: Minimal imports for most projects — `Agent, Pipeline, FanOut, Loop, C, S, Route, Prompt`
- **`deprecated_aliases` codegen support**: Generator emits `DeprecationWarning` for deprecated method names pointing to their replacements
- **Choosing the Right Method table**: Transfer control user guide now documents Pipeline.step, FanOut.branch, Loop.step, Agent.sub_agent, Agent.delegate

### Changed

- All cookbook examples and user guides updated to use `.save_as()` instead of `.outputs()`
- Deep search example updated to use `.context(C.none())` instead of `.history("none")`

### Deprecated

- **`.outputs(key)`** — use `.save_as(key)` instead
- **`.history()`** — use `.context()` with C module instead
- **`.include_history()`** — use `.context()` with C module instead
- **`.static_instruct()`** — use `.static()` instead

## [0.7.0] - 2026-02-25

### Added

- **`.isolate()` convenience method**: Sets both `disallow_transfer_to_parent` and `disallow_transfer_to_peers` in one call for specialist agents
- **`[field_docs]` seed system**: Rich IDE docstrings for `output_schema`, `input_schema`, `output_key`, `disallow_transfer_to_parent`, `disallow_transfer_to_peers` — hover tooltips now explain behavior and constraints
- **Structured data user guide**: `docs/user-guide/structured-data.md` — covers `.outputs()`, `.output_schema()`, `@ Schema`, `.input_schema()`, state access patterns
- **Transfer control user guide**: `docs/user-guide/transfer-control.md` — covers control flags, `.isolate()`, control matrix, common patterns
- **Context engineering user guide**: `docs/user-guide/context-engineering.md` — C module primitives, composition, Agent.context() integration
- **Visibility user guide**: `docs/user-guide/visibility.md` — topology inference, policies, .show()/.hide()
- **Memory user guide**: `docs/user-guide/memory.md` — modes, auto-save, combining with context
- **Hand-written API reference**: `docs/generated/api/context.md`, `visibility.md`, `contracts.md`
- **54 cookbook examples**: All rewritten with real-world scenarios (insurance, customer service, fraud detection, medical, legal, etc.)
- **`.pyi` stub docstrings**: All generated stub methods now have descriptive docstrings for IDE hover
- **Rich examples + see-also**: 8 key extras in seed.manual.toml enriched with inline examples and cross-references
- **Seed merge for field_docs**: `seed_generator.py` merges `[field_docs]` from manual overlay

### Fixed

- Pre-existing lint issues in `doc_generator.py`, `_visibility.py`, `contracts.py` (B007, SIM102, SIM103, F841)
- Pyright errors in generated `.pyi` stubs (147 → 0)

## [0.6.0] - 2026-02-20

### Added

- **Intelligent Codegen**: Type-driven inference engine replaces hard-coded lookup tables for aliases, field policies, extras, and parent references
- **Code IR**: Structured intermediate representation (`code_ir.py`) is now the sole emission path for `.py`, `.pyi`, and test scaffolds
- **Auto-generating README**: `README.template.md` + `readme_generator.py` produce `README.md` with live Mermaid diagrams and verified quick-start code
- **Concept harvesting**: `concepts_generator.py` compiles architectural theory into `architecture-and-concepts.md`
- **Visual cookbooks**: Cookbook recipes execute in a sandbox to auto-render Mermaid architecture DAGs
- **Semantic API reference**: Methods grouped by category (Core Configuration, Callbacks, Control Flow) with inline code examples from docstrings
- **Context engineering**: `Agent.context()`, `C` module (context transforms), `S.capture()` for history-to-state bridging
- **Visibility inference**: `VisibilityPlugin` and event visibility analysis
- **Contract checker**: Cross-channel coherence analysis for inter-agent data flow
- **Transfer control**: `.isolate()` for specialist agents, `.delegate()` for coordinator pattern
- **Structured outputs**: `@` operator and `.output_schema()` for Pydantic-enforced JSON output

### Changed

- Code generation pipeline uses `ruff check --fix || true` → `ruff format` → `ruff check` for lint-clean output
- CI codegen steps aligned with justfile pipeline
- Generated imports use isort-compatible grouping (future/stdlib/third-party/first-party)
- `seed.manual.toml` now includes `delegate` extra for seed regeneration resilience

### Fixed

- 145 test failures caused by seed regeneration stripping signatures from auto-inferred extras
- `infer_extras()` now includes `signature` and `doc` fields for list-append extras
- Ruff SIM105, SIM110, SIM103, F841, B011, B007 violations across scripts and tests
- Doc generator tests updated to match new semantic category headers

### Removed

- Old string-concatenation code generation functions (16 `gen_*` functions, ~765 lines)
- `--use-ir` CLI flag (IR is now the only path)

## [0.5.2] - 2026-02-18

### Fixed

- Ruff formatting fixes across cookbook examples
- Cookbook code corrections for IR & backends, contracts, DI, and visualization examples

## [0.5.1] - 2026-02-18

### Fixed

- Documentation: renumbered cookbooks 35-48 to avoid collisions with primitives cookbooks (35-43)
- Documentation: updated user guide with IR & backends, middleware, and testing pages
- Documentation: updated existing cookbooks (02, 11, 15, 28, 31) with v4 feature examples
- Codegen sync: regenerated builders, stubs, and API reference for google-adk 1.25.0

## [0.5.0] - 2026-02-18

### Added

- **IR + Backend**: `to_ir()` converts builders to frozen dataclass IR trees; `to_app()` compiles through IR to native ADK App
- **Backend Protocol**: `Backend` protocol with `compile`, `run`, `stream`; `ADKBackend` implementation; `final_text()` helper
- **ExecutionConfig**: `app_name`, `resumable`, `compaction`, `middlewares` configuration
- **Middleware**: `Middleware` protocol with 13 lifecycle hooks, `_MiddlewarePlugin` adapter
- **Built-in Middleware**: `RetryMiddleware` (exponential backoff), `StructuredLogMiddleware` (event capture)
- **Data Contracts**: `.produces(Schema)`, `.consumes(Schema)` for inter-agent data flow
- **Contract Verification**: `check_contracts()` validates sequential data flow at build time
- **ToolConfirmation**: `.tool(fn, require_confirmation=True)` pass-through
- **Resource DI**: `inject_resources()` hides infra params from LLM schema; `.inject()` builder method
- **Mock Testing**: `mock_backend()` for deterministic testing without LLM calls; `AgentHarness` for ergonomic test assertions
- **Graph Visualization**: `.to_mermaid()` generates Mermaid diagrams from IR trees
- New testing module: `adk_fluent.testing` (check_contracts, mock_backend, AgentHarness)
- New DI module: `adk_fluent.di` (inject_resources)
- New viz module: `adk_fluent.viz` (ir_to_mermaid)

## [0.4.0] - 2025-02-17

### Added

- 6 ADK sample ports: LLM Auditor, Financial Advisor, Short Movie, Deep Search, Brand Search, Travel Concierge
- Pipeline operators (`>>`, `* until()`, `@ Schema`) on Deep Search example
- `.sub_agent()` as canonical method for adding sub-agents
- `.include_history()` alias for `include_contents`
- `FanOut.step()` alias for `.branch()` (API consistency with Pipeline/Loop)
- `deprecation_alias` behavior in code generator
- Per-alias `field_docs` support in generator for alias-specific docstrings
- Cookbook #43: primitives showcase (`tap`, `expect`, `gate`, `Route`, `S.*`)
- `py.typed` marker (PEP 561)

### Changed

- `.tool()` docstring clarifies append semantics vs `.tools()` replace
- `.output_schema()` docstring clarifies relationship with `@` operator
- `.tap()` and `.timeout()` docstrings warn about builder type change
- Updated cookbook #07 to use `.sub_agent()` instead of `.member()`

### Deprecated

- `.member()` — use `.sub_agent()` instead (emits `DeprecationWarning`)

## [0.3.1] - 2025-02-17

### Changed

- Migrated CI/CD and project URLs from GitLab to GitHub
- Updated documentation URL to GitHub Pages

## [0.3.0] - 2025-02-16

### Added

- New primitives: `tap`, `expect`, `gate`, `race`, `map_over`, `mock`, `retry_if`, `timeout`
- `Route` builder for deterministic state-based branching
- `S` state transform factories (`pick`, `drop`, `rename`, `default`, `merge`, `transform`, `compute`, `guard`, `log`)
- `Prompt` builder for structured multi-section prompt composition
- `Preset` for reusable configuration bundles
- `@agent` decorator for FastAPI-style agent definition
- `StateKey` typed state descriptors
- Fallback operator `//`
- Function steps via `>> fn`
- Dict routing shorthand `>> {"key": agent}`
- `.proceed_if()` conditional gating
- `.loop_until()` conditional loop exit
- `.inject_context()` for dynamic context injection
- `.static()` for context-cacheable instructions
- `.clone()` and `.with_()` for immutable variants
- `.validate()` and `.explain()` introspection
- `.to_dict()`, `.to_yaml()`, `.from_dict()`, `.from_yaml()` serialization
- `.ask()`, `.stream()`, `.session()`, `.map()` one-shot execution
- `.test()` inline smoke testing
- Cookbook examples 17-42
- Sphinx documentation site with Furo theme
- Generated API reference, migration guide, cookbook docs

## [0.2.0] - 2025-02-15

### Added

- Expression algebra: `>>` (sequence), `|` (parallel), `*` (loop), `@` (typed output)
- Conditional `_if` callback variants
- Variadic callback methods
- `__getattr__` forwarding with typo detection
- `.pyi` type stubs for all builders
- Cookbook examples 01-16

## [0.1.0] - 2025-02-14

### Added

- Initial release
- `Agent`, `Pipeline`, `FanOut`, `Loop` fluent builders
- 130+ auto-generated builders from ADK Pydantic schemas
- Code generator pipeline: scanner -> seed_generator -> generator
- justfile development workflow
- CI/CD with GitHub Actions
- PyPI publishing via Trusted Publishing (OIDC)

[0.1.0]: https://github.com/vamsiramakrishnan/adk-fluent/releases/tag/v0.1.0
[0.10.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.9.6...v0.10.0
[0.11.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.10.0...v0.11.0
[0.13.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.12.1...v0.13.0
[0.12.1]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.12.0...v0.12.1
[0.2.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.1.0...v0.2.0
[0.3.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.2.0...v0.3.0
[0.3.1]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.3.0...v0.3.1
[0.4.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.3.1...v0.4.0
[0.5.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.4.0...v0.5.0
[0.5.1]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.5.0...v0.5.1
[0.5.2]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.5.1...v0.5.2
[0.6.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.5.2...v0.6.0
[0.7.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.6.0...v0.7.0
[0.8.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.7.0...v0.8.0
[0.9.1]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.8.0...v0.9.1
[0.9.2]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.9.1...v0.9.2
[0.9.3]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.9.2...v0.9.3
[0.9.4]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.9.3...v0.9.4
[0.9.5]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.9.4...v0.9.5
[0.9.6]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.9.5...v0.9.6
