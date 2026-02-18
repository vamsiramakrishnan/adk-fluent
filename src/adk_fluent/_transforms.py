"""State transform factories for the >> operator. Hand-written, not generated.

Each factory returns a callable (dict -> StateDelta | StateReplacement) that
composes with >> for free via _fn_step wrapping.

StateDelta:        additive merge — only the returned keys are updated.
StateReplacement:  replace session-scoped keys — unprefixed keys not in the
                   replacement are set to None; app:/user:/temp: keys are
                   NEVER touched.

Usage:
    from adk_fluent import S

    pipeline = (
        Agent("researcher").instruct("Find data.").outputs("findings")
        >> S.pick("findings", "sources")
        >> S.rename(findings="input")
        >> S.default(confidence=0.5)
        >> Agent("writer").instruct("Write report.")
    )
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

__all__ = ["S", "StateDelta", "StateReplacement"]

# ADK state scope prefixes (from google.adk.sessions.state.State)
_SCOPE_PREFIXES = ("app:", "user:", "temp:")


@dataclass(frozen=True, slots=True)
class StateDelta:
    """Additive: merge these keys into state. Existing keys not mentioned are untouched."""
    updates: dict[str, Any]


@dataclass(frozen=True, slots=True)
class StateReplacement:
    """Replace session-scoped keys. ONLY unprefixed keys are affected.

    ADK constraint: State has no __delitem__. The FnAgent implements
    replacement by setting removed unprefixed keys to None in state_delta.
    Keys with scope prefixes (app:, user:, temp:) are NEVER touched.
    """
    new_state: dict[str, Any]


class S:
    """State transform factories. Each method returns a callable for use with >>.

    Methods that *replace* session-scoped state return ``StateReplacement``:
    ``pick``, ``drop``, ``rename``.

    Methods that *additively merge* into state return ``StateDelta``:
    ``default``, ``merge``, ``transform``, ``compute``, ``set``, ``guard``, ``log``.

    Plain ``dict`` returns from user-supplied callables are treated as
    ``StateDelta`` for backward compatibility.
    """

    @staticmethod
    def pick(*keys: str) -> Callable[[dict], StateReplacement]:
        """Keep only the specified session-scoped keys. app:/user:/temp: keys are always preserved.

            >> S.pick("name", "score")
        """
        def _pick(state: dict) -> StateReplacement:
            return StateReplacement({k: state[k] for k in keys
                                     if k in state and not k.startswith(_SCOPE_PREFIXES)})
        _pick.__name__ = f"pick_{'_'.join(keys)}"
        return _pick

    @staticmethod
    def drop(*keys: str) -> Callable[[dict], StateReplacement]:
        """Remove the specified keys from state. Only session-scoped keys are affected.

            >> S.drop("_internal", "_debug")
        """
        drop_set = set(keys)
        def _drop(state: dict) -> StateReplacement:
            return StateReplacement({k: v for k, v in state.items()
                                     if k not in drop_set
                                     and not k.startswith(_SCOPE_PREFIXES)})
        _drop.__name__ = f"drop_{'_'.join(keys)}"
        return _drop

    @staticmethod
    def rename(**mapping: str) -> Callable[[dict], StateReplacement]:
        """Rename state keys. Unmapped session-scoped keys pass through unchanged.
        app:/user:/temp: keys are never touched.

            >> S.rename(result="input", raw_score="score")
        """
        def _rename(state: dict) -> StateReplacement:
            out: dict[str, Any] = {}
            for k, v in state.items():
                if k.startswith(_SCOPE_PREFIXES):
                    continue  # Prefixed keys handled by FnAgent, not transform
                new_key = mapping.get(k, k)
                out[new_key] = v
            return StateReplacement(out)
        _rename.__name__ = f"rename_{'_'.join(mapping.keys())}"
        return _rename

    @staticmethod
    def default(**defaults: Any) -> Callable[[dict], StateDelta]:
        """Fill missing keys with default values. Existing keys are not overwritten.

            >> S.default(confidence=0.5, language="en")
        """
        def _default(state: dict) -> StateDelta:
            updates = {k: v for k, v in defaults.items() if k not in state}
            return StateDelta(updates)
        _default.__name__ = f"default_{'_'.join(defaults.keys())}"
        return _default

    @staticmethod
    def merge(*keys: str, into: str, fn: Callable | None = None) -> Callable[[dict], StateDelta]:
        """Combine multiple keys into one. Default join is newline concatenation.

            >> S.merge("web", "papers", into="research")
            >> S.merge("a", "b", into="total", fn=lambda a, b: a + b)
        """
        def _merge(state: dict) -> StateDelta:
            values = [state[k] for k in keys if k in state]
            if fn is not None:
                merged = fn(*values)
            else:
                merged = "\n".join(str(v) for v in values)
            return StateDelta({into: merged})
        _merge.__name__ = f"merge_{'_'.join(keys)}_into_{into}"
        return _merge

    @staticmethod
    def transform(key: str, fn: Callable) -> Callable[[dict], StateDelta]:
        """Apply a function to a single state value.

            >> S.transform("text", str.upper)
            >> S.transform("score", lambda x: round(x, 2))
        """
        fn_name = getattr(fn, "__name__", "fn")
        def _transform(state: dict) -> StateDelta:
            if key in state:
                return StateDelta({key: fn(state[key])})
            return StateDelta({})
        _transform.__name__ = f"transform_{key}_{fn_name}"
        return _transform

    @staticmethod
    def guard(predicate: Callable[[dict], bool], msg: str = "State guard failed") -> Callable[[dict], StateDelta]:
        """Assert a state invariant. Raises ValueError if predicate is falsy.

            >> S.guard(lambda s: "key" in s, "Missing required key")
            >> S.guard(lambda s: float(s.get("score", 0)) > 0)
        """
        def _guard(state: dict) -> StateDelta:
            if not predicate(state):
                raise ValueError(msg)
            return StateDelta({})
        _guard.__name__ = "guard"
        return _guard

    @staticmethod
    def log(*keys: str, label: str = "") -> Callable[[dict], StateDelta]:
        """Debug-print selected keys (or all state if no keys given). Returns no updates.

            >> S.log("score", "confidence")
            >> S.log(label="after-writer")
        """
        def _log(state: dict) -> StateDelta:
            prefix = f"[{label}] " if label else ""
            if keys:
                subset = {k: state.get(k, "<missing>") for k in keys}
            else:
                subset = state
            print(f"{prefix}{subset}")
            return StateDelta({})
        _log.__name__ = f"log_{'_'.join(keys) if keys else 'all'}"
        return _log

    @staticmethod
    def compute(**factories: Callable) -> Callable[[dict], StateDelta]:
        """Derive new keys from the full state dict.

            >> S.compute(
                summary=lambda s: s["text"][:100],
                word_count=lambda s: len(s.get("text", "").split()),
            )
        """
        def _compute(state: dict) -> StateDelta:
            return StateDelta({k: fn(state) for k, fn in factories.items()})
        _compute.__name__ = f"compute_{'_'.join(factories.keys())}"
        return _compute

    @staticmethod
    def set(**values: Any) -> Callable[[dict], StateDelta]:
        """Set explicit key-value pairs in state (additive merge).

            >> S.set(stage="review", counter=0)
        """
        def _set(state: dict) -> StateDelta:
            return StateDelta(dict(values))
        _set.__name__ = f"set_{'_'.join(values.keys())}"
        return _set
