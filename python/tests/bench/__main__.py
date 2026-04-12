"""Run all microbenchmarks. Usage: python -m tests.bench"""

from __future__ import annotations


def main() -> None:
    from tests.bench import (
        bench_builder_clone,
        bench_middleware_stack,
        bench_state_chain,
        bench_tape_record,
    )

    bench_tape_record.main()
    print()
    bench_state_chain.main()
    print()
    bench_middleware_stack.main()
    print()
    bench_builder_clone.main()


if __name__ == "__main__":
    main()
