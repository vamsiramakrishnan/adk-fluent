"""State transform factories for the >> operator. Hand-written, not generated.

Each factory returns a plain callable (dict -> dict) that composes
with >> for free via _fn_step wrapping.

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
from typing import Any, Callable

__all__ = ["S"]


class S:
    """State transform factories. Each method returns a callable for use with >>."""

    @staticmethod
    def pick(*keys: str) -> Callable[[dict], dict]:
        """Keep only the specified keys from state.

            >> S.pick("name", "score")
        """
        def _pick(state: dict) -> dict:
            return {k: state[k] for k in keys if k in state}
        _pick.__name__ = f"pick_{'_'.join(keys)}"
        return _pick

    @staticmethod
    def drop(*keys: str) -> Callable[[dict], dict]:
        """Remove the specified keys from state.

            >> S.drop("_internal", "_debug")
        """
        drop_set = set(keys)
        def _drop(state: dict) -> dict:
            return {k: v for k, v in state.items() if k not in drop_set}
        _drop.__name__ = f"drop_{'_'.join(keys)}"
        return _drop

    @staticmethod
    def rename(**mapping: str) -> Callable[[dict], dict]:
        """Rename state keys. Unmapped keys pass through unchanged.

            >> S.rename(result="input", raw_score="score")
        """
        reverse = {v: k for k, v in mapping.items()}
        def _rename(state: dict) -> dict:
            out = {}
            for k, v in state.items():
                new_key = mapping.get(k, k)
                out[new_key] = v
            return out
        _rename.__name__ = f"rename_{'_'.join(mapping.keys())}"
        return _rename

    @staticmethod
    def default(**defaults: Any) -> Callable[[dict], dict]:
        """Fill missing keys with default values. Existing keys are not overwritten.

            >> S.default(confidence=0.5, language="en")
        """
        def _default(state: dict) -> dict:
            return {k: state.get(k, v) for k, v in {**defaults, **state}.items()}
        _default.__name__ = f"default_{'_'.join(defaults.keys())}"
        return _default

    @staticmethod
    def merge(*keys: str, into: str, fn: Callable | None = None) -> Callable[[dict], dict]:
        """Combine multiple keys into one. Default join is newline concatenation.

            >> S.merge("web", "papers", into="research")
            >> S.merge("a", "b", into="total", fn=lambda a, b: a + b)
        """
        def _merge(state: dict) -> dict:
            values = [state[k] for k in keys if k in state]
            if fn is not None:
                merged = fn(*values)
            else:
                merged = "\n".join(str(v) for v in values)
            return {into: merged}
        _merge.__name__ = f"merge_{'_'.join(keys)}_into_{into}"
        return _merge

    @staticmethod
    def transform(key: str, fn: Callable) -> Callable[[dict], dict]:
        """Apply a function to a single state value.

            >> S.transform("text", str.upper)
            >> S.transform("score", lambda x: round(x, 2))
        """
        fn_name = getattr(fn, "__name__", "fn")
        def _transform(state: dict) -> dict:
            if key in state:
                return {key: fn(state[key])}
            return {}
        _transform.__name__ = f"transform_{key}_{fn_name}"
        return _transform

    @staticmethod
    def guard(predicate: Callable[[dict], bool], msg: str = "State guard failed") -> Callable[[dict], dict]:
        """Assert a state invariant. Raises ValueError if predicate is falsy.

            >> S.guard(lambda s: "key" in s, "Missing required key")
            >> S.guard(lambda s: float(s.get("score", 0)) > 0)
        """
        def _guard(state: dict) -> dict:
            if not predicate(state):
                raise ValueError(msg)
            return {}
        _guard.__name__ = "guard"
        return _guard

    @staticmethod
    def log(*keys: str, label: str = "") -> Callable[[dict], dict]:
        """Debug-print selected keys (or all state if no keys given). Returns no updates.

            >> S.log("score", "confidence")
            >> S.log(label="after-writer")
        """
        def _log(state: dict) -> dict:
            prefix = f"[{label}] " if label else ""
            if keys:
                subset = {k: state.get(k, "<missing>") for k in keys}
            else:
                subset = state
            print(f"{prefix}{subset}")
            return {}
        _log.__name__ = f"log_{'_'.join(keys) if keys else 'all'}"
        return _log

    @staticmethod
    def compute(**factories: Callable) -> Callable[[dict], dict]:
        """Derive new keys from the full state dict.

            >> S.compute(
                summary=lambda s: s["text"][:100],
                word_count=lambda s: len(s.get("text", "").split()),
            )
        """
        def _compute(state: dict) -> dict:
            return {k: fn(state) for k, fn in factories.items()}
        _compute.__name__ = f"compute_{'_'.join(factories.keys())}"
        return _compute
