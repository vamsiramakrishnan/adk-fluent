"""Code emitters — convert IR nodes to Python source or .pyi stubs."""

from __future__ import annotations

import shutil
import subprocess

from .nodes import (
    AppendStmt,
    AssignStmt,
    AsyncForYield,
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

# ---------------------------------------------------------------------------
# Import sorting (isort-compatible)
# ---------------------------------------------------------------------------

# Known stdlib / built-in modules used by generated code
_STDLIB_PREFIXES = frozenset(
    {
        "collections",
        "typing",
        "dataclasses",
        "abc",
        "os",
        "sys",
        "json",
        "pathlib",
        "functools",
        "itertools",
        "contextlib",
        "warnings",
        "copy",
        "io",
        "re",
        "enum",
        "datetime",
    }
)

# Known first-party prefixes
_FIRST_PARTY_PREFIXES = frozenset({"adk_fluent"})


def _classify_import(line: str) -> int:
    """Classify an import line into a group for isort-compatible ordering.

    Returns 0=future, 1=stdlib, 2=third-party, 3=first-party.
    """
    stripped = line.strip()
    if stripped.startswith("from __future__"):
        return 0

    # Extract the top-level module name
    if stripped.startswith("from "):
        module = stripped.split()[1].split(".")[0]
    elif stripped.startswith("import "):
        module = stripped.split()[1].split(".")[0].rstrip(",")
    else:
        return 2  # default to third-party

    if module in _FIRST_PARTY_PREFIXES:
        return 3
    if module in _STDLIB_PREFIXES:
        return 1
    return 2  # third-party (google.adk, etc.)


def _sort_and_group_imports(raw_lines: list[str]) -> list[str]:
    """Sort and group imports into future / stdlib / third-party / first-party.

    Merges ``from X import a`` and ``from X import b`` into ``from X import a, b``.
    Produces isort/ruff-compatible import blocks separated by blank lines.
    """
    # Phase 1: parse and merge "from M import ..." lines by module
    # key = (group, module_path), value = set of imported names
    from_imports: dict[tuple[int, str], set[str]] = {}
    # Plain "import X" lines (no merging needed)
    plain_imports: dict[int, list[str]] = {0: [], 1: [], 2: [], 3: []}

    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        group = _classify_import(stripped)

        if stripped.startswith("from ") and " import " in stripped:
            _, rest = stripped.split("from ", 1)
            module, names_str = rest.split(" import ", 1)
            module = module.strip()
            names = {n.strip() for n in names_str.split(",")}
            key = (group, module)
            from_imports.setdefault(key, set()).update(names)
        else:
            if stripped not in plain_imports[group]:
                plain_imports[group].append(stripped)

    # Phase 2: rebuild merged import lines
    # Sort names to match ruff/isort convention: ALL_CAPS first, then case-insensitive
    def _isort_name_key(name: str) -> tuple[bool, str]:
        return (not name.isupper(), name.lower())

    groups: dict[int, list[str]] = {0: [], 1: [], 2: [], 3: []}
    for (group, module), names in from_imports.items():
        joined = ", ".join(sorted(names, key=_isort_name_key))
        groups[group].append(f"from {module} import {joined}")
    for group, lines in plain_imports.items():
        groups[group].extend(lines)

    # Sort within each group
    for g in groups.values():
        g.sort()

    # Combine with blank line separators
    result: list[str] = []
    for key in (0, 1, 2, 3):
        if groups[key]:
            if result:
                result.append("")
            result.extend(groups[key])

    return result


# ---------------------------------------------------------------------------
# Ruff formatting — makes generator output its own final form
# ---------------------------------------------------------------------------

_RUFF_BIN: str | None = None


def _find_ruff() -> str | None:
    """Locate the ruff binary (cached after first call)."""
    global _RUFF_BIN  # noqa: PLW0603
    if _RUFF_BIN is None:
        _RUFF_BIN = shutil.which("ruff") or ""
    return _RUFF_BIN or None


def _ruff_format(source: str, *, filename: str = "<generated>.py") -> str:
    """Run ruff check --fix + ruff format on source via stdin.

    Returns the formatted source.  Falls back to the original source
    if ruff is unavailable or fails (CI will catch any issues).
    """
    ruff = _find_ruff()
    if not ruff:
        return source

    try:
        # Step 1: ruff check --fix (isort, etc.)
        result = subprocess.run(
            [ruff, "check", "--fix", "--stdin-filename", filename, "-"],
            input=source,
            capture_output=True,
            text=True,
            timeout=10,
        )
        source = result.stdout or source

        # Step 2: ruff format (quote style, blank lines, etc.)
        result = subprocess.run(
            [ruff, "format", "--stdin-filename", filename, "-"],
            input=source,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout or source
    except (subprocess.TimeoutExpired, OSError):
        return source


# ---------------------------------------------------------------------------
# Statement emission
# ---------------------------------------------------------------------------


def _emit_param(p: Param) -> str:
    """Format a single parameter."""
    result = p.name
    if p.type is not None:
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
    elif isinstance(stmt, ForkAndAssign):
        return f"{indent}self = self._maybe_fork_for_mutation()"
    elif isinstance(stmt, DeprecationStmt):
        lines = [
            f"{indent}import warnings",
            f"{indent}warnings.warn(",
            f'{indent}    ".{stmt.old_name}() is deprecated, use .{stmt.new_name}() instead",',
            f"{indent}    DeprecationWarning,",
            f"{indent}    stacklevel=2,",
            f"{indent})",
        ]
        return "\n".join(lines)
    elif isinstance(stmt, AsyncForYield):
        lines = [
            f"{indent}from {stmt.module} import {stmt.func}",
            f"{indent}async for {stmt.var} in {stmt.func}({stmt.args}):",
            f"{indent}    yield {stmt.var}",
        ]
        return "\n".join(lines)
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


# ---------------------------------------------------------------------------
# Python source emission
# ---------------------------------------------------------------------------


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

    # Deduplicate, sort, and group imports (isort-compatible)
    if mod.imports:
        grouped = _sort_and_group_imports(mod.imports)
        lines.extend(grouped)

    # Emit optional imports wrapped in try/except or contextlib.suppress
    if mod.optional_imports:
        needs_suppress = any(fallback == "pass" for _, fallback in mod.optional_imports)
        if needs_suppress:
            lines.append("import contextlib")
        for import_line, fallback in mod.optional_imports:
            if fallback == "pass":
                lines.append("with contextlib.suppress(ImportError, ModuleNotFoundError):")
                lines.append(f"    {import_line}")
            else:
                lines.append("try:")
                lines.append(f"    {import_line}")
                lines.append("except (ImportError, ModuleNotFoundError):")
                lines.append(f"    {fallback}")

    # Emit TYPE_CHECKING-guarded imports (for type annotations only)
    if mod.type_checking_imports:
        lines.append("")
        lines.append("if TYPE_CHECKING:")
        for imp in _sort_and_group_imports(mod.type_checking_imports):
            if imp:  # blank lines between groups
                lines.append(f"    {imp}")
            else:
                lines.append("")

    for cls in mod.classes:
        # PEP 8: two blank lines before top-level class definitions
        lines.append("")
        lines.append("")
        lines.append(_emit_class_python(cls))

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stub (.pyi) emission
# ---------------------------------------------------------------------------


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

    # Stubs only expose public attrs — internal attrs (prefixed _) are
    # implementation details that cause pyright override-mismatch noise.
    public_attrs = [a for a in c.attrs if not a.name.startswith("_")]
    if public_attrs:
        for attr in public_attrs:
            if attr.type_hint:
                lines.append(f"    {attr.name}: {attr.type_hint} = {attr.value}")
            else:
                lines.append(f"    {attr.name} = {attr.value}")

    for method in c.methods:
        lines.append(_emit_method_stub(method))

    if not c.doc and not public_attrs and not c.methods:
        lines.append("    ...")

    return "\n".join(lines)


def _emit_module_stub(mod: ModuleNode) -> str:
    """Emit a module stub."""
    lines: list[str] = []

    if mod.doc:
        lines.append(f'"""{mod.doc}"""')
        lines.append("")

    # Deduplicate, sort, and group imports (isort-compatible)
    if mod.imports:
        grouped = _sort_and_group_imports(mod.imports)
        lines.extend(grouped)
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
    """Emit Python source code from an IR node.

    Module-level output is automatically formatted with ruff so the
    generator's output is its own final form — no post-processing needed.
    """
    if isinstance(node, MethodNode):
        return _emit_method_python(node)
    elif isinstance(node, ClassNode):
        return _emit_class_python(node)
    elif isinstance(node, ModuleNode):
        return _ruff_format(_emit_module_python(node))
    else:
        raise TypeError(f"Cannot emit Python for {type(node)}")


def emit_stub(node: MethodNode | ClassNode | ModuleNode) -> str:
    """Emit .pyi type stub from an IR node.

    Module-level output is automatically formatted with ruff.
    """
    if isinstance(node, MethodNode):
        return _emit_method_stub(node)
    elif isinstance(node, ClassNode):
        return _emit_class_stub(node)
    elif isinstance(node, ModuleNode):
        return _ruff_format(_emit_module_stub(node), filename="<generated>.pyi")
    else:
        raise TypeError(f"Cannot emit stub for {type(node)}")
