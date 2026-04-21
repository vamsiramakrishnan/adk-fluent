"""Parity test: ``object.__setattr__`` must be centralised in ``_frozen.py``.

Frozen dataclasses need a single sanctioned escape hatch for populating
derived fields in ``__post_init__``. That escape hatch lives in
:mod:`adk_fluent._frozen` as :func:`_set_frozen_fields`. Raw
``object.__setattr__`` calls outside that module reintroduce exactly the
scatter this test prevents.

The only allowed exception is ``backends/adk/_primitives.py``, which uses
``object.__setattr__`` to bypass pydantic ``BaseAgent`` validation — a
different pattern from frozen-dataclass ``__post_init__``. That file is
whitelisted explicitly so future pydantic sites still require a review.
"""

from __future__ import annotations

from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "adk_fluent"

# Files allowed to use raw ``object.__setattr__``. Every entry is justified.
ALLOWED = frozenset(
    {
        # The helper itself.
        SRC_ROOT / "_frozen.py",
        # Pydantic BaseAgent subclasses — __init__ path, not __post_init__.
        SRC_ROOT / "backends" / "adk" / "_primitives.py",
    }
)


def test_object_setattr_only_in_frozen_helper() -> None:
    offenders: list[tuple[Path, int, str]] = []
    for path in SRC_ROOT.rglob("*.py"):
        if path in ALLOWED:
            continue
        text = path.read_text(encoding="utf-8")
        if "object.__setattr__" not in text:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "object.__setattr__" in line:
                offenders.append((path, lineno, line.strip()))

    assert not offenders, (
        "Raw object.__setattr__ outside adk_fluent._frozen. "
        "Use _set_frozen_fields(self, field=value) in __post_init__ instead. "
        f"Offenders:\n"
        + "\n".join(f"  {p}:{ln}: {src}" for p, ln, src in offenders)
    )
