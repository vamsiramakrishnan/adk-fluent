"""Namespace protocol — shared contract for all namespace spec types.

Every namespace module (S, C, P, A, M, T) exposes composable spec objects.
This module defines the runtime-checkable protocol they all conform to,
plus shared utilities for fingerprinting and key metadata merging.

This protocol is *descriptive*, not prescriptive — it documents the
contract that all six namespaces already satisfy after uniformization.
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol, runtime_checkable

__all__ = ["NamespaceSpec", "merge_keysets", "fingerprint_spec"]


@runtime_checkable
class NamespaceSpec(Protocol):
    """Protocol that all namespace spec types should satisfy.

    Conforming types: STransform, CTransform, PTransform, ATransform,
    MComposite, TComposite.
    """

    @property
    def _kind(self) -> str:
        """Discriminator tag for IR serialization and introspection."""
        ...

    def _as_list(self) -> tuple[Any, ...]:
        """Flatten for composite building. Leaf types return ``(self,)``."""
        ...

    @property
    def _reads_keys(self) -> frozenset[str] | None:
        """State keys this spec reads. ``None`` means opaque (full state)."""
        ...

    @property
    def _writes_keys(self) -> frozenset[str] | None:
        """State keys this spec writes. ``None`` means opaque (full state)."""
        ...


def merge_keysets(
    a: frozenset[str] | None,
    b: frozenset[str] | None,
) -> frozenset[str] | None:
    """Merge two key metadata sets. ``None`` means opaque (full state).

    Used by composition operators across all namespaces.
    """
    if a is None or b is None:
        return None
    return a | b


def fingerprint_spec(spec: Any) -> str:
    """SHA-256 fingerprint of a spec's structural content.

    Works across all namespace types. Returns a 16-char hex digest
    suitable for caching and versioning.
    """
    h = hashlib.sha256()
    _hash_spec(h, spec)
    return h.hexdigest()[:16]


def _hash_spec(h: Any, spec: Any) -> None:
    """Recursively hash a spec tree."""
    kind = getattr(spec, "_kind", type(spec).__name__)
    h.update(kind.encode("utf-8"))

    # Hash children if composite
    children = getattr(spec, "_as_list", lambda: (spec,))()
    if children != (spec,):
        for child in children:
            _hash_spec(h, child)

    # Hash key metadata if present
    reads = getattr(spec, "_reads_keys", None)
    if reads is not None:
        for k in sorted(reads):
            h.update(f"r:{k}".encode())

    writes = getattr(spec, "_writes_keys", None)
    if writes is not None:
        for k in sorted(writes):
            h.update(f"w:{k}".encode())
