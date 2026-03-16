# adk-fluent Tech Debt Audit

**Date**: 2026-03-16
**Scope**: Full `src/adk_fluent/` codebase — 5 audit passes covering _base.py, backends, testing/compile, namespace modules, and cross-cutting concerns.

---

## Executive Summary

The codebase is well-maintained: zero TODO/FIXME comments, clean deprecation paths with warnings, and consistent patterns across modules. The main debt clusters are:

| Category | Severity | Count |
|----------|----------|-------|
| Unimplemented backend methods | HIGH | 3 |
| Composition operator asymmetry | HIGH | 6 namespaces |
| Monolithic contract checker (812 lines) | MEDIUM | 1 function |
| Broad exception handling | MEDIUM | 10+ sites |
| Type annotation gaps | MEDIUM | 5+ modules |
| Code duplication (tree walk, middleware, identifiers) | MEDIUM | 5 sites |
| Silent failure patterns | MEDIUM | 5 sites |
| Deprecated methods to remove | LOW | 13 methods |
| Placeholder compile passes | LOW | 1 |

---

## HIGH Severity

### H1: ADK Backend `run()`/`stream()` not implemented

**File**: `backends/adk/__init__.py:117-129`

Both `run()` and `stream()` raise `NotImplementedError`. Users must go through `_helpers.py` which is tightly coupled. This is the only backend where the core execution path doesn't work.

**Fix**: Implement `run()`/`stream()` in ADKBackend using session service + API key, or document this as intentional compile-only backend.

### H2: Temporal worker only generates sequential workflows

**File**: `backends/temporal_worker.py:458-460`

Comment admits: "For now, generate a simple sequential workflow. More complex patterns (parallel, loop, fallback) would need deeper AST generation or a plan interpreter approach."

**Fix**: Implement plan interpreter for parallel/loop/fallback workflow generation.

### H3: Namespace composition operator asymmetry

| Module | `+` (union) | `\|` (pipe) | `>>` (chain) |
|--------|:-----------:|:-----------:|:------------:|
| C (Context) | Yes | Yes | No |
| P (Prompt) | Yes | Yes | No |
| S (State) | No | No | Yes |
| A (Artifacts) | No | No | No |
| M (Middleware) | No | Yes | No |
| T (Tools) | No | Yes | No |
| E (Evaluation) | No | Yes | No |
| G (Guards) | No | Yes | No |
| UI | Yes | Yes | Yes |

Users expect consistent composition across namespaces. S lacks `+`/`|`, C/P lack `>>`, A lacks all operators.

**Fix**: Phase 1 — add missing operators where semantically meaningful. Phase 2 — document which operators each namespace supports and why.

---

## MEDIUM Severity

### M1: Broad exception handling in _base.py

**Lines**: 933, 1030, 1036, 1044, 1227, 1404, 1629, 2251, 2765, 2894

10 sites with `except (NotImplementedError, Exception):` followed by `pass`. Silently swallows all errors including during IR contract checks and build-time validation.

**Fix**: Use specific exception types. Log suppressed exceptions at debug level.

### M2: Duplicated middleware merge logic

**File**: `_base.py:795-801, 835-841`

Identical 7-line middleware merging block appears in both `__rshift__()` and `__or__()`.

**Fix**: Extract `_merge_middlewares(self, other) -> list`.

### M3: Duplicated `_safe_identifier()` across 3 worker modules

**Files**: `temporal_worker.py:363-370`, `prefect_worker.py:314-319`, `dbos_worker.py:308-313`

Three identical implementations of the same utility.

**Fix**: Extract to `backends/_utils.py`.

### M4: Silent failures in guards and artifacts

- `_guards.py:_LLMJudge.judge()` — returns `JudgmentResult(passed=True)` if GenAI import fails
- `_artifacts.py:_ToolFactory.load()` — returns error dict instead of raising
- `asyncio_backend.py:135-143` — returns placeholder event when ModelProvider is missing

Users won't realize features are disabled.

**Fix**: Fail explicitly or emit visible warnings.

### M5: Parallel state merge is last-write-wins with no conflict detection

**File**: `asyncio_backend.py:249-262`

`state.update(bs)` for each parallel branch. If branches write the same key, one silently overwrites.

**Fix**: Add conflict detection (at minimum a warning). The diagnosis engine already catches this at IR level (check 13) but runtime doesn't enforce it.

### M6: E namespace missing `_kind` protocol property

**File**: `_eval.py`

E class lacks `_kind`, `_reads_keys`, `_writes_keys` — the standard NamespaceSpec protocol properties that all other namespaces implement.

**Fix**: Add protocol properties to E class.

### M7: Unsafe string interpolation in codegen

**Files**: `temporal_worker.py:177-178`, `prefect_worker.py:206-210`, `dbos_worker.py:210-216`

Manual `.replace()` calls without escaping. If node names contain special characters, generated code could be invalid or injectable.

**Fix**: Use proper templating or AST-based code generation.

### M8: Backend protocol `capabilities` typed as `Any`

**File**: `backends/_protocol.py:36-42`

`capabilities` property returns `Any` to avoid circular imports with `EngineCapabilities` in `compile/`.

**Fix**: Move `EngineCapabilities` to `_protocol.py` or use `TYPE_CHECKING` guard.

### M9: Dispatch task registry potential memory leak

**File**: `backends/adk/_primitives.py:51, 54, 609-612`

ContextVar-based task registry; cleanup depends on `pop()` calls. If exception during join, tasks may accumulate.

**Fix**: Use `try...finally` to ensure cleanup.

---

## LOW Severity

### L1: 13 deprecated methods in agent.py

All properly warn with `DeprecationWarning` and have documented replacements:

