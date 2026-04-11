"""TypeScript emitter — convert IR nodes to TypeScript source and .d.ts declarations.

This is the TypeScript counterpart of emitters.py (Python). It reads the same
IR nodes (ModuleNode, ClassNode, MethodNode, etc.) and produces .ts files that
wrap @google/adk classes using the adk-fluent-ts builder pattern.

Key design differences from the Python emitter:
- Immutable builders: ForkAndAssign → `const next = this._clone();`
- No operator overloading: >>, |, *, // → .then(), .parallel(), .times(), .fallback()
- Type mapping: str → string, int → number, list[T] → T[], etc.
- Import mapping: google.adk.* → @google/adk
"""

from __future__ import annotations

import re

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
# Python → TypeScript type mapping
# ---------------------------------------------------------------------------

_TYPE_MAP: dict[str, str] = {
    "str": "string",
    "int": "number",
    "float": "number",
    "bool": "boolean",
    "None": "void",
    "Any": "unknown",
    "Self": "this",
    "bytes": "Uint8Array",
    "Callable": "(...args: unknown[]) => unknown",
}

# Regex patterns for generic type translation
_GENERIC_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"list\[(.+)\]", re.IGNORECASE), r"Array<\1>"),
    (re.compile(r"dict\[(.+),\s*(.+)\]", re.IGNORECASE), r"Record<\1, \2>"),
    (re.compile(r"Optional\[(.+)\]"), r"\1 | undefined"),
    (re.compile(r"tuple\[(.+)\]"), r"[\1]"),
    (re.compile(r"set\[(.+)\]"), r"Set<\1>"),
    (re.compile(r"Callable\[\[(.+)\],\s*(.+)\]"), r"(\1) => \2"),
    (re.compile(r"Callable\[\.\.\.,\s*(.+)\]"), r"(...args: unknown[]) => \1"),
]


def _map_type(py_type: str | None) -> str:
    """Convert a Python type annotation to TypeScript."""
    if py_type is None:
        return "unknown"

    # Direct mapping
    if py_type in _TYPE_MAP:
        return _TYPE_MAP[py_type]

    # Union types: A | B
    if " | " in py_type:
        parts = [_map_type(p.strip()) for p in py_type.split(" | ")]
        return " | ".join(parts)

    # Generic patterns
    for pattern, replacement in _GENERIC_PATTERNS:
        if pattern.search(py_type):
            mapped = pattern.sub(replacement, py_type)
            # Recursively map inner types
            return mapped

    # Fallback: return as-is (it might be a custom class name)
    return py_type


# ---------------------------------------------------------------------------
# Python → TypeScript import mapping
# ---------------------------------------------------------------------------

# Map Python ADK module paths to @google/adk imports
_IMPORT_MAP: dict[str, tuple[str, str]] = {
    # Agents
    "google.adk.agents.base_agent": ("@google/adk", "BaseAgent"),
    "google.adk.agents.llm_agent": ("@google/adk", "LlmAgent"),
    "google.adk.agents.sequential_agent": ("@google/adk", "SequentialAgent"),
    "google.adk.agents.parallel_agent": ("@google/adk", "ParallelAgent"),
    "google.adk.agents.loop_agent": ("@google/adk", "LoopAgent"),
    # Tools
    "google.adk.tools.function_tool": ("@google/adk", "FunctionTool"),
    "google.adk.tools.agent_tool": ("@google/adk", "AgentTool"),
    "google.adk.tools.google_search_tool": ("@google/adk", "GoogleSearchTool"),
    # Runner
    "google.adk.runners": ("@google/adk", "InMemoryRunner"),
}

# Map first-party Python imports to adk-fluent-ts imports
_FLUENT_IMPORT_MAP: dict[str, tuple[str, str]] = {
    "adk_fluent._base": ("../core/builder-base.js", "BuilderBase"),
    "adk_fluent": ("../index.js", ""),
}


def _map_import(py_import: str) -> str | None:
    """Convert a Python import line to a TypeScript import statement.

    Returns None if the import has no TypeScript equivalent.
    """
    stripped = py_import.strip()

    if stripped.startswith("from __future__"):
        return None  # No TS equivalent

    if stripped.startswith("from ") and " import " in stripped:
        _, rest = stripped.split("from ", 1)
        module, names_str = rest.split(" import ", 1)
        module = module.strip()
        names = [n.strip() for n in names_str.split(",")]

        # Check ADK import map
        for py_mod, (ts_mod, _ts_name) in _IMPORT_MAP.items():
            if module.startswith(py_mod):
                ts_names = ", ".join(names)
                return f'import {{ {ts_names} }} from "{ts_mod}";'

        # Check first-party import map
        for py_mod, (ts_mod, _) in _FLUENT_IMPORT_MAP.items():
            if module.startswith(py_mod):
                ts_names = ", ".join(names)
                return f'import {{ {ts_names} }} from "{ts_mod}";'

        # Standard library → skip (no TS equivalent)
        if module.split(".")[0] in {
            "collections", "typing", "dataclasses", "abc", "warnings",
            "copy", "functools", "contextlib",
        }:
            return None

    return None  # Unknown import, skip


