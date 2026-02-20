"""Code IR — structured representation of generated Python code.

Instead of building source strings directly, the generator builds IR nodes
that can be validated, transformed, and emitted to multiple targets
(.py, .pyi, tests).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


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


Stmt = Union[
    ReturnStmt, AssignStmt, SubscriptAssign, AppendStmt,
    ForAppendStmt, IfStmt, ImportStmt, RawStmt,
]


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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _emit_param(p: Param) -> str:
    """Format a single parameter."""
    result = p.name
    if p.type is not None:
        # Don't add type annotation if the name already contains special chars
        # like *args — the * is part of the name
        if p.name.startswith("*") or p.name.startswith("**"):
            result = f"{p.name}: {p.type}"
        else:
            result = f"{p.name}: {p.type}"
    if p.default is not None:
        result = f"{result} = {p.default}"
    return result


def _emit_stmt(stmt: Stmt, indent: str = "        ") -> str:
    """Emit a single statement with the given indentation."""
    if isinstance(stmt, ReturnStmt):
        return f"{indent}return {stmt.expr}"
    elif isinstance(stmt, AssignStmt):
        return f"{indent}{stmt.target} = {stmt.value}"
    elif isinstance(stmt, SubscriptAssign):
        return f'{indent}{stmt.target}["{stmt.key}"] = {stmt.value}'
    elif isinstance(stmt, AppendStmt):
        return f'{indent}{stmt.target}["{stmt.key}"].append({stmt.value})'
    elif isinstance(stmt, ForAppendStmt):
        lines = [
            f"{indent}for {stmt.var} in {stmt.iterable}:",
            f'{indent}    {stmt.target}["{stmt.key}"].append({stmt.var})',
        ]
        return "\n".join(lines)
    elif isinstance(stmt, IfStmt):
        lines = [f"{indent}if {stmt.condition}:"]
        for s in stmt.body:
            lines.append(_emit_stmt(s, indent + "    "))
        return "\n".join(lines)
    elif isinstance(stmt, ImportStmt):
        lines = [
            f"{indent}from {stmt.module} import {stmt.name}",
            f"{indent}{stmt.call}",
        ]
        return "\n".join(lines)
    elif isinstance(stmt, RawStmt):
        raw_lines = stmt.code.split("\n")
        return "\n".join(f"{indent}{line}" for line in raw_lines)
    else:
        raise TypeError(f"Unknown statement type: {type(stmt)}")


def _build_param_list(params: list[Param]) -> str:
    """Build the parameter list string, handling keyword-only params."""
    parts: list[str] = []
    star_inserted = False
    for p in params:
        if p.keyword_only and not star_inserted:
            parts.append("*")
            star_inserted = True
        parts.append(_emit_param(p))
    return ", ".join(parts)


def _emit_method_python(m: MethodNode, indent: str = "    ") -> str:
    """Emit a method with its body."""
    prefix = "async " if m.is_async else ""
    params_str = _build_param_list(m.params)
    ret = f" -> {m.returns}" if m.returns else ""
    lines = [f"{indent}{prefix}def {m.name}({params_str}){ret}:"]

    if m.doc:
        lines.append(f'{indent}    """{m.doc}"""')

    if m.body:
        for stmt in m.body:
            lines.append(_emit_stmt(stmt, indent + "    "))
    elif not m.doc:
        lines.append(f"{indent}    ...")

    return "\n".join(lines)


def _emit_class_python(c: ClassNode) -> str:
    """Emit a full class definition."""
    bases_str = f"({', '.join(c.bases)})" if c.bases else ""
    lines = [f"class {c.name}{bases_str}:"]

    if c.doc:
        lines.append(f'    """{c.doc}"""')

    if c.attrs:
        for attr in c.attrs:
            if attr.type_hint:
                lines.append(f"    {attr.name}: {attr.type_hint} = {attr.value}")
            else:
                lines.append(f"    {attr.name} = {attr.value}")

    if c.attrs and c.methods:
        lines.append("")

    for i, method in enumerate(c.methods):
        lines.append(_emit_method_python(method))
        if i < len(c.methods) - 1:
            lines.append("")

    if not c.doc and not c.attrs and not c.methods:
        lines.append("    ...")

    return "\n".join(lines)


def _emit_module_python(mod: ModuleNode) -> str:
    """Emit a full module with deduplicated imports."""
    lines: list[str] = []

    if mod.doc:
        lines.append(f'"""{mod.doc}"""')
        lines.append("")

    # Deduplicate and sort imports
    if mod.imports:
        unique_imports = sorted(set(mod.imports))
        for imp in unique_imports:
            lines.append(imp)
        lines.append("")

    for i, cls in enumerate(mod.classes):
        if i > 0:
            lines.append("")
            lines.append("")
        lines.append(_emit_class_python(cls))

    lines.append("")
    return "\n".join(lines)


def _emit_method_stub(m: MethodNode, indent: str = "    ") -> str:
    """Emit a method stub (body is just ...)."""
    prefix = "async " if m.is_async else ""
    params_str = _build_param_list(m.params)
    ret = f" -> {m.returns}" if m.returns else ""
    return f"{indent}{prefix}def {m.name}({params_str}){ret}: ..."


def _emit_class_stub(c: ClassNode) -> str:
    """Emit a class stub."""
    bases_str = f"({', '.join(c.bases)})" if c.bases else ""
    lines = [f"class {c.name}{bases_str}:"]

    if c.doc:
        lines.append(f'    """{c.doc}"""')

    if c.attrs:
        for attr in c.attrs:
            if attr.type_hint:
                lines.append(f"    {attr.name}: {attr.type_hint} = {attr.value}")
            else:
                lines.append(f"    {attr.name} = {attr.value}")

    for method in c.methods:
        lines.append(_emit_method_stub(method))

    if not c.doc and not c.attrs and not c.methods:
        lines.append("    ...")

    return "\n".join(lines)


def _emit_module_stub(mod: ModuleNode) -> str:
    """Emit a module stub."""
    lines: list[str] = []

    if mod.doc:
        lines.append(f'"""{mod.doc}"""')
        lines.append("")

    # Deduplicate and sort imports
    if mod.imports:
        unique_imports = sorted(set(mod.imports))
        for imp in unique_imports:
            lines.append(imp)
        lines.append("")

    for i, cls in enumerate(mod.classes):
        if i > 0:
            lines.append("")
            lines.append("")
        lines.append(_emit_class_stub(cls))

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def emit_python(node: MethodNode | ClassNode | ModuleNode) -> str:
    """Emit Python source code from an IR node."""
    if isinstance(node, MethodNode):
        return _emit_method_python(node)
    elif isinstance(node, ClassNode):
        return _emit_class_python(node)
    elif isinstance(node, ModuleNode):
        return _emit_module_python(node)
    else:
        raise TypeError(f"Cannot emit Python for {type(node)}")


def emit_stub(node: MethodNode | ClassNode | ModuleNode) -> str:
    """Emit .pyi type stub from an IR node."""
    if isinstance(node, MethodNode):
        return _emit_method_stub(node)
    elif isinstance(node, ClassNode):
        return _emit_class_stub(node)
    elif isinstance(node, ModuleNode):
        return _emit_module_stub(node)
    else:
        raise TypeError(f"Cannot emit stub for {type(node)}")
