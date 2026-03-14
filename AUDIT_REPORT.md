# Repository Audit Report — adk-fluent

> **Auditor persona**: Expert Developer Advocate & Staff Engineer
> **Date**: 2026-03-14
> **Scope**: Full codebase vs. documentation drift analysis + DX gap assessment
> **Version audited**: 0.11.0 (google-adk 1.25.0)

---

## Executive Summary

adk-fluent is a **remarkably well-engineered** project with production-grade CI/CD, comprehensive test infrastructure, and extensive user guides. However, a significant gap exists between the *actual* API surface (which is rich and mature) and the *documented* API surface (which understates the library's capabilities). The auto-generated `CLAUDE.md` and `README.md` cover roughly **60-70% of the real API**, leaving many powerful features as "ghost code." This audit identifies 8 critical drift items, 12 DX friction points, and 9 polish recommendations.

---

## Task 1: Code vs. Documentation Drift

### 🚨 Critical Drift

#### 1. CLAUDE.md massively underdocuments the Agent builder API

**Severity**: Critical — LLM-assisted development (Claude Code, Cursor, Copilot) relies on CLAUDE.md as the ground truth.

The CLAUDE.md "Agent builder methods" section lists ~30 methods. The actual `BuilderBase` and `Agent` classes expose **60+ methods**. Entire categories are missing:

| Category | Missing methods |
|---|---|
| Execution | `.ask()`, `.ask_async()`, `.stream()`, `.events()`, `.map()`, `.map_async()` — listed in a later section but not in the method table |
| Introspection | `.diagnose()`, `.doctor()`, `.data_flow()`, `.llm_anatomy()`, `.inspect()`, `.to_dict()`, `.to_yaml()` |
| Testing | `.eval()`, `.eval_suite()` |
| Flow control | `.loop_until()`, `.loop_while()`, `.until()`, `.proceed_if()`, `.timeout()`, `.dispatch()` |
| Visibility | `.show()`, `.hide()`, `.transparent()`, `.filtered()`, `.annotated()` |
| Memory | `.memory()`, `.memory_auto_save()` |
| Transfer control | `.isolate()`, `.stay()`, `.no_peers()` |
| Configuration | `.strict()`, `.unchecked()`, `.use()`, `.middleware()`, `.inject()`, `.native()`, `.debug()` |
| Contracts | `.produces()`, `.consumes()` |
| Prompt | `.prepend()`, `.global_instruct()`, `.generate_content_config()` |
| Advanced | `.planner()`, `.code_executor()`, `.tool_schema()`, `.callback_schema()`, `.prompt_schema()`, `.artifact_schema()` |

**Impact**: An AI coding assistant using CLAUDE.md as context will not suggest `.diagnose()`, `.doctor()`, `.eval()`, `.memory()`, or `.timeout()` — features that could save developers hours of debugging.

**Fix**: Regenerate CLAUDE.md to include all public methods, or restructure into "Core", "Advanced", and "Introspection" tiers.

---

#### 2. Ghost code: `E` (Evaluation), `G` (Guards) namespaces undocumented in CLAUDE.md

The `__init__.py` exports two entire namespace modules that receive **zero mention** in CLAUDE.md:

- **`E`** — Evaluation suite builder (`E.case()`, `E.criterion()`, `EvalSuite`, `EvalReport`, `ComparisonReport`, `EPersona`)
- **`G`** — Guard composition (`G.guard()`, `GComposite`, `GuardViolation`, `PIIDetector`, `ContentJudge`)

These are fully implemented, tested, and exported from the package. A developer reading CLAUDE.md would never know they exist.

**Fix**: Add `E` and `G` sections to the "Namespace modules" documentation in CLAUDE.md.

---

#### 3. Ghost code: Expression primitives underdocumented

CLAUDE.md documents the expression operators (`>>`, `|`, `*`, `//`, `@`) but omits the **function-level primitives** that power them:

- `until(predicate, max=)` — documented only in the `*` operator example
- `tap(fn)` / `expect(fn)` — inline transformation, not documented
- `map_over(key)` — map agent over list items, not documented
- `gate(predicate)` — conditional execution, not documented
- `race(*agents)` — first-to-complete race, not documented
- `dispatch(...)` / `join()` — background task primitives, not documented

These are all exported from `__init__.py` and `prelude.py`.

**Fix**: Add an "Expression primitives" section to CLAUDE.md.

---

#### 4. Ghost code: Source/Inbox/StreamRunner pattern undocumented

The `__init__.py` exports `Source`, `Inbox`, and `StreamRunner` from dedicated modules (`source.py`, `stream.py`). These appear to support an event-driven streaming pattern. They receive zero documentation in CLAUDE.md, README, or user guides (no `docs/user-guide/streaming.md` exists, only `execution.md`).

**Fix**: Document the streaming/source pattern or mark as experimental.

---

#### 5. CLAUDE.md documents `.save_as()` as deprecated but CHANGELOG says it was "retained as canonical"

CLAUDE.md states:
> Use `.writes()` not deprecated `.save_as()` / `.output_key()`

But CHANGELOG v0.10.0 explicitly says:
> `save_as()` retained as canonical (`.outputs()` deprecated in v0.8.0)

This is a direct contradiction. A developer following CLAUDE.md guidance would unnecessarily migrate away from `.save_as()`.

**Fix**: Align CLAUDE.md with the CHANGELOG. If `.save_as()` is canonical, remove it from the deprecated list. If `.writes()` is preferred, update the CHANGELOG.

---

#### 6. `__init__.py` exports private symbols

The `__all__` list in `__init__.py` exports **47+ private symbols** (prefixed with `_`):

```
_compile_context_spec, _compile_prompt_spec, _FnStepBuilder, _CaptureBuilder,
_ArtifactBuilder, _FallbackBuilder, _TapBuilder, _MapOverBuilder, _GateBuilder,
_RaceBuilder, _JoinBuilder, _fn_step, _LoopHookAgent, _FanOutHookAgent,
_dispatch_tasks, _global_task_budget, _middleware_dispatch_hooks, _topology_hooks,
_execution_mode, _DEFAULT_MAX_TASKS, _add_artifacts, _add_tool, _add_tools,
_agent_to_ir, _pipeline_to_ir, _fanout_to_ir, _loop_to_ir, _show_agent,
_hide_agent, _add_memory, _add_memory_auto_save, _isolate_agent, _stay_agent,
_no_peers_agent, _eval_inline, _eval_suite, _instruct_with_guard,
_context_with_guard, _guard_dispatch, _MiddlewarePlugin, _agent_matches,
_ScopedMiddleware, _ConditionalMiddleware, _SingleHookMiddleware, _trace_context,
_ConfirmWrapper, _TimeoutWrapper, _CachedWrapper, _TransformWrapper
```

These are implementation internals leaking into the public API. While the "never import from internal modules" rule in CLAUDE.md covers `_base` and `_context`, exporting private symbols from `__init__.py` contradicts this intent.

**Impact**: Autocomplete is polluted with 47+ symbols users should never touch. External code could depend on internals that may change without notice.

**Fix**: Remove `_`-prefixed symbols from `__all__`. If some are needed for the generator pipeline, use a separate `_internals` namespace.

---

#### 7. pyproject.toml classifier mismatch: "Alpha" vs badge "Beta"

```toml
# pyproject.toml
"Development Status :: 3 - Alpha"
```

```markdown
# README.md badge
[![Status](https://img.shields.io/badge/status-beta-yellow)]
```

The package metadata says Alpha while the README badge says Beta.

**Fix**: Align to one status. Given 50+ cookbook examples, 108 manual tests, and a versioned changelog, "Beta" (`Development Status :: 4 - Beta`) is more accurate.

---

#### 8. Ghost docs: `T.search(registry)` documented but actual API is `T.toolset()`

CLAUDE.md documents:
```
T.search(registry)           — BM25-indexed dynamic loading
```

But the CHANGELOG v0.9.6 and `__init__.py` exports show `SearchToolset` and `ToolRegistry` as separate classes, with `T.toolset()` being the factory method for wrapping toolsets. The `T.search()` factory may exist but `T.toolset()` is the canonical method per the CHANGELOG.

**Fix**: Verify `T.search()` still exists and update CLAUDE.md to reflect the current API.

---

### 🚧 DX Friction (The "Duct Tape")

#### 1. No `docker-compose.yml` or devcontainer for zero-setup onboarding

The CONTRIBUTING.md lists prerequisites (Python 3.11+, `just`, `uv`) but doesn't provide a container-based alternative. A new contributor on Windows or without `just` installed faces multiple setup steps before they can run tests.

**Recommendation**: Add a `.devcontainer/devcontainer.json` for VS Code/GitHub Codespaces with all tools pre-installed. Time-to-first-test should be < 2 minutes.

---

#### 2. No architecture diagram in README or docs landing page

The `docs/user-guide/architecture-and-concepts.md` exists but the README jumps straight to API examples. A new developer has no visual mental model of:
- How builders relate to native ADK objects
- The code generation pipeline (scanner → seed → generator)
- The namespace module hierarchy (S/C/P/A/M/T/E/G)

**Recommendation**: Add a Mermaid architecture diagram to the README showing the builder → ADK object flow and the codegen pipeline. The library already has `.to_mermaid()` — eat your own dog food.

---

#### 3. Bus factor of 1

`CODEOWNERS` shows only `@vamsiramakrishnan`. Every file in the repository has a single owner. The CONTRIBUTING.md doesn't mention co-maintainers, review cadence, or succession planning.

**Recommendation**: Document the review process even for a solo maintainer. Consider adding a second reviewer for the codegen pipeline specifically.

---

#### 4. No "Common Issues" or FAQ beyond error reference

The `docs/user-guide/error-reference.md` catalogs errors from the library itself, but there's no troubleshooting guide for:
- `google-adk` version conflicts
- API key setup issues (AI Studio vs Vertex AI)
- `adk web` integration gotchas
- Common import errors when using virtual environments

**Recommendation**: Add a `docs/user-guide/troubleshooting.md` with real-world setup issues.

---

#### 5. CONTRIBUTING.md warns "don't edit generated files" but doesn't make it fail-safe

The CONTRIBUTING.md states:
> **Important: Never edit auto-generated files directly**

But there's no git hook or CI check that *prevents* accidental edits to generated files. The `just check-gen` command verifies idempotency, but a contributor could still push edits that pass until someone runs regeneration.

**Recommendation**: Add a pre-commit hook that rejects changes to files listed in `.gitattributes` as `linguist-generated=true`.

---

#### 6. 534 symbols in `__all__` — overwhelming for discovery

The `__init__.py` exports 534 symbols. Even with IDE autocomplete, this creates a wall of noise. The `prelude.py` exists as a curated subset but isn't prominently documented.

**Recommendation**: Document `prelude.py` as the recommended import path for interactive/exploratory use. Consider a "Quick Reference Card" showing the 20 most-used imports.

---

#### 7. Test coverage threshold is 60% — low for a library

```toml
[tool.coverage.report]
fail_under = 60
```

For a library that generates production agent configurations, 60% coverage is a low bar. Critical paths in `_base.py` (2100+ lines) and `_context.py` (83KB) should have higher coverage expectations.

**Recommendation**: Raise to 80% with per-module thresholds for core modules.

---

#### 8. No migration guide between versions

The CHANGELOG documents breaking changes (e.g., verb harmonization in v0.10.0), but there's no standalone migration guide. A user upgrading from 0.9.x to 0.10.x must read the full CHANGELOG to find rename mappings.

**Recommendation**: Add `docs/user-guide/migration.md` with version-to-version upgrade instructions and `sed` commands for common renames.

---

#### 9. `quickstart.py` not referenced from README

The CHANGELOG v0.11.0 mentions a "Standalone `quickstart.py`" was added, but it's not linked from the README's Quick Start section.

**Recommendation**: Link or inline the quickstart script from the README.

---

#### 10. No runnable example without API key

Every example requires a real `gemini-2.5-flash` API key. There's no way to run the Quick Start with `.mock()` to verify the library works before configuring credentials.

**Recommendation**: Add a "Try without an API key" section using `.mock()`:
```python
agent = Agent("demo", "gemini-2.5-flash").instruct("Hello").mock(["Hi there!"])
print(agent.ask("Hello"))  # => Hi there!
```

---

#### 11. `just setup` doesn't verify prerequisites

`just setup` runs `uv sync` and `pre-commit install` but doesn't check if `uv` or `pre-commit` are installed first. A new contributor will get a cryptic error.

**Recommendation**: Add a `just doctor` command that checks for Python 3.11+, `uv`, `just`, and `pre-commit`.

---

#### 12. No changelog entry for unreleased changes

The CHANGELOG doesn't have an `[Unreleased]` section header for tracking in-progress changes, which is part of the Keep a Changelog standard.

**Recommendation**: Add an `[Unreleased]` section at the top of CHANGELOG.md.

---

### ✨ World-Class Polish Recommendations

#### 1. Add a "Cheat Sheet" one-pager

Create a single-page `docs/cheatsheet.md` with every operator, namespace method, and builder method in a dense, copy-pasteable format. Many developers will print/bookmark this as their daily reference.

#### 2. Generate CLAUDE.md from the actual code, not just the manifest

The current `llms_generator.py` generates CLAUDE.md from `manifest.json` + `seed.toml`, which describes the *generated* builders but misses the *hand-written* API surface (execution methods, introspection, testing, primitives). The generator should also scan the hand-written modules.

#### 3. Add inline `# Example:` comments in CLAUDE.md method tables

Each method in the CLAUDE.md tables should have a minimal inline example:
```
.timeout(seconds)            — wrap with time limit → Agent("a").timeout(30)
.mock(responses)             — canned LLM responses → Agent("a").mock(["Hi"])
```

#### 4. Add a "What's New in 0.11" section to docs landing page

The docs site should highlight recent additions (Artifact Phase 2+3, verb harmonization) to help returning users catch up.

#### 5. Publish a `ARCHITECTURE.md` with the codegen pipeline diagram

The codegen pipeline (scanner → seed → generator → builders + stubs + tests) is this project's most unique architectural decision. Document it as a standalone `ARCHITECTURE.md` in the repo root.

#### 6. Add OpenGraph/social preview image

The docs `conf.py` has `sphinxext-opengraph` configured but no custom `og:image`. A branded social card would improve link previews on Twitter/LinkedIn/Slack.

#### 7. Add a "Comparison with LangChain/CrewAI/AutoGen" section

The `docs/user-guide/comparison.md` exists but it's unclear if it covers competitive positioning. Developers evaluating adk-fluent want a clear "when to use this vs. X" matrix.

#### 8. Add property-based tests for operator algebra

The library claims operators are "immutable" and "copy-on-write." These algebraic properties are perfect for Hypothesis property-based testing:
```python
@given(st.builds(Agent, st.text()))
def test_clone_identity(agent):
    assert agent.clone("copy")._cfg == agent._cfg
```

#### 9. Pin the ADK badge to the actual tested range

The README badge says `≥1.20` but `pyproject.toml` says `>=1.20.0` and CI pins to `1.25.0`. The badge should reflect the tested range: `1.20–1.25`.

---

## Task 2: "Duct Tape" Gap Analysis Summary

| DX Dimension | Grade | Notes |
|---|---|---|
| **Onboarding** | B+ | Excellent README and install, but no zero-config container, no mock-only quickstart |
| **Architecture** | B | Good conceptual docs, but no visual diagram in README, no standalone ARCHITECTURE.md |
| **Standards** | A- | CONTRIBUTING.md, PR template, issue templates all present and thorough |
| **Testing** | B+ | 108 manual tests + cookbooks, but 60% coverage bar is low |
| **Troubleshooting** | B- | Error reference is good, but no FAQ for environment/setup issues |
| **API Documentation** | C+ | User guides are excellent, but CLAUDE.md (the LLM context) is **severely incomplete** |
| **CI/CD** | A | 7-stage pipeline, hermetic builds, trusted publishing — production-grade |
| **Code Quality** | A | ruff, pyright strict, pre-commit, golden tests — exceptional |

**Overall DX Grade: B+**

The project's infrastructure and code quality are A-tier. The gap to "world-class" is almost entirely in **documentation completeness** — specifically, the auto-generated CLAUDE.md underrepresenting the actual API, and the absence of a visual architecture overview. Fix the CLAUDE.md generator to scan hand-written modules, add an architecture diagram, and this project jumps to A-tier.

---

## Priority Action Items

| Priority | Action | Effort | Impact |
|---|---|---|---|
| P0 | Fix CLAUDE.md generator to include hand-written API surface | Medium | Critical — affects all LLM-assisted development |
| P0 | Resolve `.save_as()` vs `.writes()` contradiction | Low | Prevents developer confusion |
| P0 | Remove `_`-prefixed symbols from `__all__` | Low | Cleans up public API |
| P1 | Document `E` and `G` namespace modules | Medium | Unlocks testing/guard features for users |
| P1 | Add architecture diagram to README | Low | Improves first-impression comprehension |
| P1 | Update pyproject.toml classifier to Beta | Trivial | Aligns metadata with actual maturity |
| P1 | Add `.devcontainer/devcontainer.json` | Low | Zero-setup onboarding |
| P2 | Add troubleshooting guide | Medium | Reduces support burden |
| P2 | Add migration guide | Medium | Eases version upgrades |
| P2 | Add mock-only quickstart example | Low | Try-before-you-configure |
| P2 | Raise coverage threshold to 80% | Medium | Higher confidence in releases |
| P3 | Add cheat sheet one-pager | Low | Developer productivity |
| P3 | Add social preview image | Trivial | Better link sharing |

---

## Addendum: SDK-Specific Deep Audit

### Type Stubs & IDE Autocomplete (`.pyi` files)

**Verdict: Production-ready. No IDE-breaking issues found.**

| Aspect | Status | Details |
|---|---|---|
| PEP 561 compliance | PASS | `py.typed` marker present, `"Typing :: Typed"` classifier set |
| Stub coverage | PASS | 9 generated modules fully stubbed (agent, workflow, tool, config, runtime, service, plugin, executor, planner) |
| Fluent chaining | PASS | 515/792 methods (65%) return `Self` — remaining 35% are constructors, `.build()`, and terminal methods |
| `Any` returns | PASS | Only 7 methods return `Any` — all are intentional terminal methods (`.session()`, `.eval()`, `.to_ir()`) that exit the builder chain |
| Package distribution | PASS | Hatchling config includes `.pyi` files in both wheel and sdist |
| Hand-written modules | PASS | Type-checked at source level via Pyright in strict mode (no stubs needed) |

**Method chaining works correctly in IDEs:**
```python
# Full autocomplete preserved through the chain:
agent = (
    Agent("helper", "gemini-2.5-flash")
    .instruct("You are helpful.")        # returns Self ✓
    .tool(search_fn)                      # returns Self ✓
    .memory("preload")                    # returns Self ✓
    .build()                              # returns LlmAgent (chain terminates) ✓
)
```

**One improvement opportunity:** The `.pyi` stubs are generated from the manifest and accurately reflect generated code, but they don't cover hand-written `BuilderBase` methods (since those are type-checked at source level). This means IDE hover-docs for inherited methods like `.validate()`, `.explain()`, `.diagnose()` show source-level docstrings — which is correct behavior, not a bug.

---

### Codegen Pipeline Documentation

**Verdict: A- overall. Excellent happy-path docs, but contributor edge cases and format references need work.**

The codegen pipeline (`scanner.py` → `manifest.json` → `seed.toml` → `generator.py` → builders + stubs + tests) is documented in:
- `docs/contributing/codegen-pipeline.md` — explains the full 5-stage flow (A grade)
- `docs/contributing/adding-builders.md` — how to add extras, renames, optional args (B+ grade)
- `docs/contributing/upstream-impact-analysis.md` — **outstanding** 9-category impact analysis with upgrade runbook (A+ grade)
- `CONTRIBUTING.md` — warns against editing generated files
- `justfile` — `just scan`, `just seed`, `just generate`, `just all`, `just archive`, `just diff`

**What's well-covered:**
- The scanner → seed → generator flow is explained with clear examples
- `just all` runs the complete pipeline in one command
- `just check-gen` verifies generated files are up-to-date (also runs in CI)
- `.gitattributes` marks generated files with `linguist-generated=true`
- `upstream-impact-analysis.md` covers 9 categories of ADK changes with explicit upgrade runbook
- `sync-adk.yml` workflow auto-syncs weekly with auto-PR creation

**What's missing or unclear:**

| Gap | Grade | Impact |
|---|---|---|
| **CONTRIBUTING.md doesn't mention sync-adk.yml** or the upgrade runbook | Critical | New contributors don't know about automatic weekly ADK sync or how to handle manual upgrades |
| **Seed manifest format undocumented** — `[global]` field policy settings (`skip_fields`, `additive_fields`, `list_extend_fields`) have no reference doc | F | Contributors must reverse-engineer from `seed.toml` source |
| **upstream-impact-analysis.md not linked from CONTRIBUTING.md** | High | Outstanding document buried in docs/ — contributors won't find it |
| No "add a new namespace module" guide | Medium | Adding a hand-written module (like `G`) has no documented process |
| Classifier rules undocumented | Medium | Why `VertexAiSearchTool` gets a builder but `EventLog` doesn't is tribal knowledge |
| Generator error messages not cataloged | Low | When the generator fails, error messages aren't in error-reference.md |
| No end-to-end example of adding a new ADK class | Low | Hypothetical walkthrough would help new contributors |

**Recommended addition to CONTRIBUTING.md:**
```markdown
### When Google Releases a New ADK Version

The adk-fluent pipeline automatically stays in sync via a weekly CI workflow (sync-adk.yml).
For manual upgrades:

1. Save current state: `just archive`
2. Update: `pip install --upgrade google-adk`
3. Scan: `just scan`
4. Review: `just diff`
5. Regenerate: `just all`
6. Verify: `just test && just typecheck`

See [Upstream ADK Impact Analysis](docs/contributing/upstream-impact-analysis.md) for details.
```

---

### Deprecated Method Handling

**Verdict: Excellent. All 10 deprecated methods issue `DeprecationWarning` and redirect correctly.**

Verified deprecated methods with proper warnings:
- `.delegate()` → `.agent_tool()`
- `.guardrail()` → `.guard()`
- `.history()` / `.include_history()` → `.context()`
- `.inject_context()` → `.prepend()`
- `.input_schema()` → `.accepts()`
- `.output_key()` / `.outputs()` → `.writes()`
- `.output_schema()` → `.returns()`
- `.retry_if()` → `.loop_while()`
- `.save_as()` → `.writes()` (but see Critical Drift #5 — CHANGELOG contradiction)
- `.static_instruct()` → `.static()`

---

### Namespace Module Verification

**All 6 documented namespace modules verified against source code:**

| Module | Documented methods | Actual methods | Status |
|---|---|---|---|
| **S** (State) | 11 | 26+ | Underdocumented — missing `S.capture()`, `S.identity()`, `S.accumulate()`, `S.counter()`, `S.history()`, `S.validate()`, `S.require()`, `S.flatten()`, `S.unflatten()`, `S.zip()`, `S.group_by()`, `S.log()` |
| **C** (Context) | 12 | 28+ | Underdocumented — missing `C.default()`, `C.select()`, `C.recent()`, `C.compact()`, `C.dedup()`, `C.project()`, `C.priority()`, `C.fit()`, `C.fresh()`, `C.redact()`, `C.extract()`, `C.distill()`, `C.validate()`, `C.notes()`, `C.write_notes()`, `C.manus_cascade()` |
| **P** (Prompt) | 10 | 17+ | Underdocumented — missing `P.reorder()`, `P.only()`, `P.without()`, `P.compress()`, `P.adapt()`, `P.scaffolded()`, `P.versioned()` |
| **A** (Artifacts) | 4 | 17+ | Severely underdocumented — missing batch ops, content transforms, `A.for_llm()`, `A.list()`, `A.version()`, `A.delete()`, `A.when()` |
| **M** (Middleware) | 6 | 22+ | Severely underdocumented — missing `M.circuit_breaker()`, `M.timeout()`, `M.cache()`, `M.fallback_model()`, `M.dedup()`, `M.sample()`, `M.trace()`, `M.metrics()`, `M.before_agent()`, `M.after_agent()`, `M.on_loop()`, `M.on_timeout()`, `M.on_route()`, `M.on_fallback()` |
| **T** (Tools) | 3 | 13+ | Severely underdocumented — missing `T.mock()`, `T.confirm()`, `T.timeout()`, `T.cache()`, `T.mcp()`, `T.openapi()`, `T.transform()`, `T.toolset()`, `T.schema()` |

**Aggregate: CLAUDE.md documents 46 namespace methods out of 123+ actual methods (37% coverage).**

This is the single biggest documentation gap in the repository.

---

### Undocumented Callback Methods

Two callback methods exist in `agent.py` but appear in no documentation:
- `.on_model_error(fn)` — agent.py line ~390
- `.on_tool_error(fn)` — agent.py line ~404

These are valuable for error handling patterns but invisible to users.

---

### Revised Priority Action Items (SDK-Specific)

| Priority | Action | Effort | Impact |
|---|---|---|---|
| P0 | Update CLAUDE.md namespace sections — 37% coverage is unacceptable for LLM context | High | Unlocks 77 undocumented namespace methods |
| P0 | Document `E` and `G` namespaces in CLAUDE.md | Medium | Two entire feature areas invisible |
| P0 | Resolve `.save_as()` canonical status contradiction | Low | Developer confusion |
| P1 | Document `.on_model_error()` and `.on_tool_error()` callbacks | Low | Error handling patterns |
| P1 | Document `sync-adk.yml` workflow for contributors | Low | Contributor onboarding |
| P1 | Add `seed.toml` override format documentation | Medium | Codegen contributor experience |
| P1 | Add "Handling New ADK Releases" section to CONTRIBUTING.md | Low | Contributors can't find upgrade runbook |
| P1 | Link upstream-impact-analysis.md from CONTRIBUTING.md | Trivial | Outstanding doc is buried |
| P1 | Create seed manifest format reference | Medium | Field policy rules completely undocumented (grade F) |
| P2 | Document classifier rules (which classes get builders) | Medium | Tribal knowledge |
| P2 | Catalog generator error messages in error-reference.md | Medium | Developer self-service |
| P2 | Add "add a new namespace module" contributor guide | Medium | Scaling the project |

---

*Report generated by Claude Code audit — session `llAD5`*
