# Architectural DevEx Proposal: adk-fluent Manual Code Audit

> **Auditor Role**: Staff Developer Experience (DevEx) Engineer & Pragmatic Python Architect
> **Metric**: 100x Developer ROI — every refactor must measurably improve how developers *communicate* with this library
> **Date**: 2026-03-14
> **Scope**: Hand-coded foundational modules only (excludes auto-generated builders and the codegen pipeline)

---

## Executive Summary

adk-fluent's hand-coded foundation is **exceptionally well-architected** — a rare case where the underlying machinery matches the quality of the public API it serves. The copy-on-write immutability model, the `Self`-typed fluent chains, the five-concern data flow separation, and the `.native()` escape hatch are evidence of a team that understands what makes a fluent API *feel right*.

That said, there are **seven high-ROI refactors** that would push this from "excellent SDK" to "SDK that developers brag about on Twitter." None are academic exercises. Each one removes a concrete paper cut or prevents a real confusion scenario.

**Overall Health Score: 8.5/10**

---

## Phase 1: The Namespace "Vibe Check" (Discoverability)

### 🔍 The Cognitive Clutter

**1. `__init__.py` exports 347 symbols — IDE autocomplete is a firehose**

When a developer types `from adk_fluent import `, their IDE shows all 347 names in a flat, unsorted list: `ActiveStreamingTool` next to `Agent` next to `AgentConfig` next to `AgentEngineSandboxCodeExecutor`. The *seven things they need 95% of the time* (`Agent`, `Pipeline`, `FanOut`, `Loop`, `S`, `C`, `P`) are buried.

The `prelude.py` module (122 curated exports across 9 tiers) was designed to solve this, but it requires users to *already know* about `from adk_fluent.prelude import *` — a discoverability chicken-and-egg problem.

**File**: `src/adk_fluent/__init__.py` — 786 lines, 347 `__all__` entries
**File**: `src/adk_fluent/prelude.py` — 122 lines, well-tiered

**Verdict**: The `__init__.py` is correct (no namespace leakage, strict `__all__`, all `_`-prefixed internals hidden). But it trades discoverability for completeness.

**2. Internal dataclass types leak into `__all__`**

`CFromState`, `CWindow`, `CUserOnly`, `PRole`, `PContext`, `PTask`, `PConstraint`, `PFormat`, `PExample`, etc. are exported at the top level. Users should never need to import `CFromState` directly — they use `C.from_state()` which *returns* a `CFromState`. Exporting these clutters autocomplete without adding value.

**Count**: ~40+ internal dataclass types that are implementation details of the namespace factories.

### 💎 The 100x Refactor

**Recommendation: Tiered `__init__.py` with `__all__` partitioning**

Keep all 347 exports for backward compatibility, but restructure the `__all__` with a comment-based cognitive hierarchy and promote `prelude` in package docstring:

```python
"""adk-fluent: Fluent builder API for Google ADK.

Quick start — import only what you need 95% of the time:

    from adk_fluent.prelude import *

Full API — all 347 symbols available:

    from adk_fluent import Agent, Pipeline, FanOut, Loop
    from adk_fluent import S, C, P, A, M, T, E, G
"""
```

**Concrete action**: Add a module-level docstring to `__init__.py` that teaches the prelude pattern *at the point of discovery*. When a user's IDE shows the package summary, they see the prelude import immediately.

**Second action**: Consider suppressing internal dataclass types (`CFromState`, `PRole`, etc.) from `__all__` in a future minor version. These are namespace implementation details, not public API. Users who need them can still import directly:

```python
from adk_fluent._context import CFromState  # explicit internal import
```

---

## Phase 2: The Fluent State Machine (Robustness & Purity)

### 🔍 The Cognitive Clutter

**1. Copy-on-Write is correct but has a deep-clone overhead concern**

The CoW strategy (`_freeze()` + `_maybe_fork_for_mutation()` → `copy.deepcopy()`) is architecturally sound. It guarantees that operator expressions (`>>`, `|`, `*`) never mutate their operands. However:

- `deep_clone_builder()` in `_helpers.py:301-308` calls `copy.deepcopy()` on the entire `_config`, `_callbacks`, and `_lists` dicts
- For a deeply nested workflow (e.g., a Pipeline of 10 agents, each with tools and callbacks), the first mutation after an operator triggers a full deep-copy of the entire builder tree
- This is O(total_state) per operator, which is fine for typical usage but could surprise users building complex compositions programmatically

**File**: `src/adk_fluent/_base.py:188-200` — freeze/fork mechanism
**File**: `src/adk_fluent/_helpers.py:301-308` — `deep_clone_builder()`

**Verdict**: Not a bug. Not worth fixing for typical usage. But worth *documenting* as a design decision, and worth adding a lazy-copy optimization if profiling ever shows it's a bottleneck.

**2. `Self` return type is used correctly — the IDE autocomplete journey is excellent**

Every builder method returns `Self`, which means:
```python
Agent("x", "gemini-2.5-flash").instruct("...").tool(fn).writes("key").build()
#     ^Agent                    ^Agent          ^Agent   ^Agent       ^LlmAgent
```

IDE autocomplete preserves the full method set at every step. Subclasses (e.g., `Agent` extending `BuilderBase`) don't break the chain. This is *exactly right*.

**File**: `src/adk_fluent/_base.py:192` — `_maybe_fork_for_mutation() -> Self`
**File**: `src/adk_fluent/agent.py:132-137` — example method returning `Self`

**3. Operator methods return `BuilderBase` instead of `Self` — breaks subclass chain**

When you do `agent_a >> agent_b`, the result is typed as `BuilderBase`, not as the originating type. This is technically correct (the result is a `Pipeline`, not an `Agent`), but it means post-operator methods show `BuilderBase` methods only. This is a minor IDE friction for users who chain after operators:

```python
result = Agent("a") >> Agent("b")
result.middleware(...)  # IDE shows BuilderBase methods, not Pipeline methods
```

**Verdict**: Acceptable trade-off. The operator creates a new type (Pipeline), so returning the exact type would require overloaded return types per operand combination. Not worth the complexity.

### 💎 The 100x Refactor

**No changes needed.** The state machine is clean. The CoW pattern is correct. The `Self` typing is properly implemented.

**One documentation improvement**: Add a brief note in the CLAUDE.md or a code comment in `_base.py` explaining *why* deep clone is used instead of lazy/structural sharing:

```python
# WHY deep_clone_builder uses copy.deepcopy:
# Structural sharing (sharing sub-dicts between clones) would save memory
# but creates subtle aliasing bugs when a nested list is mutated.
# For typical builder graphs (<100 nodes), deepcopy is fast enough (<1ms).
# If profiling shows this is a bottleneck, consider copy-on-write dicts.
```

---

## Phase 3: The Pragmatic Escape Hatches & Empathy

### 🔍 The Cognitive Clutter

**1. `.native()` escape hatch exists but is under-documented**

The `.native(fn)` method registers a post-build hook that receives the raw ADK object:

```python
agent = (
    Agent("x", "gemini-2.5-flash")
    .instruct("...")
    .native(lambda adk_obj: setattr(adk_obj, "some_edge_case_field", True))
    .build()
)
```

This is the correct escape hatch design — it doesn't break the fluent chain and runs *after* the builder has done its work. However, it's only mentioned in CLAUDE.md with a brief example. Users who are stuck because the builder doesn't expose a specific ADK field won't discover it organically.

**File**: `src/adk_fluent/_base.py:563-575` — `.native()` and `_apply_native_hooks()`

**2. `BuilderError` translates Pydantic errors beautifully**

```python
# Raw Pydantic error (what users would see without translation):
# pydantic.ValidationError: 3 validation errors for LlmAgent
#   name
#     field required (type=value_error.missing)
#   model
#     str type expected (type=type_error.str)

# BuilderError (what users actually see):
# BuilderError: Failed to build Agent('helper'):
#   - name: Field required
#   - model: Input should be a valid string
```

This is excellent DevEx. The `_safe_build()` method at `_base.py:545-561` catches `pydantic.ValidationError` and extracts field-level error locations. Every other exception type gets a single-line wrap.