# ---------------------------------------------------------------------------
# Statement emission (TypeScript)
# ---------------------------------------------------------------------------


def _emit_param_ts(p: Param) -> str:
    """Format a single TypeScript parameter."""
    ts_type = _map_type(p.type)
    result = f"{p.name}: {ts_type}" if p.type else p.name
    if p.default is not None:
        result = f"{result} = {_map_default(p.default)}"
    return result


def _map_default(value: str) -> str:
    """Convert a Python default value to TypeScript."""
    if value == "None":
        return "undefined"
    if value == "True":
        return "true"
    if value == "False":
        return "false"
    return value


def _emit_stmt_ts(stmt: Stmt, indent: str = "    ") -> str:
    """Emit a single TypeScript statement."""
    if isinstance(stmt, ReturnStmt):
        expr = stmt.expr.replace("self", "this")
        return f"{indent}return {expr};"

    elif isinstance(stmt, AssignStmt):
        target = stmt.target.replace("self.", "this.")
        value = stmt.value.replace("self.", "this.")
        return f"{indent}{target} = {value};"

    elif isinstance(stmt, SubscriptAssign):
        target = stmt.target.replace("self.", "this.")
        value = stmt.value.replace("self.", "this.")
        return f'{indent}{target}.set("{stmt.key}", {value});'

    elif isinstance(stmt, AppendStmt):
        target = stmt.target.replace("self.", "this.")
        value = stmt.value.replace("self.", "this.")
        return f'{indent}if (!{target}.has("{stmt.key}")) {{ {target}.set("{stmt.key}", []); }}\n{indent}{target}.get("{stmt.key}")!.push({value});'

    elif isinstance(stmt, ForAppendStmt):
        target = stmt.target.replace("self.", "this.")
        iterable = stmt.iterable.replace("self.", "this.")
        return f'{indent}for (const {stmt.var} of {iterable}) {{\n{indent}  {target}.get("{stmt.key}")!.push({stmt.var});\n{indent}}}'

    elif isinstance(stmt, IfStmt):
        condition = stmt.condition.replace("self.", "this.").replace(" is not None", " !== undefined").replace(" is None", " === undefined")
        lines = [f"{indent}if ({condition}) {{"]
        for s in stmt.body:
            lines.append(_emit_stmt_ts(s, indent + "  "))
        lines.append(f"{indent}}}")
        return "\n".join(lines)

    elif isinstance(stmt, ImportStmt):
        # In TS, imports go at top of file, not inline
        call = stmt.call.replace("self.", "this.")
        return f"{indent}{call};"

    elif isinstance(stmt, RawStmt):
        # Best-effort: replace Python syntax with TS
        code = stmt.code.replace("self.", "this.").replace("None", "undefined")
        return f"{indent}{code}"

    elif isinstance(stmt, ForkAndAssign):
        return f"{indent}const next = this._clone();"

    elif isinstance(stmt, DeprecationStmt):
        return f'{indent}console.warn(".{stmt.old_name}() is deprecated, use .{stmt.new_name}() instead");'

    elif isinstance(stmt, AsyncForYield):
        return f"{indent}// TODO: async generator not yet supported in TS emitter"

    else:
        raise TypeError(f"Unknown statement type: {type(stmt)}")


# ---------------------------------------------------------------------------
# Method emission (TypeScript)
# ---------------------------------------------------------------------------


