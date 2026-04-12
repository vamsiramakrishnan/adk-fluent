"""Run all microbenchmarks. Usage: python -m tests.bench"""

from __future__ import annotations


def main() -> None:
    from tests.bench import (
        bench_builder_clone,
        bench_context_providers,
        bench_eval_gate,
        bench_middleware_stack,
        bench_prompt_render,
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
    print()
    bench_context_providers.main()
    print()
    bench_prompt_render.main()
    print()
    bench_eval_gate.main()


if __name__ == "__main__":
    main()
