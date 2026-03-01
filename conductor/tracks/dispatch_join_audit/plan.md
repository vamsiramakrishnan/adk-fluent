# Dispatch/Join System Improvements Plan

This track implements fixes and improvements identified in the Dispatch/Join System Audit.

## Phase 1: Core API & Error Handling (P0 & P1)

- [ ] Implement `fail_fast=False` parameter in `join()` and `JoinAgent`.
- [ ] Implement `into=None` parameter in `join()` and `JoinAgent`.
- [ ] Add `max_tasks(n)` method to `BackgroundTask`, deprecate `task_budget(n)`.
- [ ] Remove dead stream hooks from `TopologyHooks` or wire them in `StreamRunner`.
- [ ] Add warning when `join()` is called but no tasks are dispatched.
- [ ] Implement `dispatch_status()` helper function.
- [ ] Update `builder.dispatch(...)` method to accept extra agents (parity with `dispatch()` factory).

## Phase 2: Documentation & Integration (P0, P2, P3)

- [ ] Write `docs/user-guide/background-tasks.md` containing timeline diagram and state flow.
- [ ] Register cookbooks 59-62.
- [ ] Add contract checker pass for duplicate `.writes()` targets in dispatch children.
- [ ] Add tests for dispatch integration patterns (routing, artifacts, contracts).