**3. Silent predicate failures are a hidden DevEx trap**

`_predicate_utils.py` (the canonical predicate evaluator used by `S.when()`, `C.when()`, `P.when()`) **silently swallows all exceptions** from user predicates:

```python
# _predicate_utils.py:34-39
if callable(predicate):
    try:
        return bool(predicate(state))
    except Exception:
        _log.warning("Predicate raised an exception; treating as False")
        return False
```

Similarly, `_routing.py:194-199` swallows `KeyError`, `TypeError`, `ValueError` in route predicates:

```python
for predicate, agent in rules:
    try:
        if predicate(state):
            target = agent
            break
    except (KeyError, TypeError, ValueError):
        continue  # silently skip failed predicate
```

**The DevEx problem**: A user writes `Route("tier").eq("VIP", vip_agent)` and state["tier"] doesn't exist. The route silently falls through to `.otherwise()`. The user spends 30 minutes debugging "why isn't my VIP agent being selected?" because there's no error, no warning visible in their terminal — just a `logging.warning` lost in the noise.

**4. No `ADKFluentError` base exception hierarchy**

The library has two exception types:
- `BuilderError` (build-time configuration errors)
- `GuardViolation` (runtime guard failures)

But these don't share a common base. A user who wants to `except` all adk-fluent errors can't:

```python
try:
    agent.build()
except ???:  # No common base to catch all adk-fluent errors
    pass
```

### 💎 The 100x Refactor

**Refactor 1: Exception hierarchy with a common base**

```python
class ADKFluentError(Exception):
    """Base exception for all adk-fluent errors.

    Catch this to handle any adk-fluent error uniformly:

        try:
            agent.build()
        except ADKFluentError as e:
            print(f"adk-fluent error: {e}")
    """

class BuilderError(ADKFluentError):
    """Raised when .build() fails due to invalid configuration."""
    ...

class GuardViolation(ADKFluentError):
    """Raised when a guard rejects input or output."""
    ...

class PredicateError(ADKFluentError):
    """Raised when a predicate function fails unexpectedly.

    Only raised in strict mode. In default mode, predicate
    failures are logged and treated as False.
    """
    ...
```

**Refactor 2: Strict predicate mode**

Add a `strict` flag to predicate evaluation that raises instead of swallowing:

```python
def evaluate_predicate(
    predicate: Any,
    state: dict[str, Any],
    *,
    strict: bool = False,
) -> bool:
    if callable(predicate):
        try:
            return bool(predicate(state))
        except Exception as exc:
            if strict:
                raise PredicateError(
                    f"Predicate {getattr(predicate, '__name__', repr(predicate))} "
                    f"raised {type(exc).__name__}: {exc}\n"
                    f"State keys available: {sorted(state.keys())}"
                ) from exc
            _log.warning("Predicate raised %s; treating as False", exc)
            return False
```

**Why this is 100x ROI**: The single biggest time sink in debugging agent pipelines is "why isn't my data flowing where I expect?" Silent predicate failures are the #1 cause. Adding `strict=True` (or `.debug()` on the builder) turns a 30-minute debugging session into a 3-second error message.

**Refactor 3: Improve `.native()` discoverability**

Add a companion method that makes the escape hatch more intuitive:

```python
def with_raw_config(self, **kwargs: Any) -> Self:
    """Set arbitrary fields on the ADK object after build.

    Use when the builder doesn't expose a specific ADK parameter:

        agent = (
            Agent("x", "gemini-2.5-flash")
            .instruct("...")
            .with_raw_config(
                disallow_transfer_to_parent=True,
                include_contents="none",
            )
            .build()
        )

    Equivalent to:
        .native(lambda obj: [setattr(obj, k, v) for k, v in kwargs.items()])
    """
    def _apply(obj):
        for key, value in kwargs.items():
            if not hasattr(obj, key):
                import warnings
                warnings.warn(
                    f"ADK object {type(obj).__name__} has no attribute '{key}'. "
                    f"Available attributes: {sorted(a for a in dir(obj) if not a.startswith('_'))}",
                    stacklevel=2,
                )
            setattr(obj, key, value)
    return self.native(_apply)
```

