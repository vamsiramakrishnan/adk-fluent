"""Code IR — structured representation of generated Python code.

Instead of building source strings directly, the generator builds IR nodes
that can be validated, transformed, and emitted to multiple targets
(.py, .pyi, tests).
"""

# Ensure module identity: whether loaded as 'scripts.code_ir' (from project root)
# or 'code_ir' (from scripts/ directory), the module object is the same.
# This prevents isinstance() failures when IR nodes cross module boundaries.
import sys as _sys

_sys.modules.setdefault("code_ir", _sys.modules[__name__])
if "scripts.code_ir" in _sys.modules and _sys.modules["scripts.code_ir"] is not _sys.modules.get("code_ir"):
    # scripts.code_ir was loaded separately — alias its submodules too
    _sys.modules.setdefault("scripts.code_ir", _sys.modules[__name__])

from .emitters import emit_python, emit_stub
from .ts_emitter import emit_dts, emit_typescript
from .nodes import (
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
from .utils import split_at_commas

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
