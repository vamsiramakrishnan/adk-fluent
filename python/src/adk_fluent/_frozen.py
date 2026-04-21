"""Sanctioned mutation helper for frozen dataclasses in __post_init__.

Frozen dataclasses cannot assign to their own fields after __init__, but
``__post_init__`` often needs to populate derived fields from declared
ones. ``object.__setattr__`` is the escape hatch; this helper keeps all
uses of that escape hatch in one named entrypoint so the intent is clear
at every call site and there's a single grep to find them all.

Usage::

    @dataclass(frozen=True, slots=True)
    class CComposite(CTransform):
        blocks: tuple[CTransform, ...] = ()

        def __post_init__(self) -> None:
            _set_frozen_fields(
                self,
                include_contents=_derive_include_contents(self.blocks),
                instruction_provider=_make_composite_provider(self.blocks),
            )

This is the ONLY sanctioned place to bypass a frozen dataclass's
immutability. Raw ``object.__setattr__(self, ...)`` calls outside this
module are reviewed-and-rejected by the parity test suite.
"""

from __future__ import annotations

from typing import Any

__all__ = ["_set_frozen_fields"]


def _set_frozen_fields(obj: Any, /, **fields: Any) -> None:
    """Populate derived fields on a frozen dataclass during __post_init__.

    Args:
        obj: The frozen dataclass instance being initialised.
        **fields: field_name=value pairs to assign.

    This exists so every bypass of ``@dataclass(frozen=True)`` immutability
    has a single, greppable name. Do not use it outside ``__post_init__``.
    """
    for name, value in fields.items():
        object.__setattr__(obj, name, value)
