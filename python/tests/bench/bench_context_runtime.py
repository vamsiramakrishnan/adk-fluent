"""Benchmark: context runtime template + combined provider fastpaths.

Wave 4a pre-compiles ``{key}`` / ``{key?}`` placeholders in template
providers and combined-provider instructions into a flat segment tuple
so the per-turn cost is an ``O(segments)`` walk + one ``"".join`` —
no regex, no per-call closure allocation.

This bench isolates:

* Static template rendering (no placeholders) — expected: fastest path,
  just returns the literal.
* Small template (3 placeholders) vs. medium (10) vs. dense (20).
* Dynamic instruction with placeholders — slow path, still benefits
  from the module-level precompiled pattern.
* Combined provider (instruction + C.window) vs. raw provider — measures
  the fusion overhead with a mock session.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from adk_fluent._context import C, _compile_context_spec
from adk_fluent._context_providers import (
    _compile_template,
    _make_template_provider,
    _render_template,
)
from tests.bench._common import bench, report_header


def _state(n: int) -> dict[str, str]:
    return {f"k{i}": f"value_{i}" for i in range(n)}


def main() -> None:
    report_header("Context runtime benchmarks")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # ---- raw compile_template / render_template ------------------------
    static = "You are a helpful assistant. No placeholders here."
    small = "Hi {name}, your score is {score} ({grade})."
    medium = (
        "Role: {role}. Task: {task}. Context: {context}. Format: {format}. "
        "Audience: {audience}. Constraints: {c1}, {c2}, {c3}. Notes: {notes}."
    )
    dense = " ".join(f"{{k{i}}}" for i in range(20))

    small_segs = _compile_template(small)
    medium_segs = _compile_template(medium)
    dense_segs = _compile_template(dense)

    st_small = {"name": "Ada", "score": 97, "grade": "A"}
    st_medium = {
        "role": "reviewer",
        "task": "read code",
        "context": "PR #42",
        "format": "markdown",
        "audience": "engineers",
        "c1": "concise",
        "c2": "cite lines",
        "c3": "no fluff",
        "notes": "be fast",
    }
    st_dense = _state(20)

    bench("compile_template (static, 0 ph)", lambda: _compile_template(static), iters=200_000)
    bench("compile_template (small, 3 ph)", lambda: _compile_template(small), iters=200_000)
    bench("compile_template (medium, 10 ph)", lambda: _compile_template(medium), iters=100_000)
    bench("compile_template (dense, 20 ph)", lambda: _compile_template(dense), iters=100_000)

    bench("render small [3 ph]", lambda: _render_template(small_segs, st_small), iters=500_000)
    bench("render medium [10 ph]", lambda: _render_template(medium_segs, st_medium), iters=200_000)
    bench("render dense [20 ph]", lambda: _render_template(dense_segs, st_dense), iters=200_000)

    # ---- _make_template_provider end-to-end via async -------------------
    provider_small = _make_template_provider(small)
    provider_medium = _make_template_provider(medium)
    provider_static = _make_template_provider(static)

    ctx_small = SimpleNamespace(state=st_small)
    ctx_medium = SimpleNamespace(state=st_medium)

    bench(
        "template provider static",
        lambda: loop.run_until_complete(provider_static(ctx_small)),
        iters=100_000,
    )
    bench(
        "template provider small (3 ph)",
        lambda: loop.run_until_complete(provider_small(ctx_small)),
        iters=100_000,
    )
    bench(
        "template provider medium (10 ph)",
        lambda: loop.run_until_complete(provider_medium(ctx_medium)),
        iters=50_000,
    )

    # ---- combined provider: instruction + C spec ------------------------
    # ``C.from_state("extra")`` gives us a cheap spec_provider that only
    # reads state (no session scan), so the bench isolates the
    # instruction-resolve path that 4a touched.
    spec = C.from_state("extra")
    compiled_static = _compile_context_spec(
        developer_instruction="You are a helpful assistant. No placeholders here.",
        context_spec=spec,
    )
    compiled_small = _compile_context_spec(
        developer_instruction="Hi {name}, your score is {score} ({grade}).",
        context_spec=spec,
    )
    compiled_medium = _compile_context_spec(
        developer_instruction=medium,
        context_spec=spec,
    )

    prov_static = compiled_static["instruction"]
    prov_small = compiled_small["instruction"]
    prov_medium = compiled_medium["instruction"]

    state_with_extra = dict(st_medium)
    state_with_extra["extra"] = "extra context data"
    state_with_extra.update(st_small)
    ctx = SimpleNamespace(state=state_with_extra, session=SimpleNamespace(events=[]))

    bench(
        "combined provider [static]",
        lambda: loop.run_until_complete(prov_static(ctx)),
        iters=50_000,
    )
    bench(
        "combined provider [small 3 ph]",
        lambda: loop.run_until_complete(prov_small(ctx)),
        iters=50_000,
    )
    bench(
        "combined provider [medium 10 ph]",
        lambda: loop.run_until_complete(prov_medium(ctx)),
        iters=50_000,
    )

    loop.close()


if __name__ == "__main__":
    main()
