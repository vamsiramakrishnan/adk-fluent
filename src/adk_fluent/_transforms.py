"""State transform factories for the >> operator. Hand-written, not generated.

Each factory returns an ``STransform`` — a composable, callable object that
plugs into the ``>>`` pipeline operator and the ``+`` combine operator.

Composition operators::

    >>  chain   — first runs, state updated, second runs on updated state
    +   combine — both run on original state, results merge

StateDelta:        additive merge — only the returned keys are updated.
StateReplacement:  replace session-scoped keys — unprefixed keys not in the
                   replacement are set to None; app:/user:/temp: keys are
                   NEVER touched.

Each ``STransform`` carries ``_reads_keys`` and ``_writes_keys`` attributes
(frozenset[str] or None) for build-time contract tracing.  ``None`` means
"reads/writes the full state" (opaque to the checker).

Usage::

    from adk_fluent import S

    # Pipeline with >> operator (unchanged)
    pipeline = (
        Agent("researcher").instruct("Find data.").save_as("findings")
        >> S.pick("findings", "sources")
        >> S.rename(findings="input")
        >> S.default(confidence=0.5)
        >> Agent("writer").instruct("Write report.")
    )

    # NEW: Compose transforms with + and >>
    cleanup = S.pick("findings") >> S.rename(findings="input") >> S.default(confidence=0.5)
    pipeline = Agent("researcher").save_as("findings") >> cleanup >> Agent("writer")

    # NEW: Combine transforms with +
    defaults = S.default(language="en") + S.default(confidence=0.5)
    pipeline = Agent("researcher") >> defaults >> Agent("writer")
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = ["S", "STransform", "StateDelta", "StateReplacement"]

# ADK state scope prefixes (from google.adk.sessions.state.State)
_SCOPE_PREFIXES = ("app:", "user:", "temp:")


@dataclass(frozen=True, slots=True, eq=False)
class StateDelta:
    """Additive: merge these keys into state. Existing keys not mentioned are untouched."""

    updates: dict[str, Any]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, StateDelta):
            return self.updates == other.updates
        if isinstance(other, dict):
            return self.updates == other
        return NotImplemented

    def __hash__(self) -> int:
        return id(self)


@dataclass(frozen=True, slots=True, eq=False)
class StateReplacement:
    """Replace session-scoped keys. ONLY unprefixed keys are affected.

    ADK constraint: State has no __delitem__. The FnAgent implements
    replacement by setting removed unprefixed keys to None in state_delta.
    Keys with scope prefixes (app:, user:, temp:) are NEVER touched.
    """

    new_state: dict[str, Any]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, StateReplacement):
            return self.new_state == other.new_state
        if isinstance(other, dict):
            return self.new_state == other
        return NotImplemented

    def __hash__(self) -> int:
        return id(self)


# ======================================================================
# STransform — composable state transform object
# ======================================================================


def _merge_keysets(a: frozenset[str] | None, b: frozenset[str] | None) -> frozenset[str] | None:
    """Merge two key metadata sets. None means opaque (full state)."""
    if a is None or b is None:
        return None
    return a | b


def _apply_result(state: dict[str, Any], result: StateDelta | StateReplacement | dict | None) -> dict[str, Any]:
    """Apply a transform result to a state dict, returning a new dict."""
    out = dict(state)
    if result is None:
        return out
    if isinstance(result, StateDelta):
        out.update(result.updates)
    elif isinstance(result, StateReplacement):
        # Keep scoped keys, replace session-scoped
        scoped = {k: v for k, v in out.items() if k.startswith(_SCOPE_PREFIXES)}
        out = {**scoped, **result.new_state}
    elif isinstance(result, dict):
        out.update(result)
    return out


class STransform:
    """Composable state transform with metadata for contract checking.

    An ``STransform`` is callable (backward-compatible with plain functions)
    and supports composition via ``>>`` (chain) and ``+`` (combine).

    Created by ``S.pick()``, ``S.rename()``, ``S.default()``, etc.
    Works with the ``>>`` pipeline operator on Agent/Pipeline/Loop/FanOut.

    Composition examples::

        # Chain: first runs, then second runs on updated state
        cleanup = S.pick("a", "b") >> S.rename(a="x")

        # Combine: both run on original state, deltas merge
        defaults = S.default(a=1) + S.default(b=2)

        # Interop with Agent builders via >>
        pipeline = Agent("a").save_as("out") >> S.pick("out") >> Agent("b")

        # Start a pipeline from an S transform
        pipeline = S.capture("input") >> Agent("writer")
    """

    def __init__(
        self,
        fn: Callable,
        *,
        reads: frozenset[str] | None = None,
        writes: frozenset[str] | None = None,
        name: str = "transform",
        capture_key: str | None = None,
    ):
        self._fn = fn
        self._reads_keys = reads
        self._writes_keys = writes
        self._capture_key = capture_key
        # __name__ used by _fn_step and debugging
        self.__name__ = name

    def __call__(self, state: dict) -> StateDelta | StateReplacement:
        """Execute this transform on a state dict."""
        return self._fn(state)

    # ------------------------------------------------------------------
    # Composition: >> (chain)
    # ------------------------------------------------------------------

    def __rshift__(self, other: Any) -> Any:
        """Chain: ``self >> other``.

        - STransform >> STransform → chained STransform
        - STransform >> Agent/Pipeline → Pipeline (self as first step)
        """
        if isinstance(other, STransform):
            return _chain_transforms(self, other)

        # Agent/Pipeline/FanOut/Loop — wrap self as builder step, then >>
        from adk_fluent._base import BuilderBase, _fn_step
        from adk_fluent._routing import Route

        if isinstance(other, BuilderBase | Route):
            return _fn_step(self) >> other

        # Plain callable → wrap as STransform then chain
        if callable(other) and not isinstance(other, type):
            return _chain_transforms(self, STransform(other, name=getattr(other, "__name__", "fn")))

        return NotImplemented

    def __rrshift__(self, other: Any) -> Any:
        """Support ``Agent >> STransform`` (already works via callable protocol, but explicit)."""
        from adk_fluent._base import BuilderBase

        if isinstance(other, BuilderBase):
            return other >> self
        return NotImplemented

    # ------------------------------------------------------------------
    # Composition: + (combine)
    # ------------------------------------------------------------------

    def __add__(self, other: Any) -> STransform:
        """Combine: ``self + other``.

        Both transforms run on the original state. Results merge:
        - StateDelta + StateDelta → merged StateDelta (second wins on conflicts)
        - StateReplacement + StateReplacement → merged StateReplacement
        - Mixed → second result type wins
        """
        if isinstance(other, STransform):
            return _combine_transforms(self, other)
        if callable(other) and not isinstance(other, type):
            return _combine_transforms(self, STransform(other, name=getattr(other, "__name__", "fn")))
        return NotImplemented

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        parts = [self.__name__]
        if self._reads_keys is not None:
            parts.append(f"reads={set(self._reads_keys)}")
        if self._writes_keys is not None:
            parts.append(f"writes={set(self._writes_keys)}")
        return f"STransform({', '.join(parts)})"


def _chain_transforms(first: STransform, second: STransform) -> STransform:
    """Chain two transforms sequentially.

    First runs on original state, result applied, then second runs on
    the updated state. Combined metadata is the union of both.
    """

    def _chained(state: dict) -> StateDelta | StateReplacement:
        result1 = first(state)
        intermediate = _apply_result(state, result1)
        return second(intermediate)

    reads = _merge_keysets(first._reads_keys, second._reads_keys)
    writes = _merge_keysets(first._writes_keys, second._writes_keys)
    name = f"{first.__name__}_then_{second.__name__}"

    return STransform(_chained, reads=reads, writes=writes, name=name)


def _combine_transforms(first: STransform, second: STransform) -> STransform:
    """Combine two transforms: both run on original state, results merge.

    StateDelta results merge (second wins on conflicts).
    StateReplacement results merge (second wins on conflicts).
    Mixed: replacement takes precedence.
    """

    def _combined(state: dict) -> StateDelta | StateReplacement:
        result1 = first(state)
        result2 = second(state)

        # Both StateDelta — merge updates
        if isinstance(result1, StateDelta) and isinstance(result2, StateDelta):
            return StateDelta({**result1.updates, **result2.updates})

        # Both StateReplacement — merge new_state
        if isinstance(result1, StateReplacement) and isinstance(result2, StateReplacement):
            return StateReplacement({**result1.new_state, **result2.new_state})

        # StateReplacement + StateDelta → apply delta on top of replacement
        if isinstance(result1, StateReplacement) and isinstance(result2, StateDelta):
            return StateReplacement({**result1.new_state, **result2.updates})

        # StateDelta + StateReplacement → replacement wins
        if isinstance(result1, StateDelta) and isinstance(result2, StateReplacement):
            return result2

        return StateDelta({})

    reads = _merge_keysets(first._reads_keys, second._reads_keys)
    writes = _merge_keysets(first._writes_keys, second._writes_keys)
    name = f"{first.__name__}_and_{second.__name__}"

    return STransform(_combined, reads=reads, writes=writes, name=name)


# ======================================================================
# S namespace — public API
# ======================================================================


class S:
    """State transform factories. Each method returns an ``STransform`` for use with ``>>``.

    Methods that *replace* session-scoped state return ``StateReplacement``:
    ``pick``, ``drop``, ``rename``.

    Methods that *additively merge* into state return ``StateDelta``:
    ``default``, ``merge``, ``transform``, ``compute``, ``set``, ``guard``, ``log``.

    All methods return ``STransform`` objects which support composition::

        # Chain with >>
        cleanup = S.pick("a") >> S.rename(a="x") >> S.default(y=1)

        # Combine with +
        defaults = S.default(a=1) + S.set(b=2)

        # Use in pipelines
        pipeline = Agent("a") >> cleanup >> Agent("b")

    Each returned transform carries ``_reads_keys`` and ``_writes_keys``
    (frozenset[str] or None) for build-time contract tracing.
    """

    @staticmethod
    def pick(*keys: str) -> STransform:
        """Keep only the specified session-scoped keys. app:/user:/temp: keys are always preserved.

        >>> S.pick("name", "score")
        """

        def _pick(state: dict) -> StateReplacement:
            return StateReplacement({k: state[k] for k in keys if k in state and not k.startswith(_SCOPE_PREFIXES)})

        return STransform(_pick, reads=None, writes=frozenset(keys), name=f"pick_{'_'.join(keys)}")

    @staticmethod
    def drop(*keys: str) -> STransform:
        """Remove the specified keys from state. Only session-scoped keys are affected.

        >>> S.drop("_internal", "_debug")
        """
        drop_set = set(keys)

        def _drop(state: dict) -> StateReplacement:
            return StateReplacement(
                {k: v for k, v in state.items() if k not in drop_set and not k.startswith(_SCOPE_PREFIXES)}
            )

        return STransform(_drop, reads=None, writes=None, name=f"drop_{'_'.join(keys)}")

    @staticmethod
    def rename(**mapping: str) -> STransform:
        """Rename state keys. Unmapped session-scoped keys pass through unchanged.
        app:/user:/temp: keys are never touched.

        >>> S.rename(result="input", raw_score="score")
        """

        def _rename(state: dict) -> StateReplacement:
            out: dict[str, Any] = {}
            for k, v in state.items():
                if k.startswith(_SCOPE_PREFIXES):
                    continue  # Prefixed keys handled by FnAgent, not transform
                new_key = mapping.get(k, k) or k
                out[new_key] = v
            return StateReplacement(out)

        return STransform(
            _rename,
            reads=frozenset(mapping.keys()),
            writes=frozenset(mapping.values()),
            name=f"rename_{'_'.join(mapping.keys())}",
        )

    @staticmethod
    def default(**defaults: Any) -> STransform:
        """Fill missing keys with default values. Existing keys are not overwritten.

        >>> S.default(confidence=0.5, language="en")
        """

        def _default(state: dict) -> StateDelta:
            updates = {k: v for k, v in defaults.items() if k not in state}
            return StateDelta(updates)

        return STransform(
            _default,
            reads=frozenset(defaults.keys()),
            writes=frozenset(defaults.keys()),
            name=f"default_{'_'.join(defaults.keys())}",
        )

    @staticmethod
    def merge(*keys: str, into: str, fn: Callable | None = None) -> STransform:
        """Combine multiple keys into one. Default join is newline concatenation.

        >>> S.merge("web", "papers", into="research")
        >>> S.merge("a", "b", into="total", fn=lambda a, b: a + b)
        """

        def _merge(state: dict) -> StateDelta:
            values = [state[k] for k in keys if k in state]
            if fn is not None:
                merged = fn(*values)
            else:
                merged = "\n".join(str(v) for v in values)
            return StateDelta({into: merged})

        return STransform(
            _merge,
            reads=frozenset(keys),
            writes=frozenset({into}),
            name=f"merge_{'_'.join(keys)}_into_{into}",
        )

    @staticmethod
    def transform(key: str, fn: Callable) -> STransform:
        """Apply a function to a single state value.

        >>> S.transform("text", str.upper)
        >>> S.transform("score", lambda x: round(x, 2))
        """
        fn_name = getattr(fn, "__name__", "fn")

        def _transform(state: dict) -> StateDelta:
            if key in state:
                return StateDelta({key: fn(state[key])})
            return StateDelta({})

        return STransform(
            _transform,
            reads=frozenset({key}),
            writes=frozenset({key}),
            name=f"transform_{key}_{fn_name}",
        )

    @staticmethod
    def guard(predicate: Callable[[dict], bool], msg: str = "State guard failed") -> STransform:
        """Assert a state invariant. Raises ValueError if predicate is falsy.

        >>> S.guard(lambda s: "key" in s, "Missing required key")
        >>> S.guard(lambda s: float(s.get("score", 0)) > 0)
        """

        def _guard(state: dict) -> StateDelta:
            if not predicate(state):
                raise ValueError(msg)
            return StateDelta({})

        return STransform(_guard, reads=None, writes=frozenset(), name="guard")

    @staticmethod
    def log(*keys: str, label: str = "") -> STransform:
        """Debug-print selected keys (or all state if no keys given). Returns no updates.

        >>> S.log("score", "confidence")
        >>> S.log(label="after-writer")
        """

        def _log(state: dict) -> StateDelta:
            prefix = f"[{label}] " if label else ""
            if keys:
                subset = {k: state.get(k, "<missing>") for k in keys}
            else:
                subset = state
            print(f"{prefix}{subset}")
            return StateDelta({})

        return STransform(
            _log,
            reads=frozenset(keys) if keys else None,
            writes=frozenset(),
            name=f"log_{'_'.join(keys) if keys else 'all'}",
        )

    @staticmethod
    def compute(**factories: Callable) -> STransform:
        """Derive new keys from the full state dict.

        >>> S.compute(
        ...     summary=lambda s: s["text"][:100],
        ...     word_count=lambda s: len(s.get("text", "").split()),
        ... )
        """

        def _compute(state: dict) -> StateDelta:
            return StateDelta({k: fn(state) for k, fn in factories.items()})

        return STransform(
            _compute,
            reads=None,
            writes=frozenset(factories.keys()),
            name=f"compute_{'_'.join(factories.keys())}",
        )

    @staticmethod
    def set(**values: Any) -> STransform:
        """Set explicit key-value pairs in state (additive merge).

        >>> S.set(stage="review", counter=0)
        """

        def _set(state: dict) -> StateDelta:
            return StateDelta(dict(values))

        return STransform(
            _set,
            reads=frozenset(),
            writes=frozenset(values.keys()),
            name=f"set_{'_'.join(values.keys())}",
        )

    @staticmethod
    def capture(key: str) -> STransform:
        """Capture the most recent user message into state[key].

        The callable is a stub — real capture happens in CaptureAgent,
        which is wired by the >> operator when _capture_key is detected.

        >>> S.capture("user_input") >> Agent("writer")
        """

        def _capture(state: dict) -> StateDelta:
            return StateDelta({})

        return STransform(
            _capture,
            reads=frozenset(),
            writes=frozenset({key}),
            name=f"capture_{key}",
            capture_key=key,
        )

    @staticmethod
    def identity() -> STransform:
        """No-op transform. Passes state through unchanged.

        Useful as a neutral element for composition::

            transform = S.identity()
            if need_cleanup:
                transform = transform >> S.pick("a", "b")
            pipeline = agent >> transform >> next_agent
        """

        def _identity(state: dict) -> StateDelta:
            return StateDelta({})

        return STransform(_identity, reads=frozenset(), writes=frozenset(), name="identity")

    @staticmethod
    def when(predicate: Callable[[dict], bool] | str, transform: STransform) -> STransform:
        """Conditional transform. Applies transform only if predicate(state) is truthy.

        String predicate is a shortcut for state key check::

            S.when("verbose", S.log("score"))   # apply if state["verbose"] truthy
            S.when(lambda s: "draft" in s, S.rename(draft="input"))
        """
        from adk_fluent._predicate_utils import evaluate_predicate

        def _when(state: dict) -> StateDelta | StateReplacement:
            if evaluate_predicate(predicate, state):
                return transform(state)
            return StateDelta({})

        reads = _merge_keysets(None, transform._reads_keys)  # predicate reads opaque
        if isinstance(predicate, str):
            # String predicate reads a known key — merge it in
            pred_reads = frozenset({predicate})
            reads = _merge_keysets(pred_reads, transform._reads_keys)

        return STransform(
            _when,
            reads=reads,
            writes=transform._writes_keys,
            name=f"when_{transform.__name__}",
        )

    @staticmethod
    def branch(key: str, **transforms: STransform) -> STransform:
        """Route to different transforms based on a state key value.

        >>> S.branch("intent",
        ...     booking=S.set(route="book"),
        ...     info=S.set(route="faq"),
        ... )
        """

        def _branch(state: dict) -> StateDelta | StateReplacement:
            value = state.get(key)
            if value is not None and str(value) in transforms:
                return transforms[str(value)](state)
            return StateDelta({})

        all_writes: frozenset[str] | None = frozenset()
        for t in transforms.values():
            all_writes = _merge_keysets(all_writes, t._writes_keys)

        return STransform(
            _branch,
            reads=frozenset({key}),
            writes=all_writes,
            name=f"branch_{key}",
        )