| Deprecated | Replacement |
|-----------|-------------|
| `.delegate()` | `.agent_tool()` |
| `.guardrail()` | `.guard()` |
| `.history()` | `.context()` |
| `.include_history()` | `.context()` |
| `.inject_context()` | `.prepend()` |
| `.input_schema()` | `.accepts()` |
| `.output_key()` | `.writes()` |
| `.output_schema()` | `.returns()` |
| `.outputs()` | `.writes()` |
| `.retry_if()` | `.loop_while()` |
| `.save_as()` | `.writes()` |
| `.static_instruct()` | `.static()` |
| `Source.from_async()` | `StreamRunner.source()` |

**Fix**: Schedule removal for next major version.

### L2: Long methods in _base.py

- `_prepare_build_config()` — 133 lines (1731-1863)
- `_explain_plain()` — 150 lines (1081-1230)

**Fix**: Extract sub-concerns (context compilation, prompt compilation, UI compilation).

### L3: 35 `# type: ignore` comments across 13 files

Most are justified (optional deps with `import-not-found`, operator overloading with `arg-type`). No bare unexplained ignores.

**Fix**: Low priority. Some could be eliminated by improving protocols.

### L4: Unreachable `yield` statements in ADK primitives

**File**: `backends/adk/_primitives.py` — 9 instances of `return; yield  # noqa: RET504`

Required for async generator protocol compliance. Technically correct but code smell.

**Fix**: Cosmetic only — extract to helper or use `AsyncIterator` return type.

### L5: `progress_key` deprecated parameter in `.dispatch()`

**File**: `_base.py:2180`

Documented as deprecated alias for `stream_to` but lacks a `DeprecationWarning`.

**Fix**: Add deprecation warning.

### L6: Inconsistent `hasattr` vs `getattr` for `_middlewares`

**File**: `_base.py:726, 774, 795, 836, 2274`

Mix of `hasattr(self, "_middlewares")` and `getattr(self, "_middlewares", [])`.

**Fix**: Standardize on `getattr(self, "_middlewares", [])`.

### L7: `_DictState` dead code with mutable default

**File**: `asyncio_backend.py:548-554`

Class attribute `state = {}` is a shared mutable default (anti-pattern). Class appears unused in practice.

**Fix**: Remove or fix the mutable default.

---

## Positive Observations

- **Zero TODOs/FIXMEs** — codebase is clean of untracked work
- **All deprecated methods have warnings** — proper migration path
- **Consistent backend structure** — Prefect/DBOS follow Temporal's pattern exactly
- **14/14 IR nodes handled** in asyncio, Prefect, and DBOS backends
- **15-check diagnosis engine** catches most issues at IR level before runtime
- **3000+ tests passing** with lint clean

---

## Testing & Compile Layer

### T1: contracts.py `_check_sequence_contracts()` is 812 lines (MEDIUM)

**File**: `testing/contracts.py:155-970`

Single function performs all 16 contract passes. Cannot test individual passes in isolation, hard to maintain.

**Fix**: Extract each pass into a separate function.

### T2: Pass 11 missing from documentation (MEDIUM)

**File**: `testing/contracts.py:1-23`

Module docstring claims "16 total" passes but jumps from Pass 10 to Pass 12. Pass 11 is undocumented.

**Fix**: Either document the missing pass or update the count.

### T3: Duplicated tree traversal across contracts.py and diagnosis.py (MEDIUM)

Both modules independently implement IR tree walking (`_walk()` patterns). Tree is traversed 3+ times during a single `diagnose()` call.

**Fix**: Extract shared tree walker to a utility function.

### T4: Silent issue type loss in `_convert_issues()` (MEDIUM)

**File**: `testing/diagnosis.py:309-325`

If `check_contracts()` returns a type not in `(str, dict)`, the issue is silently dropped — no else clause.

**Fix**: Add `else:` clause that warns or preserves unknown issue types.

### T5: No individual pass test utilities (LOW)

**File**: `testing/__init__.py`

Users can run `check_contracts()` but cannot test individual passes (e.g., just output key tracking, or just template var resolution) in isolation.

**Fix**: Export per-pass validator functions.

### T6: Placeholder `annotate_checkpoints()` in compile passes (LOW)

**File**: `compile/passes.py:150-162`

No-op function documented as "future feature" but already listed in `run_passes()`. 13 lines to document nothing.

**Fix**: Remove from `run_passes()` until implemented, or implement it.

### T7: Type annotation gaps across testing/compile (LOW)

Functions accept `Any` where `FullNode | AgentNode` would be appropriate. Affects `diagnose()`, `check_contracts()`, `fuse_transforms()`, `run_passes()`.

---

## Recommended Fix Order

### Sprint 1 (Critical path)
1. **H1**: Implement ADK backend `run()`/`stream()` or formally document as compile-only
2. **M1**: Replace broad exception handling with specific types
3. **M4**: Convert silent failures to explicit warnings

### Sprint 2 (Developer experience)
4. **H3**: Add missing namespace composition operators
5. **M2 + M3**: Extract duplicated code to shared utilities
6. **M6**: Add protocol properties to E namespace
7. **T4**: Fix silent issue type loss in `_convert_issues()`
8. **L1**: Plan deprecation removal timeline

### Sprint 3 (Robustness)
9. **H2**: Implement full Temporal workflow codegen
10. **T1**: Refactor 812-line `_check_sequence_contracts()` into per-pass functions
11. **T3**: Consolidate duplicated tree traversal logic
12. **M5**: Add parallel state merge conflict detection
13. **M7**: Switch codegen to proper templating
14. **M8 + M9**: Fix protocol typing and task cleanup