**Why this is 100x ROI**: `.with_raw_config(field=value)` is self-documenting. `.native(lambda obj: setattr(obj, 'field', value))` requires the user to know about `setattr` and lambdas. Plus, the warning on unknown attributes prevents silent misconfiguration.

---

## Phase 4: Cross-Cutting Findings

### 🔍 Additional Cognitive Clutter

**1. `_context.py` is ~2500 lines — the largest hand-written module**

The C namespace has 40+ factory methods, each creating its own frozen dataclass + a lazy async provider factory function. The provider factories (`_make_xxx_provider()`) account for ~60% of the file. This module should be split:

- `_context.py` — public API: `C` class, `CTransform` base, composition operators (~800 lines)
- `_context_providers.py` — private: all `_make_xxx_provider()` factories (~1500 lines)

**2. `decorators.py` accesses `_config` and `_lists` directly**

```python
# decorators.py — fragile private attribute access
builder._config["instruction"] = fn.__doc__
builder._lists["tools"].append(wrapped_fn)
```

If the builder internals change (e.g., `_config` → `_state`), the decorator module silently breaks. Should use the public fluent API instead:

```python
builder = builder.instruct(fn.__doc__)
builder = builder.tool(wrapped_fn)
```

**3. `TimeoutMiddleware` leaks memory on long-running applications**

```python
# middleware.py — _deadlines dict never cleaned up
class TimeoutMiddleware:
    _deadlines: dict[str, float] = {}  # grows forever
```

After each agent invocation completes, the deadline entry is never removed. For a long-running server processing thousands of requests, this is a slow memory leak.

**4. `_SampledMiddleware` uses unseeded `random.random()`**

```python
# middleware.py
class _SampledMiddleware:
    def _should_run(self):
        return random.random() < self._rate
```

Non-deterministic behavior makes tests flaky. Should accept an optional `random.Random` instance for testability.

### 💎 The 100x Refactors (Summary)

| # | Refactor | ROI | Effort | Files |
|---|----------|-----|--------|-------|
| 1 | Add `ADKFluentError` base exception hierarchy | **Very High** — catch-all for error handling | Low | `_base.py`, `_guards.py` |
| 2 | Strict predicate mode with `PredicateError` | **Very High** — eliminates #1 debugging time sink | Low | `_predicate_utils.py`, `_routing.py` |
| 3 | `.with_raw_config(**kwargs)` escape hatch | **High** — discoverable, self-documenting, warns on typos | Low | `_base.py` |
| 4 | `__init__.py` docstring promoting prelude | **High** — fixes discoverability chicken-and-egg | Trivial | `__init__.py` |
| 5 | Split `_context.py` into API + providers | **Medium** — maintainability, not user-facing | Medium | `_context.py`, new `_context_providers.py` |
| 6 | Fix `TimeoutMiddleware` memory leak | **Medium** — correctness for long-running apps | Low | `middleware.py` |
| 7 | Fix `decorators.py` private attribute access | **Medium** — resilience to internal refactors | Low | `decorators.py` |

---

## 🎨 The Vibe Shift: Reference Implementation

Below is the proposed exception hierarchy and strict predicate evaluator — the two highest-ROI changes that require the least code:

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Proposed: src/adk_fluent/_exceptions.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""adk-fluent exception hierarchy.

All adk-fluent exceptions inherit from ADKFluentError.
Users can catch the base class to handle any library error:

    from adk_fluent import ADKFluentError

    try:
        agent.build()
    except ADKFluentError as e:
        logger.error("Builder failed: %s", e)
