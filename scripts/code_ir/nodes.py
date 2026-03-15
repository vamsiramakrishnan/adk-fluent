"""IR node definitions — structured representation of generated Python code.

Statement nodes are frozen dataclasses (immutable values).
Structural nodes (Method, Class, Module) are mutable for incremental construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Statement Nodes (frozen dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReturnStmt:
    """return <expr>"""

    expr: str


@dataclass(frozen=True)
class AssignStmt:
    """<target> = <value>"""

    target: str
    value: str


@dataclass(frozen=True)
class SubscriptAssign:
    """<target>[<key>] = <value>"""

    target: str
    key: str
    value: str


@dataclass(frozen=True)
class AppendStmt:
    """<target>[<key>].append(<value>)"""

    target: str
    key: str
    value: str


@dataclass(frozen=True)
class ForAppendStmt:
    """for <var> in <iterable>: <target>[<key>].append(<var>)"""

    var: str
    iterable: str
    target: str
    key: str


@dataclass(frozen=True)
class IfStmt:
    """if <condition>: <body>"""

    condition: str
    body: tuple  # tuple of statement nodes (frozen requires tuple, not list)


@dataclass(frozen=True)
class ImportStmt:
    """from <module> import <name>; then execute <call>"""

    module: str
    name: str
    call: str


@dataclass(frozen=True)
class RawStmt:
    """Escape hatch for complex statements that don't fit the IR."""

    code: str


@dataclass(frozen=True)
class ForkAndAssign:
    """self = self._maybe_fork_for_mutation() — copy-on-write guard."""


@dataclass(frozen=True)
class DeprecationStmt:
    """Emit a DeprecationWarning for a renamed method.

    Generates::

        import warnings
        warnings.warn(
            ".{old_name}() is deprecated, use .{new_name}() instead",
            DeprecationWarning,
            stacklevel=2,
        )
    """

    old_name: str
    new_name: str


@dataclass(frozen=True)
class AsyncForYield:
    """Async generator delegation: import helper, async-for-yield.

    Generates::

        from {module} import {func}
        async for {var} in {func}({args}):
            yield {var}
    """

    module: str
    func: str
    args: str
    var: str = "chunk"


Stmt = (
    ReturnStmt
    | AssignStmt
    | SubscriptAssign
    | AppendStmt
    | ForAppendStmt
    | IfStmt
    | ImportStmt
    | RawStmt
    | ForkAndAssign
    | DeprecationStmt
    | AsyncForYield
)


# ---------------------------------------------------------------------------
# Structural Nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Param:
    """A method parameter."""

    name: str
    type: str | None = None
    default: str | None = None
    keyword_only: bool = False


@dataclass
class MethodNode:
    """A method in a class."""

    name: str
    params: list[Param] = field(default_factory=list)
    returns: str | None = None
    doc: str = ""
    body: list[Stmt] = field(default_factory=list)
    is_async: bool = False
    is_generator: bool = False  # for async generators


@dataclass
class ClassAttr:
    """A class-level attribute."""

    name: str
    type_hint: str
    value: str  # repr of the value


@dataclass
class ClassNode:
    """A builder class."""

    name: str
    bases: list[str] = field(default_factory=list)
    doc: str = ""
    attrs: list[ClassAttr] = field(default_factory=list)
    methods: list[MethodNode] = field(default_factory=list)


@dataclass
class ModuleNode:
    """A Python module."""

    doc: str = ""
    imports: list[str] = field(default_factory=list)
    classes: list[ClassNode] = field(default_factory=list)
    type_checking_imports: list[str] = field(default_factory=list)
    optional_imports: list[tuple[str, str]] = field(default_factory=list)
    """Imports that require optional dependencies.

    Each entry is ``(import_line, fallback_assignment)`` — emitted as::

        try:
            <import_line>
        except (ImportError, ModuleNotFoundError):
            <fallback_assignment>
    """
