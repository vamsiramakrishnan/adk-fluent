"""Benchmark: S-transform chains (the state hot path).

Each S-transform in the current implementation rebuilds ``state`` via
``out = dict(state)`` before mutating. This benchmark measures chains of
different depths and widths so we can compare against a future
structural-sharing (HAMT) implementation.
"""

from __future__ import annotations

from adk_fluent import S

from tests.bench._common import bench, report_header


def main() -> None:
    report_header("S-transform chain benchmarks")

    small_state = {f"k{i}": i for i in range(8)}
    medium_state = {f"k{i}": i for i in range(64)}
    large_state = {f"k{i}": i for i in range(512)}

    from adk_fluent._transforms import _apply_result

    def run(transform, state: dict) -> None:
        _apply_result(state, transform(state))

    # pick — classic read-only reshape.
    pick4 = S.pick("k0", "k1", "k2", "k3")
    bench("pick(4 of 8)", lambda: run(pick4, small_state), iters=100_000)
    bench("pick(4 of 64)", lambda: run(pick4, medium_state), iters=100_000)
    bench("pick(4 of 512)", lambda: run(pick4, large_state), iters=100_000)

    # set — write path (copies state into new dict before mutating).
    set_one = S.set(new_key=42)
    bench("set(1 key into 8)", lambda: run(set_one, small_state), iters=100_000)
    bench("set(1 key into 64)", lambda: run(set_one, medium_state), iters=100_000)
    bench("set(1 key into 512)", lambda: run(set_one, large_state), iters=100_000)

    # Chained: pick >> rename >> set (realistic).
    chain = S.pick("k0", "k1", "k2", "k3") >> S.rename(k0="x0") >> S.set(done=True)
    bench("chain pick>>rename>>set [8]", lambda: run(chain, small_state), iters=100_000)
    bench("chain pick>>rename>>set [64]", lambda: run(chain, medium_state), iters=100_000)
    bench("chain pick>>rename>>set [512]", lambda: run(chain, large_state), iters=50_000)


if __name__ == "__main__":
    main()