"""

from __future__ import annotations
from typing import Any


class ADKFluentError(Exception):
    """Base exception for all adk-fluent errors."""


class BuilderError(ADKFluentError):
    """Raised when .build() fails due to invalid configuration.

    Attributes:
        builder_name: Name passed to the builder constructor.
        builder_type: Class name of the builder (e.g., "Agent").
        field_errors: Human-readable list of field-level issues.
        original: The underlying exception (usually pydantic.ValidationError).
    """

    def __init__(
        self,
        builder_name: str,
        builder_type: str,
        field_errors: list[str],
        original: Exception,
    ):
        self.builder_name = builder_name
        self.builder_type = builder_type
        self.field_errors = field_errors
        self.original = original
        lines = [f"Failed to build {builder_type}('{builder_name}'):"]
        for err in field_errors:
            lines.append(f"  - {err}")
        super().__init__("\n".join(lines))


class GuardViolation(ADKFluentError):
    """Raised when a guard rejects input or output.

    Attributes:
        guard_kind: Type of guard ("pii", "toxicity", "length", "schema", "custom").
        phase: When the violation occurred ("pre_model", "post_model", etc.).
        detail: Human-readable explanation.
        value: The rejected content (may be truncated for large payloads).
    """

    def __init__(
        self,
        guard_kind: str,
        phase: str,
        detail: str,
        value: Any = None,
    ):
        self.guard_kind = guard_kind
        self.phase = phase
        self.detail = detail
        self.value = value
        super().__init__(f"[{guard_kind}] {detail}")


class PredicateError(ADKFluentError):
    """Raised when a predicate function fails in strict mode.

    In default mode, predicate failures are logged as warnings and
    treated as False. Enable strict mode with Agent(...).debug() or
    by passing strict=True to evaluate_predicate().

    Attributes:
        predicate_repr: String representation of the failing predicate.
        available_keys: State keys that were available when the error occurred.
        original: The underlying exception.
    """

    def __init__(
        self,
        predicate_repr: str,
        available_keys: list[str],
        original: Exception,
    ):
        self.predicate_repr = predicate_repr
        self.available_keys = available_keys
        self.original = original
        super().__init__(
            f"Predicate {predicate_repr} raised {type(original).__name__}: {original}\n"
            f"  State keys available: {available_keys}\n"
            f"  Hint: Check that your predicate handles missing keys gracefully,\n"
            f"  or use .get() with a default value."
        )
```

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Proposed: Updated src/adk_fluent/_predicate_utils.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""Shared predicate evaluation for P.when, S.when, C.when.

Single canonical implementation used by all composition namespaces.
M.when has its own evaluation path (execution mode checks, TraceContext
access) so it does not use this module.
"""

from __future__ import annotations

import logging
from typing import Any

__all__ = ["evaluate_predicate"]

_log = logging.getLogger(__name__)


def evaluate_predicate(
    predicate: Any,
    state: dict[str, Any],
    *,
    strict: bool = False,
) -> bool:
    """Evaluate a predicate against session state.

    Args:
        predicate: The predicate to evaluate. Accepts:
            - None → False
            - str → state key check: bool(state.get(key))
            - callable → bool(predicate(state))
            - anything else → bool(predicate)
        state: The current session state dictionary.
        strict: If True, raise PredicateError on exceptions instead
                of silently returning False. Enable via .debug() on builders.

    Returns:
        Boolean result of the predicate evaluation.

    Raises:
        PredicateError: If strict=True and the predicate raises an exception.
    """
    if predicate is None:
        return False
    if isinstance(predicate, str):
        return bool(state.get(predicate))
    if callable(predicate):
        try:
            return bool(predicate(state))
        except Exception as exc:
            if strict:
                from adk_fluent._exceptions import PredicateError

                raise PredicateError(
                    predicate_repr=getattr(predicate, "__name__", repr(predicate)),
                    available_keys=sorted(state.keys()),
                    original=exc,
                ) from exc
            _log.warning(
                "Predicate %s raised %s; treating as False",
                getattr(predicate, "__name__", "?"),
                exc,
            )
            return False
    return bool(predicate)
```

```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Proposed: .with_raw_config() addition to BuilderBase
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Add to src/adk_fluent/_base.py, after the .native() method:

