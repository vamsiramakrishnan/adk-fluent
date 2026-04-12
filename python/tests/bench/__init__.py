"""Stdlib-only microbenchmarks for adk-fluent hot paths.

These benchmarks are intentionally dependency-free (no pytest-benchmark, no
google-adk) so they can run in any environment and produce stable absolute
numbers for before/after comparisons during performance work.

Run a single bench::

    python -m tests.bench.bench_tape_record

Run all benches::

    python -m tests.bench

Each bench prints one line per measurement of the form::

    <name>: <iterations> iters, <ns/op> ns/op, <MB> MB resident
"""
