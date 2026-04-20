"""Composite — base class for namespace composite types.

One class, one truth. All namespace composites (MComposite, TComposite,
EComposite, GComposite) inherit from this instead of reinventing storage,
``__or__``, ``__repr__``, ``_kind``, and ``_as_list`` independently.

Uses ``__init_subclass__`` — the Pythonic way to customize class creation
without metaclass complexity.  Subclasses become 5-line declarations::

    class MComposite(Composite, kind="middleware_chain"):
        def to_stack(self) -> list[Any]:
            return list(self._items)

Design principles:
- ``_items`` is the single source of truth for child storage
- ``|`` is the composition operator (all namespaces)
- ``__repr__`` shows discriminator info from children
- ``_kind``, ``_as_list``, ``_reads_keys``, ``_writes_keys`` satisfy NamespaceSpec
"""

from __future__ import annotations

from typing import Any, ClassVar

__all__ = ["Composite"]


class Composite:
    """Base for all namespace composite types.

    Provides: ``__or__``, ``__ror__``, ``__rrshift__``, ``__repr__``, ``__len__``,
    ``_kind``, ``_as_list``, ``_reads_keys``, ``_writes_keys``.

    Subclasses may set ``_builder_attach_method`` to the Builder method
    name that accepts this composite (e.g. ``"middleware"``, ``"guard"``,
    ``"tools"``). When set, ``Composite >> Builder`` attaches the composite
    to the builder and returns the modified builder — making the operator
    grammar uniform across namespaces. See ``docs/reference/operators.md``.
    """

    __slots__ = ("_items", "_kind_override")

    _kind_tag: ClassVar[str]
    _child_repr: ClassVar[str] = "_kind"  # attribute to show in __repr__
    _builder_attach_method: ClassVar[str | None] = None

    def __init_subclass__(cls, *, kind: str = "", **kw: Any) -> None:
        super().__init_subclass__(**kw)
        if kind:
            cls._kind_tag = kind

    def __init__(self, items: list[Any] | None = None, *, kind: str = "") -> None:
        self._items: list[Any] = list(items or [])
        self._kind_override = kind

    # -- NamespaceSpec protocol -----------------------------------------------

    @property
    def _kind(self) -> str:
        """Discriminator tag for IR serialization."""
        return self._kind_override or self._kind_tag

    def _as_list(self) -> tuple[Any, ...]:
        """Flatten for composite building."""
        return tuple(self._items)

    @property
    def _reads_keys(self) -> frozenset[str] | None:
        """Default: opaque (returns ``None``). Override in subclass if computable."""
        return None

    @property
    def _writes_keys(self) -> frozenset[str] | None:
        """Default: opaque (returns ``None``). Override in subclass if computable."""
        return None

    # -- Composition: | -------------------------------------------------------

    def __or__(self, other: Any) -> Any:
        if isinstance(other, type(self)):
            return type(self)(self._items + other._items)
        return type(self)(self._items + [other])

    def __ror__(self, other: Any) -> Any:
        if isinstance(other, type(self)):
            return type(self)(other._items + self._items)
        return type(self)([other] + self._items)

    # -- Attach to builder: Composite >> Builder -----------------------------

    def __rshift__(self, other: Any) -> Any:
        """Attach this composite to a builder: ``Composite >> Builder``.

        Subclasses opt in by setting ``_builder_attach_method`` to the
        name of the builder method that accepts this composite
        (e.g. ``"middleware"``, ``"guard"``, ``"tools"``). When the
        right-hand side is not a builder, returns ``NotImplemented`` so
        Python tries the other side's ``__rrshift__``.
        """
        from adk_fluent._base import BuilderBase

        if not isinstance(other, BuilderBase):
            return NotImplemented
        method = self._builder_attach_method
        if method is None:
            return NotImplemented
        return getattr(other, method)(self)

    # -- Introspection --------------------------------------------------------

    def __repr__(self) -> str:
        attr = self._child_repr
        names = [getattr(item, attr, type(item).__name__) for item in self._items]
        return f"{type(self).__name__}([{', '.join(str(n) for n in names)}])"

    def __len__(self) -> int:
        return len(self._items)
