"""TypeScript emitter — convert IR nodes to compilable TypeScript source.

This is the TypeScript counterpart of ``emitters.py`` (Python). It reads the
same IR nodes (ModuleNode, ClassNode, MethodNode, ...) and emits ``.ts`` files
that wrap @google/adk types using the ``adk-fluent-ts`` ``BuilderBase``
pattern.

Design notes
------------
* **No @google/adk imports.** The generated code is dependency-free at the
  source level — every ``.build()`` returns a tagged plain object
  ``{ _type: "ClassName", ... }``. Real ADK wiring happens in a separate
  runtime layer (or via ``.native()`` hooks). This keeps the generated tree
  small, easy to verify, and resilient to upstream ``@google/adk`` churn.
* **BuilderBase helpers.** Every setter compiles to a one-liner —
  ``return this._setConfig("k", v)`` / ``_addCallback`` / ``_addToList`` —
  rather than mimicking Python's mutate-and-return pattern. This is both
  more idiomatic and produces a smaller diff against the hand-written
  builders.
* **Permissive types.** Most Python field types don't translate cleanly
  (Pydantic models, ``Callable[..., Awaitable[...]]``, etc.). The emitter
  defaults to ``unknown`` for any type it can't confidently map. This
  guarantees ``tsc --noEmit`` passes against the generated tree without
  having to chase type drift across upstream releases.
* **camelCase methods.** Python ``snake_case`` method names are converted
  to TypeScript ``camelCase`` (``max_iterations`` → ``maxIterations``).
  ``_config`` keys remain ``snake_case`` so the build output matches what
  ADK expects.
* **Reserved word handling.** TypeScript reserved words are renamed with
  a trailing underscore (``static`` → ``static_``).
* **Skipped patterns.** Methods that delegate to Python helpers
  (``runtime_helper``, async generators, ``deep_copy``) are skipped
  entirely — these are Python-only execution paths with no TS equivalent.
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
    SubscriptAssign,
)

# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------

_PRIMITIVE_TYPES: dict[str, str] = {
    "str": "string",
    "int": "number",
    "float": "number",
    "bool": "boolean",
    "None": "undefined",
    "Any": "unknown",
    "object": "unknown",
    "Self": "this",
    "bytes": "Uint8Array",
    "type": "unknown",
}

# Identifier-only regex (single class name like ``BaseAgent``).
_IDENT_RE = re.compile(r"[A-Z_][A-Za-z0-9_]*$")
_LOWER_IDENT_RE = re.compile(r"[a-z][A-Za-z0-9_]*$")


def _safe_type(py_type: str | None) -> str:
    """Map a Python type annotation to TypeScript.

    Falls back to ``unknown`` for anything that doesn't map cleanly. The
    goal is to guarantee ``tsc --noEmit`` passes — *not* to faithfully
    preserve Python's type system.
    """
    if py_type is None:
        return "unknown"

    py_type = py_type.strip()

    if not py_type:
        return "unknown"

    if py_type in _PRIMITIVE_TYPES:
        return _PRIMITIVE_TYPES[py_type]

    if py_type == "Self":
        return "this"

    # Bare identifier (class name) — keep as-is so the runtime can use it
    # for hand-written extension points. We accept both ``BaseAgent`` and
    # plain lowercase identifiers like ``int``.
    if _IDENT_RE.fullmatch(py_type) or _LOWER_IDENT_RE.fullmatch(py_type):
        return _PRIMITIVE_TYPES.get(py_type, "unknown")

    # ``X | Y`` union (no nested brackets — keep it simple).
    if " | " in py_type and "[" not in py_type:
        parts = [_safe_type(p.strip()) for p in py_type.split(" | ")]
        return " | ".join(parts)

    # ``Optional[X]`` simple
    m = re.fullmatch(r"Optional\[([\w\.]+)\]", py_type)
    if m:
        inner = _safe_type(m.group(1))
        return f"{inner} | undefined"

    # ``list[X]`` simple
    m = re.fullmatch(r"list\[([\w\.]+)\]", py_type)
    if m:
        return "unknown[]"

    # ``dict[K, V]`` simple
    m = re.fullmatch(r"dict\[([\w\.]+),\s*([\w\.]+)\]", py_type)
    if m:
        return "Record<string, unknown>"

    # ``tuple[...]``
    if py_type.startswith("tuple["):
        return "unknown[]"

    # ``Callable[...]``
    if py_type.startswith("Callable"):
        return "(...args: unknown[]) => unknown"

    # Anything else — give up gracefully.
    return "unknown"


# ---------------------------------------------------------------------------
# snake_case → camelCase + reserved word handling
# ---------------------------------------------------------------------------

_TS_RESERVED: set[str] = {
    "break", "case", "catch", "class", "const", "continue", "debugger",
    "default", "delete", "do", "else", "enum", "export", "extends", "false",
    "finally", "for", "function", "if", "import", "in", "instanceof", "new",
    "null", "of", "return", "super", "switch", "this", "throw", "true",
    "try", "typeof", "var", "void", "while", "with", "yield", "let",
    "static", "implements", "interface", "package", "private", "protected",
    "public", "as", "any", "boolean", "constructor", "declare", "from",
    "module", "number", "set", "string", "symbol", "type", "undefined",
}

# Names already used by BuilderBase (methods, accessors, fields). Generated
# methods that collide with these get renamed with a trailing underscore so
# they don't shadow the base API. ``build`` is excluded — every concrete
# builder MUST implement it.
_BUILDER_BASE_RESERVED: set[str] = {
    "name",  # accessor on BuilderBase
    "then", "parallel", "times", "timesUntil", "fallback", "outputAs",
    "inspect", "native", "debug", "writes", "reads", "toString", "clone",
}


def _camel(name: str) -> str:
    """Convert ``snake_case`` to ``camelCase`` (preserves leading underscores)."""
    if not name:
        return name
    if name.startswith("__") and name.endswith("__"):
        return name  # dunder — leave as-is
    leading = ""
    body = name
    while body.startswith("_"):
        leading += "_"
        body = body[1:]
    parts = body.split("_")
    if not parts:
        return leading + body
    head = parts[0]
    tail = "".join(p[:1].upper() + p[1:] for p in parts[1:])
    return leading + head + tail


def _safe_method_name(name: str) -> str:
    """Convert a Python method name to a TypeScript-safe camelCase name."""
    if name == "__init__":
        return "constructor"
    camel = _camel(name)
    if camel in _TS_RESERVED or camel in _BUILDER_BASE_RESERVED:
        return camel + "_"
    return camel


def _safe_param_name(name: str) -> str:
    """Make a parameter name TS-safe (handles ``*args``, ``**kwargs``)."""
    if name.startswith("**"):
        return name[2:] + "?"  # variadic kwargs collapse to optional record
    if name.startswith("*"):
        return "..." + name[1:]
    if name in _TS_RESERVED:
        return name + "_"
    return name


# ---------------------------------------------------------------------------
# Helper-function inlining
# ---------------------------------------------------------------------------
#
# Many Python ``runtime_helper`` methods are thin wrappers around a single
# ``_setConfig``/``_addToList``/``_addCallback`` operation with some validation.
# Rather than emit a stub, we map each helper to the equivalent TS action.
#
# Action grammar — each entry is a list of action tuples:
#   ("config",   "key_name", "VALUE")     -> this._setConfig("key", VALUE)
#   ("list",     "key_name", "VALUE")     -> this._addToList("key", VALUE)
#   ("callback", "key_name", "VALUE")     -> this._addCallback("key", VALUE)
#
# VALUE may be:
#   - a literal string ("true", '"show"', "5")
#   - "PARAM"  -> resolves to the first non-self parameter name (camelCased)
#   - "PARAM:n" -> resolves to the n-th non-self parameter (0-indexed)
#
# Helpers mapped to "SKIP" produce no method (the entire setter is dropped).

_INLINE_HELPERS: dict[str, object] = {
    # --- Config-key setters (single param) ---
    "_instruct_with_guard": [("config", "instruction", "PARAM")],
    "_context_with_guard": [("config", "_context_spec", "PARAM")],
    "_add_ui_spec": [("config", "_ui_spec", "PARAM")],
    "_add_memory": [("config", "_memory", "PARAM")],
    "_add_memory_auto_save": [("config", "_memory_auto_save", "true")],
    # --- List appenders ---
    "_add_tool": [("list", "tools", "PARAM")],
    "_add_tools": [("list", "tools", "PARAM")],
    "_add_artifacts": [("list", "artifacts", "PARAM")],
    "_add_skill": [("list", "skills", "PARAM")],
    "add_agent_tool": [("list", "tools", "PARAM")],
    # --- Callback dispatchers ---
    "_guard_dispatch": [
        ("callback", "before_model_callback", "PARAM"),
        ("callback", "after_model_callback", "PARAM"),
    ],
    # --- Static visibility/transfer flags ---
    "_isolate_agent": [
        ("config", "disallow_transfer_to_parent", "true"),
        ("config", "disallow_transfer_to_peers", "true"),
    ],
    "_stay_agent": [("config", "disallow_transfer_to_parent", "true")],
    "_no_peers_agent": [("config", "disallow_transfer_to_peers", "true")],
    "_show_agent": [("config", "_visibility", '"show"')],
    "_hide_agent": [("config", "_visibility", '"hide"')],
    "_transparent_agent": [("config", "_visibility", '"transparent"')],
    "_filtered_agent": [("config", "_visibility", '"filtered"')],
    "_annotated_agent": [("config", "_visibility", '"annotated"')],
    "_show_pipeline": [("config", "_visibility", '"show"')],
    "_hide_pipeline": [("config", "_visibility", '"hide"')],
    "_show_fanout": [("config", "_visibility", '"show"')],
    "_hide_fanout": [("config", "_visibility", '"hide"')],
    "_show_loop": [("config", "_visibility", '"show"')],
    "_hide_loop": [("config", "_visibility", '"hide"')],
    # --- Runtime/IR helpers — drop entirely (Python-only execution paths) ---
    "run_one_shot": "SKIP",
    "run_one_shot_async": "SKIP",
    "run_stream": "SKIP",
    "run_events": "SKIP",
    "run_inline_test": "SKIP",
    "run_map": "SKIP",
    "run_map_async": "SKIP",
    "create_session": "SKIP",
    "_eval_inline": "SKIP",
    "_eval_suite": "SKIP",
    "_agent_to_ir": "SKIP",
    "_pipeline_to_ir": "SKIP",
    "_loop_to_ir": "SKIP",
    "_fanout_to_ir": "SKIP",
    "_publish_agent": "SKIP",
}

# Alias kept for back-compat with any external callers.
_INLINE_CTX_HELPERS = _INLINE_HELPERS


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


_IDENT_BOUNDARY = re.compile(r"[A-Za-z0-9_$]")


def _is_param_used(name: str, body_text: str) -> bool:
    """Heuristic check: is ``name`` referenced as an identifier in ``body_text``?"""
    if not name or not body_text:
        return False
    # Strip leading ``...`` from variadic
    bare = name.lstrip(".")
    if not bare:
        return False
    idx = 0
    while True:
        idx = body_text.find(bare, idx)
        if idx < 0:
            return False
        before = body_text[idx - 1] if idx > 0 else ""
        after_idx = idx + len(bare)
        after = body_text[after_idx] if after_idx < len(body_text) else ""
        if not _IDENT_BOUNDARY.match(before) and not _IDENT_BOUNDARY.match(after):
            return True
        idx = after_idx


def _emit_param(p: Param, body_text: str = "") -> str:
    """Format a single TypeScript parameter.

    If ``body_text`` is provided and the parameter is not referenced in it,
    the parameter name is prefixed with ``_`` so the TypeScript compiler's
    ``noUnusedParameters`` flag does not flag it as an error.
    """
    name = _safe_param_name(p.name)

    # Determine the bare name used for usage detection.
    if name.startswith("..."):
        bare = name[3:]
    elif name.endswith("?"):
        bare = name[:-1]
    else:
        bare = name

    used = _is_param_used(bare, body_text) if body_text else True
    if not used and not bare.startswith("_"):
        bare_marked = "_" + bare
        if name.startswith("..."):
            name = "..." + bare_marked
        elif name.endswith("?"):
            name = bare_marked + "?"
        else:
            name = bare_marked

    if name.startswith("..."):
        # Variadic
        return f"{name}: unknown[]"

    if name.endswith("?"):
        # Variadic kwargs — make it optional
        return f"{name}: Record<string, unknown>"

    ts_type = _safe_type(p.type)

    if p.default is not None:
        default = _map_default(p.default)
        # Optional parameter — TypeScript requires `?` if there's no default
        # in a function signature *or* `= default`. We use the default form.
        return f"{name}: {ts_type} = {default}"

    return f"{name}: {ts_type}"


def _map_default(value: str) -> str:
    """Convert a Python default value to TypeScript."""
    if value == "None":
        return "undefined"
    if value == "True":
        return "true"
    if value == "False":
        return "false"
    # String literals — already quoted in Python source. Numbers as-is.
    return value


# ---------------------------------------------------------------------------
# Method body pattern detection
# ---------------------------------------------------------------------------


def _emit_constructor(method: MethodNode, indent: str) -> list[str]:
    """Emit a constructor body for ``__init__`` methods."""
    params = [p for p in method.params if p.name != "self"]
    if not params:
        return [
            f'{indent}super("");',
        ]

    name_param = params[0]
    name_param_name = _safe_param_name(name_param.name)
    lines = [f"{indent}super({name_param_name});"]
    for p in params[1:]:
        param_name = _safe_param_name(p.name)
        if p.default is not None:
            lines.append(
                f"{indent}if ({param_name} !== undefined) {{",
            )
            lines.append(
                f'{indent}  this._config.set("{p.name}", {param_name});',
            )
            lines.append(f"{indent}}}")
        else:
            lines.append(
                f'{indent}this._config.set("{p.name}", {param_name});',
            )
    return lines


def _is_helper_import(stmt) -> bool:
    """True if the statement is an ``ImportStmt`` referencing ``adk_fluent._helpers``."""
    return isinstance(stmt, ImportStmt) and "adk_fluent._helpers" in (stmt.module or "")


def _emit_helper_inline(
    stmt: ImportStmt,
    indent: str,
    method_params: list[Param] | None = None,
) -> list[str] | None:
    """If ``stmt`` references a known inline-helper, emit it. Else None.

    Returns ``None`` for an unknown helper (caller skips the method).
    Returns ``[]`` (empty list as a sentinel? no — we use a marker string)
    is not used; instead, helpers mapped to ``"SKIP"`` return ``None``
    so the caller drops the method entirely.
    """
    helper = stmt.name
    if helper not in _INLINE_HELPERS:
        return None
    spec = _INLINE_HELPERS[helper]
    if spec == "SKIP":
        return None
    if not spec:
        return [f"{indent}return this;"]

    # Resolve PARAM placeholders against the method's non-self params.
    non_self = [p for p in (method_params or []) if p.name != "self"]

    def _resolve_param_index(value: str) -> int | None:
        if value == "PARAM":
            return 0
        if value.startswith("PARAM:"):
            return int(value.split(":", 1)[1])
        return None

    def _resolve(value: str) -> str:
        idx = _resolve_param_index(value)
        if idx is None:
            return value
        if idx >= len(non_self):
            return "undefined"
        # Strip leading ``*`` so the bare name is returned (the variadic
        # spread is handled separately by the caller).
        return _safe_param_name(non_self[idx].name.lstrip("*"))

    def _is_variadic(value: str) -> bool:
        idx = _resolve_param_index(value)
        if idx is None or idx >= len(non_self):
            return False
        return non_self[idx].name.startswith("*") and not non_self[idx].name.startswith("**")

    # Detect a single-action spec whose value is variadic — emit a for-loop.
    if len(spec) == 1:  # type: ignore[arg-type]
        kind, key, raw_value = spec[0]  # type: ignore[index]
        if _is_variadic(raw_value):
            var_name = _resolve(raw_value)
            item = "item"
            op_map = {
                "config": f'next._setConfig("{key}", {item})',
                "list": f'next._addToList("{key}", {item})',
                "callback": f'next._addCallback("{key}", {item})',
            }
            if kind not in op_map:
                return None
            return [
                f"{indent}let next: this = this;",
                f"{indent}for (const {item} of {var_name}) {{",
                f"{indent}  next = {op_map[kind]};",
                f"{indent}}}",
                f"{indent}return next;",
            ]

    # Build a chain: ``return this.<op1>.<op2>.<op3>;``
    actions: list[str] = []
    for action in spec:  # type: ignore[attr-defined]
        kind, key, raw_value = action
        resolved = _resolve(raw_value)
        if kind == "config":
            actions.append(f'this._setConfig("{key}", {resolved})')
        elif kind == "list":
            actions.append(f'this._addToList("{key}", {resolved})')
        elif kind == "callback":
            actions.append(f'this._addCallback("{key}", {resolved})')
        else:
            return None  # unknown action — skip

    if not actions:
        return [f"{indent}return this;"]

    if len(actions) == 1:
        return [f"{indent}return {actions[0]};"]

    # Multiple actions chain via assignment to a local ``next``.
    lines = [f"{indent}let next: this = {actions[0]};"]
    for op in actions[1:]:
        rewritten = op.replace("this.", "next.")
        lines.append(f"{indent}next = {rewritten};")
    lines.append(f"{indent}return next;")
    return lines


def _detect_pattern(method: MethodNode, indent: str) -> list[str] | None:
    """Detect a recognized method-body pattern and emit the TS equivalent.

    Returns ``None`` if no pattern matches (caller should skip the method).
    """
    body = method.body
    if not body:
        return [f"{indent}return this;"]

    # __init__ → constructor
    if method.name == "__init__":
        return _emit_constructor(method, indent)

    # Helper-only methods (runtime_helper / runtime_helper_async / runtime_helper_async_gen)
    # are first-statement ImportStmt referencing ``adk_fluent._helpers``.
    if _is_helper_import(body[0]):
        inline = _emit_helper_inline(body[0], indent, method.params)  # type: ignore[arg-type]
        return inline  # may be None — caller will skip if so

    # Async-for-yield (runtime_helper_async_gen) — Python-only.
    if isinstance(body[0], AsyncForYield):
        return None

    # build() — emit a config-only build that uses _buildConfig.
    if method.name == "build":
        # Find the deferred-import RawStmt to get the type name; fall back
        # to "unknown" via the method's return annotation.
        type_name = method.returns or "unknown"
        # If the return type is unknown (rare), strip generic suffix.
        type_name = type_name.split("[")[0]
        # Strip the ``_ADK_`` alias prefix the Python emitter adds when an
        # ADK class name collides with a builder name.
        if type_name.startswith("_ADK_"):
            type_name = type_name[len("_ADK_"):]
        return [f'{indent}return this._buildConfig("{type_name}");']

    # Pattern: ForkAndAssign + SubscriptAssign(self._config) + Return
    if (
        len(body) == 3
        and isinstance(body[0], ForkAndAssign)
        and isinstance(body[1], SubscriptAssign)
        and body[1].target == "self._config"
        and isinstance(body[2], ReturnStmt)
        and body[2].expr == "self"
    ):
        key = body[1].key
        value = _safe_param_name(body[1].value)
        return [f'{indent}return this._setConfig("{key}", {value});']

    # Pattern: ForkAndAssign + AppendStmt(self._callbacks) + Return
    if (
        len(body) == 3
        and isinstance(body[0], ForkAndAssign)
        and isinstance(body[1], AppendStmt)
        and body[1].target == "self._callbacks"
        and isinstance(body[2], ReturnStmt)
    ):
        key = body[1].key
        value = _safe_param_name(body[1].value)
        return [f'{indent}return this._addCallback("{key}", {value});']

    # Pattern: ForkAndAssign + AppendStmt(self._lists) + Return
    if (
        len(body) == 3
        and isinstance(body[0], ForkAndAssign)
        and isinstance(body[1], AppendStmt)
        and body[1].target == "self._lists"
        and isinstance(body[2], ReturnStmt)
    ):
        key = body[1].key
        value = _safe_param_name(body[1].value)
        return [f'{indent}return this._addToList("{key}", {value});']

    # Pattern: ForkAndAssign + ForAppendStmt(self._callbacks) + Return  (variadic *fns)
    if (
        len(body) == 3
        and isinstance(body[0], ForkAndAssign)
        and isinstance(body[1], ForAppendStmt)
        and body[1].target == "self._callbacks"
        and isinstance(body[2], ReturnStmt)
    ):
        key = body[1].key
        var = body[1].var
        iterable = body[1].iterable
        return [
            f"{indent}let next: this = this;",
            f"{indent}for (const {var} of {iterable}) {{",
            f'{indent}  next = next._addCallback("{key}", {var});',
            f"{indent}}}",
            f"{indent}return next;",
        ]

    # Pattern: ForkAndAssign + IfStmt(AppendStmt) + Return — conditional callback
    if (
        len(body) == 3
        and isinstance(body[0], ForkAndAssign)
        and isinstance(body[1], IfStmt)
        and isinstance(body[2], ReturnStmt)
        and len(body[1].body) == 1
        and isinstance(body[1].body[0], AppendStmt)
        and body[1].body[0].target == "self._callbacks"
    ):
        cond = body[1].condition
        ap = body[1].body[0]
        key = ap.key
        value = _safe_param_name(ap.value)
        return [
            f"{indent}if ({cond}) {{",
            f'{indent}  return this._addCallback("{key}", {value});',
            f"{indent}}}",
            f"{indent}return this;",
        ]

    # Pattern: ForkAndAssign + DeprecationStmt + SubscriptAssign + Return
    if (
        len(body) == 4
        and isinstance(body[0], ForkAndAssign)
        and isinstance(body[1], DeprecationStmt)
        and isinstance(body[2], SubscriptAssign)
        and body[2].target == "self._config"
        and isinstance(body[3], ReturnStmt)
    ):
        warn = (
            f'console.warn(".{body[1].old_name}() is deprecated, '
            f'use .{body[1].new_name}() instead");'
        )
        key = body[2].key
        value = _safe_param_name(body[2].value)
        return [
            f"{indent}{warn}",
            f'{indent}return this._setConfig("{key}", {value});',
        ]

    # Pattern: DeprecationStmt + Return self.X(...) (deprecation_alias behavior)
    if (
        len(body) == 2
        and isinstance(body[0], DeprecationStmt)
        and isinstance(body[1], ReturnStmt)
    ):
        warn = (
            f'console.warn(".{body[0].old_name}() is deprecated, '
            f'use .{body[0].new_name}() instead");'
        )
        expr = body[1].expr.replace("self.", "this.")
        # Strip Python-style positional .X(value) into camelCase
        expr = _rewrite_method_call(expr)
        return [f"{indent}{warn}", f"{indent}return {expr};"]

    # Pattern: single ReturnStmt with self.X(...) — delegates_to
    if len(body) == 1 and isinstance(body[0], ReturnStmt) and "self." in body[0].expr:
        expr = body[0].expr.replace("self.", "this.")
        expr = _rewrite_method_call(expr)
        return [f"{indent}return {expr};"]

    # Anything else — skip the whole method (signal to caller via None).
    return None


_METHOD_CALL_RE = re.compile(r"this\.([A-Za-z_][A-Za-z0-9_]*)\(")


def _rewrite_method_call(expr: str) -> str:
    """Rewrite ``this.snake_case(...)`` calls to ``this.camelCase(...)``."""
    return _METHOD_CALL_RE.sub(
        lambda m: f"this.{_safe_method_name(m.group(1))}(", expr
    )


# ---------------------------------------------------------------------------
# Method emission
# ---------------------------------------------------------------------------


def _emit_method_ts(method: MethodNode, indent: str = "  ") -> str | None:
    """Emit a TypeScript method. Returns None if the method should be skipped."""
    body_lines = _detect_pattern(method, indent + "  ")
    if body_lines is None:
        return None

    name = _safe_method_name(method.name)
    is_constructor = name == "constructor"

    params = [p for p in method.params if p.name != "self"]

    # Detect which params are referenced in the body so unused ones can be
    # prefixed with ``_`` (TS convention to suppress noUnusedParameters).
    body_text = "\n".join(body_lines)
    params_str = ", ".join(_emit_param(p, body_text) for p in params)

    if is_constructor:
        signature = f"{indent}constructor({params_str}) {{"
    else:
        ret_type = _safe_type(method.returns) if method.returns else "this"
        if name == "build":
            ret_type = "Record<string, unknown>"
        prefix = "async " if method.is_async else ""
        signature = f"{indent}{prefix}{name}({params_str}): {ret_type} {{"

    lines = []
    if method.doc and not is_constructor:
        # Docstrings as JSDoc comments
        doc_lines = method.doc.strip().split("\n")
        lines.append(f"{indent}/**")
        for dl in doc_lines:
            # Escape any */ inside the docstring
            safe = dl.replace("*/", "* /")
            lines.append(f"{indent} * {safe}")
        lines.append(f"{indent} */")

    lines.append(signature)
    lines.extend(body_lines)
    lines.append(f"{indent}}}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Class emission
# ---------------------------------------------------------------------------


_BUILDER_BASE_IMPORT = 'import { BuilderBase } from "../core/builder-base.js";'


def _emit_class_ts(c: ClassNode) -> str:
    """Emit a TypeScript class."""
    extends = " extends BuilderBase"
    lines: list[str] = []

    if c.doc:
        doc_lines = c.doc.strip().split("\n")
        lines.append("/**")
        for dl in doc_lines:
            lines.append(f" * {dl}")
        lines.append(" */")

    lines.append(f"export class {c.name}{extends} {{")

    method_blocks: list[str] = []
    for method in c.methods:
        block = _emit_method_ts(method)
        if block:
            method_blocks.append(block)

    if method_blocks:
        lines.append("\n\n".join(method_blocks))

    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module emission
# ---------------------------------------------------------------------------


def _emit_module_ts(mod: ModuleNode) -> str:
    """Emit a full TypeScript module."""
    lines: list[str] = []

    lines.append("// Auto-generated by the adk-fluent codegen pipeline.")
    lines.append("// Do not edit by hand — re-run `just ts-generate`.")
    lines.append("")

    lines.append(_BUILDER_BASE_IMPORT)
    lines.append("")

    for cls in mod.classes:
        lines.append(_emit_class_ts(cls))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# .d.ts emission (declaration files)
# ---------------------------------------------------------------------------
#
# tsc emits .d.ts from the .ts source automatically (declaration: true in
# tsconfig). We keep this entry point because the public API still references
# it, but it just delegates to the source emitter — the .ts file *is* its own
# declaration source.


def emit_typescript(node: MethodNode | ClassNode | ModuleNode) -> str:
    """Emit TypeScript source code from an IR node."""
    if isinstance(node, MethodNode):
        result = _emit_method_ts(node)
        return result or "// (skipped)"
    if isinstance(node, ClassNode):
        return _emit_class_ts(node)
    if isinstance(node, ModuleNode):
        return _emit_module_ts(node)
    raise TypeError(f"Cannot emit TypeScript for {type(node)}")


def emit_dts(node: MethodNode | ClassNode | ModuleNode) -> str:
    """Emit a ``.d.ts`` declaration. The .ts source itself acts as a declaration."""
    return emit_typescript(node)