def with_raw_config(self, **kwargs: Any) -> Self:
    """Set arbitrary fields on the native ADK object after build.

    Use when the fluent builder doesn't expose a specific ADK parameter.
    This is the recommended "escape hatch" for edge cases.

    Example::

        agent = (
            Agent("x", "gemini-2.5-flash")
            .instruct("You are helpful.")
            .with_raw_config(
                disallow_transfer_to_parent=True,
                include_contents="none",
            )
            .build()
        )

    Warns if the target ADK object doesn't have the specified attribute,
    preventing silent misconfiguration.

    See Also:
        .native(fn) — for full programmatic access to the ADK object.
    """
    def _apply(obj: Any) -> None:
        for key, value in kwargs.items():
            if not hasattr(obj, key):
                import warnings
                attrs = sorted(a for a in dir(obj) if not a.startswith("_"))
                warnings.warn(
                    f"ADK object {type(obj).__name__} has no attribute '{key}'. "
                    f"Did you mean one of: {', '.join(attrs[:10])}?",
                    UserWarning,
                    stacklevel=2,
                )
            setattr(obj, key, value)
    return self.native(_apply)
```

---

## Appendix: What's Already Excellent (Don't Touch)

These architectural decisions are world-class and should be preserved as-is:

| Decision | Why It's Right |
|----------|----------------|
| **Copy-on-Write immutability** | Operators don't mutate operands. Sub-expressions reusable. No surprise bugs. |
| **`Self` return type** on all builder methods | Full IDE autocomplete chain. Subclass-safe. |
| **`.build()` returns real ADK objects** | Zero lock-in. Full `adk web/run/deploy` compatibility. Users trust the abstraction. |
| **Five orthogonal data flow concerns** | `reads/writes/returns/accepts/produces` are independent. Clean mental model. |
| **`.native()` post-build hooks** | Escape hatch that doesn't break fluent chain. Power users get full access. |
| **`BuilderError` translation** | Users see field-level errors, not raw Pydantic tracebacks. |
| **16-pass contract checker** | Catches data flow bugs at build time. Better than any other fluent API library. |
| **`NamespaceSpec` protocol** | All eight namespaces (S, C, P, A, M, T, E, G) share composable contract. |
| **`prelude.py` tiered exports** | 9-tier import for progressive disclosure. Perfect for onboarding. |
| **Frozen dataclasses in P, C, A** | Immutable specs + `__slots__` = fast + IDE-friendly. |
| **`PrimitiveBuilderBase`** | DRY base for expression primitives. New primitives in ~15 lines. |
| **Lazy auto-building of sub-agents** | Users compose without manual `.build()` calls on children. |

---

## Appendix: Namespace Consistency Matrix

| Aspect | S | C | P | A | M | T | E | G |
|--------|---|---|---|---|---|---|---|---|
| Immutability | ★★★ | ★★★ | ★★★ | ★★★ | ★★☆ | ★★☆ | ★★★ | ★★★ |
| Composition | ★★★ | ★★★ | ★★★ | ★★☆ | ★★★ | ★★★ | ★★★ | ★★★ |
| Type Hints | ★★★ | ★★☆ | ★★★ | ★★☆ | ★★☆ | ★★☆ | ★★☆ | ★★☆ |
| Error Handling | ★★★ | ★★☆ | ★★☆ | ★★☆ | ★★☆ | ★★☆ | ★★☆ | ★★★ |
| Documentation | ★★★ | ★★☆ | ★★★ | ★★☆ | ★★☆ | ★★☆ | ★★☆ | ★★☆ |

**Standout**: S (transforms) and P (prompts) are the best-factored namespaces.
**Needs attention**: A (artifacts) has weak composition and opaque `_fn` fields. M/T use `Any` heavily.

---

## Appendix: File Size Audit

| File | Lines | Status |
|------|-------|--------|
| `_context.py` | ~2500 | ⚠️ Should split |
| `middleware.py` | ~1269 | ⚠️ Large but justified (protocol + 10 implementations) |
| `testing/contracts.py` | ~995 | ✅ Complex but well-structured |
| `_base.py` | ~2100 | ✅ Core infrastructure, justified size |
| `_prompt.py` | ~1128 | ✅ 20+ dataclass types, justified |
| `_primitives.py` | ~803 | ✅ 14 runtime agent types |
| `_transforms.py` | ~796 | ✅ 25+ transforms, clean |
| `_eval.py` | ~1000+ | ⚠️ Consider splitting suite vs criteria |
| `_guards.py` | ~679 | ✅ Compact |
| All others | <500 | ✅ Well-sized |
