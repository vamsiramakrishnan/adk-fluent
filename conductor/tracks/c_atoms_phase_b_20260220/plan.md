# Implementation Plan: v5.1 Phase B — C Atoms (No LLM)

## Phase 1: SELECT Primitives
- [ ] Task: Implement `C.select()`
    - [ ] Write failing tests in `tests/manual/test_c_select.py`
    - [ ] Implement `CSelect` transform and metadata filtering logic in `_context.py`
    - [ ] Verify tests pass
- [ ] Task: Implement `C.recent()`
    - [ ] Write failing tests in `tests/manual/test_c_recent.py`
    - [ ] Implement `CRecent` transform and time-decay logic in `_context.py`
    - [ ] Verify tests pass
- [ ] Task: Conductor - User Manual Verification 'Phase 1: SELECT' (Protocol in workflow.md)

## Phase 2: COMPRESS Primitives
- [ ] Task: Implement `C.compact()` and `C.dedup()`
    - [ ] Write failing tests in `tests/manual/test_c_compaction.py`
    - [ ] Implement `CCompact` and `CDedup` logic in `_context.py`
    - [ ] Verify tests pass
- [ ] Task: Implement `C.truncate()` and `C.project()`
    - [ ] Write failing tests in `tests/manual/test_c_projection.py`
    - [ ] Implement `CTruncate` and `CProject` logic in `_context.py`
    - [ ] Verify tests pass
- [ ] Task: Conductor - User Manual Verification 'Phase 2: COMPRESS' (Protocol in workflow.md)

## Phase 3: BUDGET & PROTECT Primitives
- [ ] Task: Implement `C.budget()`, `C.priority()`, and `C.fit()`
    - [ ] Write failing tests in `tests/manual/test_c_budget.py`
    - [ ] Implement budget-aware assembly logic in `_context.py`
    - [ ] Verify tests pass
- [ ] Task: Implement `C.fresh()` and `C.redact()`
    - [ ] Write failing tests in `tests/manual/test_c_protect.py`
    - [ ] Implement time-based pruning and regex redaction logic in `_context.py`
    - [ ] Verify tests pass
- [ ] Task: Conductor - User Manual Verification 'Phase 3: BUDGET & PROTECT' (Protocol in workflow.md)

## Phase 4: Composition & Operator Rules
- [ ] Task: Refine `+` and `|` operators
    - [ ] Write failing tests for complex composition in `tests/manual/test_c_composition.py`
    - [ ] Implement operator type rules and `CPipe` execution logic in `_context.py`
    - [ ] Verify tests pass
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Composition' (Protocol in workflow.md)
