# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.1] - 2026-02-27

### Added

- **Copy-on-Write frozen builders** (#7): Composition operators (`>>`, `|`, `*`, `@`, `//`) and `to_app()` now freeze the builder; subsequent mutations automatically fork a new clone. Backwards compatible — unfrozen chains still mutate in place.
- **`__dir__` override** (#8): `dir(Agent("x"))` now includes all fluent method names (aliases, callbacks, ADK model fields) for REPL/IDE autocomplete.
- **`BuilderError` exception** (#9): `.build()` failures now raise a structured `BuilderError` with per-field error messages instead of raw 30-line pydantic tracebacks. Exported from `adk_fluent`.
- **`.native(fn)` escape hatch** (#10): Register post-build hooks that receive the raw ADK object, allowing direct mutation without abstraction lock-in. Multiple hooks chain in order.
- **Rich `.explain()` output** (#11): `explain()` now renders a box-drawing tree via `rich` when installed, with plain-text fallback. New `inspect()` method shows full config values. `rich` added as optional dependency (`pip install adk-fluent[rich]`).
- **`adk-fluent visualize` CLI** (#12): New CLI tool renders any builder as a Mermaid diagram. Supports `--format html|mermaid`, `--var`, `--output`, and auto-detection of BuilderBase instances in a module.
- **Autocomplete stress tests** (#13): Pyright subprocess tests verify type resolution for chained methods, `.build()` return type, unknown method errors, and operator result types.
- **`typecheck-core` target** (#18): New justfile target runs pyright on hand-written code only. CI now runs both stub and core type checking.

### Changed

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
