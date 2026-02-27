# Implementation Plan: v5.1 Phase B — C Atoms (No LLM)

> **Status: COMPLETE** (2026-02-27 audit) — All 4 phases implemented. 9 primitives + composition operators. Tests: `tests/manual/test_c_phase_b.py` (776 lines). Implementation: `src/adk_fluent/_context.py` (lines 240-433).

## Phase 1: SELECT Primitives

- [x] Task: Implement `C.select()`
  - [x] Write failing tests in `tests/manual/test_c_select.py`
  - [x] Implement `CSelect` transform and metadata filtering logic in `_context.py`
  - [x] Verify tests pass
- [x] Task: Implement `C.recent()`
  - [x] Write failing tests in `tests/manual/test_c_recent.py`
  - [x] Implement `CRecent` transform and time-decay logic in `_context.py`
  - [x] Verify tests pass
- [x] Task: Conductor - User Manual Verification 'Phase 1: SELECT' (Protocol in workflow.md)

## Phase 2: COMPRESS Primitives

- [x] Task: Implement `C.compact()` and `C.dedup()`
  - [x] Write failing tests in `tests/manual/test_c_compaction.py`
  - [x] Implement `CCompact` and `CDedup` logic in `_context.py`
  - [x] Verify tests pass
- [x] Task: Implement `C.truncate()` and `C.project()`
  - [x] Write failing tests in `tests/manual/test_c_projection.py`
  - [x] Implement `CTruncate` and `CProject` logic in `_context.py`
  - [x] Verify tests pass
- [x] Task: Conductor - User Manual Verification 'Phase 2: COMPRESS' (Protocol in workflow.md)

## Phase 3: BUDGET & PROTECT Primitives

- [x] Task: Implement `C.budget()`, `C.priority()`, and `C.fit()`
  - [x] Write failing tests in `tests/manual/test_c_budget.py`
  - [x] Implement budget-aware assembly logic in `_context.py`
  - [x] Verify tests pass
- [x] Task: Implement `C.fresh()` and `C.redact()`
  - [x] Write failing tests in `tests/manual/test_c_protect.py`
  - [x] Implement time-based pruning and regex redaction logic in `_context.py`
  - [x] Verify tests pass
- [x] Task: Conductor - User Manual Verification 'Phase 3: BUDGET & PROTECT' (Protocol in workflow.md)

## Phase 4: Composition & Operator Rules

- [x] Task: Refine `+` and `|` operators
  - [x] Write failing tests for complex composition in `tests/manual/test_c_composition.py`
  - [x] Implement operator type rules and `CPipe` execution logic in `_context.py`
  - [x] Verify tests pass
- [x] Task: Conductor - User Manual Verification 'Phase 4: Composition' (Protocol in workflow.md)