def _emit_method_ts(m: MethodNode, indent: str = "  ") -> str:
    """Emit a TypeScript method."""
    # Build parameter list (skip 'self')
    params = [p for p in m.params if p.name != "self"]
    params_str = ", ".join(_emit_param_ts(p) for p in params)

    ret_type = _map_type(m.returns) if m.returns else "this"
    prefix = "async " if m.is_async else ""

    lines = [f"{indent}{prefix}{m.name}({params_str}): {ret_type} {{"]

    if m.doc:
        lines.insert(0, f"{indent}/** {m.doc} */")

    if m.body:
        for stmt in m.body:
            lines.append(_emit_stmt_ts(stmt, indent + "  "))
    else:
        lines.append(f"{indent}  // TODO: implement")

    lines.append(f"{indent}}}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Class emission (TypeScript)
# ---------------------------------------------------------------------------


def _emit_class_ts(c: ClassNode) -> str:
    """Emit a TypeScript class."""
    extends = f" extends {c.bases[0]}" if c.bases else ""
    lines = []

    if c.doc:
        lines.append(f"/** {c.doc} */")

    lines.append(f"export class {c.name}{extends} {{")

    # Class attributes → TypeScript fields
    for attr in c.attrs:
        ts_type = _map_type(attr.type_hint) if attr.type_hint else "unknown"
        lines.append(f"  static {attr.name}: {ts_type} = {_map_default(attr.value)};")

    if c.attrs and c.methods:
        lines.append("")

    # Methods
    for i, method in enumerate(c.methods):
        lines.append(_emit_method_ts(method))
        if i < len(c.methods) - 1:
            lines.append("")

    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module emission (TypeScript)
# ---------------------------------------------------------------------------


def _emit_module_ts(mod: ModuleNode) -> str:
    """Emit a full TypeScript module."""
    lines: list[str] = []

    if mod.doc:
        lines.append(f"/**")
        lines.append(f" * {mod.doc}")
        lines.append(f" */")
        lines.append("")

    # Map Python imports to TypeScript
    ts_imports: list[str] = []
    for imp in mod.imports:
        mapped = _map_import(imp)
        if mapped:
            ts_imports.append(mapped)

    # Deduplicate
    seen: set[str] = set()
    for imp in ts_imports:
        if imp not in seen:
            seen.add(imp)
            lines.append(imp)
    if ts_imports:
        lines.append("")

    # Emit classes
    for cls in mod.classes:
        lines.append(_emit_class_ts(cls))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Declaration file (.d.ts) emission
# ---------------------------------------------------------------------------


def _emit_method_dts(m: MethodNode, indent: str = "  ") -> str:
    """Emit a .d.ts method declaration."""
    params = [p for p in m.params if p.name != "self"]
    params_str = ", ".join(_emit_param_ts(p) for p in params)
    ret_type = _map_type(m.returns) if m.returns else "this"
    prefix = "async " if m.is_async else ""
    return f"{indent}{prefix}{m.name}({params_str}): {ret_type};"


def _emit_class_dts(c: ClassNode) -> str:
    """Emit a .d.ts class declaration."""
    extends = f" extends {c.bases[0]}" if c.bases else ""
    lines = []

    if c.doc:
        lines.append(f"/** {c.doc} */")

    lines.append(f"export declare class {c.name}{extends} {{")

    for attr in c.attrs:
        ts_type = _map_type(attr.type_hint) if attr.type_hint else "unknown"
        lines.append(f"  static {attr.name}: {ts_type};")

    for method in c.methods:
        if method.doc:
            lines.append(f"  /** {method.doc} */")
        lines.append(_emit_method_dts(method))

    lines.append("}")
    return "\n".join(lines)


def _emit_module_dts(mod: ModuleNode) -> str:
    """Emit a .d.ts module declaration file."""
    lines: list[str] = []

    if mod.doc:
        lines.append(f"/** {mod.doc} */")
        lines.append("")

    # Imports
    ts_imports: list[str] = []
    for imp in mod.imports:
        mapped = _map_import(imp)
        if mapped:
            ts_imports.append(mapped)

    seen: set[str] = set()
    for imp in ts_imports:
        if imp not in seen:
            seen.add(imp)
            lines.append(imp)
    if ts_imports:
        lines.append("")

    for cls in mod.classes:
        lines.append(_emit_class_dts(cls))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def emit_typescript(node: MethodNode | ClassNode | ModuleNode) -> str:
    """Emit TypeScript source code from an IR node."""
    if isinstance(node, MethodNode):
        return _emit_method_ts(node)
    elif isinstance(node, ClassNode):
        return _emit_class_ts(node)
    elif isinstance(node, ModuleNode):
        return _emit_module_ts(node)
    else:
        raise TypeError(f"Cannot emit TypeScript for {type(node)}")


def emit_dts(node: MethodNode | ClassNode | ModuleNode) -> str:
    """Emit .d.ts declaration file from an IR node."""
    if isinstance(node, MethodNode):
        return _emit_method_dts(node)
    elif isinstance(node, ClassNode):
        return _emit_class_dts(node)
    elif isinstance(node, ModuleNode):
        return _emit_module_dts(node)
    else:
        raise TypeError(f"Cannot emit .d.ts for {type(node)}")
