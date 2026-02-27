# Project Tracks

This file tracks all major tracks for the project. Each track has its own detailed plan in its respective folder.

> **Last updated:** 2026-02-27 — status audit against codebase

______________________________________________________________________

## Core Version Phases

- [x] **v3 Phase 1: Fix Disfluencies** — COMPLETE
  *Plan: [docs/plans/2026-02-18-v3-phase1-disfluencies.md](../docs/plans/2026-02-18-v3-phase1-disfluencies.md)*
- [x] **v4 Phase 2: Seed-Based IR + Backend Protocol** — COMPLETE
  *Plan: [docs/plans/2026-02-18-v4-phase2-ir-backend.md](../docs/plans/2026-02-18-v4-phase2-ir-backend.md)*
- [x] **v4 Phase 3: Middleware Protocol** — COMPLETE
  *Plan: [docs/plans/2026-02-18-v4-phase3-middleware.md](../docs/plans/2026-02-18-v4-phase3-middleware.md)*
- [x] **v4 Phase 4: New Capabilities** — COMPLETE
  *Plan: [docs/plans/2026-02-18-v4-phase4-capabilities.md](../docs/plans/2026-02-18-v4-phase4-capabilities.md)*

## v5.1 Context Engineering Phases

- [x] **v5.1 Phase A: Foundation** — COMPLETE
  *S.capture(), C module core (9 primitives), Agent.context(), event visibility, cross-channel contracts, memory integration, IR-first build, OTel enrichment*
  *Plan: [docs/plans/2026-02-18-v51-context-engineering.md](../docs/plans/2026-02-18-v51-context-engineering.md)*
- [x] **v5.1 Phase B: C Atoms (No LLM)** — COMPLETE
  *SELECT, COMPRESS, BUDGET, PROTECT primitives + composition operators (`+`/`|`)*
  *Plan: [./tracks/c_atoms_phase_b_20260220/](./tracks/c_atoms_phase_b_20260220/)*
- [x] **v5.1 Phase C: C Atoms (LLM-Powered)** — COMPLETE
  *summarize, relevant, extract, distill, validate, fit (with LLM caching)*
  *Plan: [docs/plans/2026-02-18-v51-context-engineering.md](../docs/plans/2026-02-18-v51-context-engineering.md)*
- [ ] **v5.1 Phase D: Scratchpads + Sugar** — NOT STARTED
  *C.notes(), C.rolling(), C.from_agents_windowed(), C.user(), C.manus_cascade(), note lifecycle*
- \[~\] **v5.1 Phase E: Typed State (StateSchema)** — PARTIAL
  *StateKey with scope prefixes implemented; StateSchema base class, CapturedBy annotation, typed contract checking, and IDE autocomplete still needed*

## Parallel Tracks

- [x] **100x Features** — COMPLETE
  *BuilderBase mixin, operators, repr, validate, serialization, presets, structured output, map, decorator syntax*
  *Plan: [docs/plans/2026-02-17-100x-features-plan.md](../docs/plans/2026-02-17-100x-features-plan.md)*
- [x] **ADK Samples Port** — COMPLETE
  *6 samples ported: llm_auditor, financial_advisor, short_movie, deep_search, brand_search, travel_concierge*
  *Plan: [docs/plans/2026-02-17-adk-samples-port-plan.md](../docs/plans/2026-02-17-adk-samples-port-plan.md)*
- [x] **Documentation Publishing** — COMPLETE
  *Sphinx + MyST-Parser + Furo theme + sphinx-design + sphinx-copybutton*
  *Plan: [docs/plans/2026-02-17-documentation-publishing-plan.md](../docs/plans/2026-02-17-documentation-publishing-plan.md)*
- [x] **Ergonomic Depth & Autodocs** — COMPLETE (Phase 1)
  *.ask(), .stream(), .clone(), .test(), .guardrail(), .session(), variadic callbacks, auto-generated docs*
  *Plan: [docs/plans/2026-02-17-ergonomic-depth-and-autodocs-plan.md](../docs/plans/2026-02-17-ergonomic-depth-and-autodocs-plan.md)*
- [x] **Full Auto Seed Generator** — COMPLETE
  *Enhanced scanner, type-driven seed generation, two-seed system (auto + manual), merge support*
  *Plan: [docs/plans/2026-02-17-full-auto-seed-generator-plan.md](../docs/plans/2026-02-17-full-auto-seed-generator-plan.md)*
- [x] **Intelligent Codegen** — COMPLETE (Phase A+B+C)
  *Type-driven inference engine, structured Code IR, content-addressed caching*
  *Plan: [docs/plans/2026-02-18-intelligent-codegen-plan.md](../docs/plans/2026-02-18-intelligent-codegen-plan.md)*
- [x] **API Surface v2** — COMPLETE
  *save_as, stay, no_peers, prelude module, deprecated aliases with warnings*
  *Plan: [docs/plans/2026-02-25-api-surface-v2-plan.md](../docs/plans/2026-02-25-api-surface-v2-plan.md)*

## Future (Not Started)

- [ ] **Pattern Library (Phase 2)** — presets like RAGAgent, RouterAgent, middleware chains
- [ ] **Declarative Definitions (Phase 3)** — YAML-based agent definitions, operator overloading
