"""Shared microbench plumbing — stdlib only.

Usage::

    from tests.bench._common import bench

    bench("my-thing", iters=100_000, fn=lambda: do_something())
"""

from __future__ import annotations

import gc
import resource
import time
from collections.abc import Callable
from typing import Any

__all__ = ["bench", "report_header"]


def _rss_mb() -> float:
    """Best-effort resident-set-size in MB (Linux: KB; macOS: bytes)."""
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return 0.0
    # Linux reports KB, macOS reports bytes. Normalize heuristically.
    if usage > 10**8:  # > 100 MB in whatever units → probably bytes
        return usage / (1024 * 1024)
    return usage / 1024


def report_header(title: str) -> None:
    print("=" * 72)
    print(title)
    print("=" * 72)


def bench(
    name: str,
    fn: Callable[[], Any],
    *,
    iters: int = 100_000,
    warmup: int = 1_000,
) -> float:
    """Run ``fn`` ``iters`` times and print ns/op.

    Returns ns/op for programmatic comparison. ``fn`` must be a nullary
    callable; wrap closures accordingly.
    """
    for _ in range(warmup):
        fn()

    gc.collect()
    gc.disable()
    try:
        start = time.perf_counter_ns()
        for _ in range(iters):
            fn()
        elapsed = time.perf_counter_ns() - start
    finally:
        gc.enable()

    ns_per_op = elapsed / iters
    print(f"{name:<48s} {iters:>10,} iters  {ns_per_op:>10.1f} ns/op  {_rss_mb():>7.1f} MB rss")
    return ns_per_op
