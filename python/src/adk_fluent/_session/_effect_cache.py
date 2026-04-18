"""EffectCache — idempotency cache for effectful tool calls (Phase E).

Borrowed-idea lineage:
    Temporal / Restate / Inngest ``ctx.run`` — record the outcome of a
    side-effect once, then replay it on resume instead of re-executing.
    Keys are user-supplied so the cache survives retries, resumes, and
    cross-session reuse.

The cache sits on :class:`SessionStore` and is consulted by the harness
``before_tool`` interceptor. When a tool is marked ``.effectful(key=...)``:

- first call: the cache misses, the tool runs, and the return value is
  stored keyed by ``(tool_name, key)``.
- subsequent calls with the same key: cache hits and the stored value
  is returned without invoking the tool — an :class:`EffectRecorded`
  event (``source="cache"``) lands on the tape for audit.

The cache is deliberately dumb: no TTL eviction thread, no LRU. TTL is
checked on lookup and expired entries are dropped. Scope is an opaque
string that callers can use to partition entries (``"session"``,
``"user:alice"``, ``"turn:42"``); lookup key is ``(scope, tool, key)``.
"""

from __future__ import annotations

import contextlib
import contextvars
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

__all__ = ["EffectCache", "EffectEntry", "active_cache", "use_cache"]


@dataclass(frozen=True, slots=True)
class EffectEntry:
    """One cached side-effect result.

    Attributes:
        tool_name: Name of the effectful tool.
        key: User-supplied idempotency key.
        scope: Partition bucket — defaults to ``"session"``.
        value: The return value from the first invocation. Opaque to the cache.
        stored_at: Monotonic timestamp when the entry was written.
        ttl_seconds: Lifetime; ``0`` means "no expiry".
        metadata: Caller-attached metadata for audit/debugging.
    """

    tool_name: str
    key: str
    scope: str
    value: Any
    stored_at: float
    ttl_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now: float | None = None) -> bool:
        if self.ttl_seconds <= 0:
            return False
        t = time.monotonic() if now is None else now
        return (t - self.stored_at) > self.ttl_seconds


class EffectCache:
    """In-memory cache of effectful tool outcomes.

    Thread-safe for reads; writes assume single-threaded session-scoped
    use (matches the rest of the harness). Expired entries are dropped
    lazily on lookup.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], EffectEntry] = {}

    # ------------------------------------------------------------------
    # Lookup / store
    # ------------------------------------------------------------------

    def _composite_key(self, tool_name: str, key: str, scope: str) -> tuple[str, str, str]:
        return (scope, tool_name, key)

    def get(self, tool_name: str, key: str, *, scope: str = "session") -> EffectEntry | None:
        """Return the cached entry or ``None`` when absent/expired."""
        ckey = self._composite_key(tool_name, key, scope)
        entry = self._entries.get(ckey)
        if entry is None:
            return None
        if entry.is_expired():
            del self._entries[ckey]
            return None
        return entry

    def put(
        self,
        tool_name: str,
        key: str,
        value: Any,
        *,
        scope: str = "session",
        ttl_seconds: float = 0.0,
        **metadata: Any,
    ) -> EffectEntry:
        """Store ``value`` under ``(scope, tool_name, key)``.

        Returns the stored :class:`EffectEntry` so callers can record it
        onto the tape alongside an :class:`EffectRecorded` event.
        """
        entry = EffectEntry(
            tool_name=tool_name,
            key=key,
            scope=scope,
            value=value,
            stored_at=time.monotonic(),
            ttl_seconds=ttl_seconds,
            metadata=dict(metadata),
        )
        self._entries[self._composite_key(tool_name, key, scope)] = entry
        return entry

    def invalidate(self, tool_name: str, key: str, *, scope: str = "session") -> bool:
        """Drop a single entry. Returns True if something was removed."""
        return self._entries.pop(self._composite_key(tool_name, key, scope), None) is not None

    def clear_scope(self, scope: str) -> int:
        """Drop every entry under ``scope``. Returns the number removed."""
        victims = [k for k in self._entries if k[0] == scope]
        for v in victims:
            del self._entries[v]
        return len(victims)

    def clear(self) -> None:
        """Drop every cached entry."""
        self._entries.clear()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._entries)

    def summary(self) -> dict[str, Any]:
        by_scope: dict[str, int] = {}
        for (scope, _tool, _key), _entry in self._entries.items():
            by_scope[scope] = by_scope.get(scope, 0) + 1
        return {
            "size": len(self._entries),
            "by_scope": by_scope,
        }

    def __repr__(self) -> str:
        return f"EffectCache(size={len(self._entries)})"


# ---------------------------------------------------------------------------
# Ambient cache (ContextVar)
# ---------------------------------------------------------------------------

_active_cache: contextvars.ContextVar[EffectCache | None] = contextvars.ContextVar(
    "adkf_active_effect_cache", default=None
)


def active_cache() -> EffectCache | None:
    """Return the ambient :class:`EffectCache` for the current task, if any."""
    return _active_cache.get()


@contextlib.contextmanager
def use_cache(cache: EffectCache | None) -> Iterator[None]:
    """Activate ``cache`` as the ambient cache inside the ``with`` block."""
    token = _active_cache.set(cache)
    try:
        yield
    finally:
        _active_cache.reset(token)
