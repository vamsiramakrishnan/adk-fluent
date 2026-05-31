"""Code IR — structured representation of generated Python code.

Instead of building source strings directly, the generator builds IR nodes
that can be validated, transformed, and emitted to multiple targets
(.py, .pyi, tests).
"""

# Canonical module identity.
#
# This package is reachable under two import names depending on where Python
# is invoked from and which import path a caller uses:
#
#   * ``code_ir``          — a bare import (used by ``generator.module_builder``,
#                            which does ``from code_ir import ModuleNode``)
#   * ``scripts.code_ir``  — the namespaced import (used by tests via
#                            ``from scripts.code_ir import emit_python``)
#
# Python treats these as two *separate* modules unless we intervene. If both
# names execute this ``__init__`` independently we end up with two distinct
# ``ModuleNode`` (and every other node) class objects. IR built under one
# identity then fails ``isinstance()`` checks inside an emitter compiled under
# the other, surfacing as ``TypeError: Cannot emit Python for <ModuleNode>``.
# Whether the bug appears depends purely on test/import ordering, which is why
# the two suites pass alone but fail together.
#
# To guarantee a single identity, the FIRST name to import wins and becomes the
# canonical module. Any later import under the OTHER name short-circuits: it
# rebinds itself (and all submodules) to the canonical objects instead of
# re-executing this package. The aliasing is symmetric, so it is correct
# regardless of which name loads first.
import sys as _sys

_ALIASES = ("code_ir", "scripts.code_ir")


def _adopt_canonical(canonical_name: str) -> bool:
    """If a canonical sibling is already imported, alias to it and stop.

    Returns ``True`` when this module has been redirected to an
    already-loaded canonical package (so the caller should skip the rest of
    ``__init__``), ``False`` when this module IS the canonical one.
    """
    canonical = _sys.modules.get(canonical_name)
    if canonical is None or canonical is _sys.modules[__name__]:
        return False
    # A sibling identity already executed — adopt all of its public attributes
    # and submodules so that node classes, emitters, etc. are shared objects.
    this = _sys.modules[__name__]
    for attr in getattr(canonical, "__all__", ()):  # noqa: B007
        setattr(this, attr, getattr(canonical, attr))
    this.__all__ = list(getattr(canonical, "__all__", ()))
    # Point this name (and its submodule names) at the canonical objects.
    _sys.modules[__name__] = canonical
    canonical_prefix = canonical.__name__ + "."
    this_prefix = __name__ + "."
    for mod_name, mod in list(_sys.modules.items()):
        if mod_name.startswith(canonical_prefix):
            _sys.modules[this_prefix + mod_name[len(canonical_prefix) :]] = mod
    return True


_redirected = any(_adopt_canonical(name) for name in _ALIASES if name != __name__)

if not _redirected:
    # This module is the canonical one. Register both alias names so that a
    # later ``import`` under the other name finds us and short-circuits above
    # instead of re-executing the package.
    for _alias in _ALIASES:
        _sys.modules.setdefault(_alias, _sys.modules[__name__])

# These imports must follow the canonical-identity setup above so that the
# names resolve to the single shared module objects (E402 is expected).
from .emitters import emit_python, emit_stub  # noqa: E402
from .ts_emitter import emit_dts, emit_typescript  # noqa: E402
from .nodes import (  # noqa: E402
    AppendStmt,
    AssignStmt,
    AsyncForYield,
    ClassAttr,
    ClassNode,
    DeprecationStmt,
    ForAppendStmt,
    ForkAndAssign,
    IfStmt,
    ImportStmt,
    MethodNode,
    ModuleNode,
    Param,
    RawStmt,
    ReturnStmt,
    Stmt,
    SubscriptAssign,
)
from .utils import split_at_commas  # noqa: E402

__all__ = [
    "AppendStmt",
    "AssignStmt",
    "AsyncForYield",
    "ClassAttr",
    "ClassNode",
    "DeprecationStmt",
    "ForAppendStmt",
    "ForkAndAssign",
    "IfStmt",
    "ImportStmt",
    "MethodNode",
    "ModuleNode",
    "Param",
    "RawStmt",
    "ReturnStmt",
    "Stmt",
    "SubscriptAssign",
    "emit_dts",
    "emit_python",
    "emit_stub",
    "emit_typescript",
    "split_at_commas",
]
