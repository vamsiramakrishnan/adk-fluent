"""AST walker — visit Python AST nodes and produce TypeScript source.

This module walks a Python AST looking for adk-fluent patterns:
- Builder chain expressions (Agent("x").instruct("y").build())
- Operator expressions (a >> b, a | b, a * 3, a // b, a @ Schema)
- Namespace calls (S.pick(), C.none(), P.role())
- Simple lambda expressions
"""

from __future__ import annotations

import ast
from typing import Any

from .operator_map import OPERATOR_MAP, to_camel_case
from .type_map import CLASS_MAP, COMPARISON_MAP, NAMESPACE_MODULES


class TSEmitter(ast.NodeVisitor):
    """Walk Python AST and emit TypeScript source code."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._indent = 0
        self._imports: set[str] = set()

    @property
    def output(self) -> str:
        """Return the full TypeScript source."""
        # Build import header
        imports = sorted(self._imports)
        header = "\n".join(imports) + "\n\n" if imports else ""
        return header + "\n".join(self._lines)

    def _write(self, text: str) -> None:
        """Write a line with current indentation."""
        prefix = "  " * self._indent
        self._lines.append(f"{prefix}{text}")

    # ------------------------------------------------------------------
    # Expression visitors → produce TypeScript expression strings
    # ------------------------------------------------------------------

    def emit_expr(self, node: ast.expr) -> str:
        """Convert a Python expression AST node to a TypeScript string."""
        if isinstance(node, ast.Call):
            return self._emit_call(node)
        elif isinstance(node, ast.BinOp):
            return self._emit_binop(node)
        elif isinstance(node, ast.Attribute):
            return self._emit_attribute(node)
        elif isinstance(node, ast.Name):
            return self._emit_name(node)
        elif isinstance(node, ast.Constant):
            return self._emit_constant(node)
        elif isinstance(node, ast.Lambda):
            return self._emit_lambda(node)
        elif isinstance(node, ast.Subscript):
            return self._emit_subscript(node)
        elif isinstance(node, ast.Compare):
            return self._emit_compare(node)
        elif isinstance(node, ast.BoolOp):
            return self._emit_boolop(node)
        elif isinstance(node, ast.UnaryOp):
            return self._emit_unaryop(node)
        elif isinstance(node, ast.List):
            items = ", ".join(self.emit_expr(e) for e in node.elts)
            return f"[{items}]"
        elif isinstance(node, ast.Tuple):
            items = ", ".join(self.emit_expr(e) for e in node.elts)
            return f"[{items}]"
        elif isinstance(node, ast.Dict):
            pairs = []
            for k, v in zip(node.keys, node.values):
                if k is not None:
                    pairs.append(f"{self.emit_expr(k)}: {self.emit_expr(v)}")
                else:
                    pairs.append(f"...{self.emit_expr(v)}")
            return "{ " + ", ".join(pairs) + " }"
        elif isinstance(node, ast.JoinedStr):
            # f-string → template literal
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    parts.append(str(value.value))
                elif isinstance(value, ast.FormattedValue):
                    parts.append(f"${{{self.emit_expr(value.value)}}}")
                else:
                    parts.append(self.emit_expr(value))
            return f"`{''.join(parts)}`"
        elif isinstance(node, ast.IfExp):
            # Ternary: a if cond else b → cond ? a : b
            cond = self.emit_expr(node.test)
            body = self.emit_expr(node.body)
            orelse = self.emit_expr(node.orelse)
            return f"{cond} ? {body} : {orelse}"
        elif isinstance(node, ast.Starred):
            return f"...{self.emit_expr(node.value)}"
        else:
            return f"/* TODO: {ast.dump(node)} */"

    def _emit_call(self, node: ast.Call) -> str:
        """Emit a function/method call."""
        args = [self.emit_expr(a) for a in node.args]

        # Handle keyword arguments → object literal
        if node.keywords:
            kw_pairs = []
            for kw in node.keywords:
                if kw.arg:
                    kw_name = to_camel_case(kw.arg)
                    kw_pairs.append(f"{kw_name}: {self.emit_expr(kw.value)}")
                else:
                    kw_pairs.append(f"...{self.emit_expr(kw.value)}")
            if kw_pairs:
                args.append("{ " + ", ".join(kw_pairs) + " }")

        args_str = ", ".join(args)

        func = node.func

        # Constructor call: Agent("x") → new Agent("x")
        if isinstance(func, ast.Name) and func.id in CLASS_MAP:
            ts_class = CLASS_MAP[func.id]
            self._imports.add(f'import {{ {ts_class} }} from "adk-fluent-ts";')
            return f"new {ts_class}({args_str})"

        # Namespace call: S.pick("a") → S.pick("a")
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id in NAMESPACE_MODULES:
                ns = func.value.id
                method = to_camel_case(func.attr)
                self._imports.add(f'import {{ {ns} }} from "adk-fluent-ts";')
                return f"{ns}.{method}({args_str})"

        # Method call on chain: x.instruct("y") → x.instruct("y")
        if isinstance(func, ast.Attribute):
            obj = self.emit_expr(func.value)
            method = to_camel_case(func.attr)
            return f"{obj}.{method}({args_str})"

        # Plain function call: until(pred, max=5) → until(pred, { max: 5 })
        if isinstance(func, ast.Name):
            name = to_camel_case(func.id)
            return f"{name}({args_str})"

        return f"/* TODO: call {ast.dump(func)} */({args_str})"

    def _emit_binop(self, node: ast.BinOp) -> str:
        """Emit a binary operation, converting operators to method calls."""
        left = self.emit_expr(node.left)
        right = self.emit_expr(node.right)

        op_type = type(node.op)

        # Special case: * (multiply)
        if isinstance(node.op, ast.Mult):
            # a * 3 → a.times(3)
            if isinstance(node.right, ast.Constant) and isinstance(node.right.value, int):
                return f"{left}.times({right})"
            # a * until(pred) → a.timesUntil(pred)
            if isinstance(node.right, ast.Call) and isinstance(node.right.func, ast.Name) and node.right.func.id == "until":
                return f"{left}.timesUntil({right})"
            return f"{left}.times({right})"

        # Mapped operators: >> | // @
        if op_type in OPERATOR_MAP:
            method, _desc = OPERATOR_MAP[op_type]
            return f"{left}.{method}({right})"

        # Arithmetic operators (pass through)
        op_map = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Div: "/",
            ast.Mod: "%",
            ast.Pow: "**",
        }
        if op_type in op_map:
            return f"{left} {op_map[op_type]} {right}"

        return f"/* TODO: {ast.dump(node.op)} */({left}, {right})"

    def _emit_attribute(self, node: ast.Attribute) -> str:
        """Emit attribute access."""
        obj = self.emit_expr(node.value)
        return f"{obj}.{to_camel_case(node.attr)}"

    def _emit_name(self, node: ast.Name) -> str:
        """Emit a name reference."""
        if node.id in COMPARISON_MAP:
            return COMPARISON_MAP[node.id]
        return node.id

    def _emit_constant(self, node: ast.Constant) -> str:
        """Emit a constant value."""
        if isinstance(node.value, str):
            # Use double quotes
            escaped = node.value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            return f'"{escaped}"'
        if isinstance(node.value, bool):
            return "true" if node.value else "false"
        if node.value is None:
            return "undefined"
        return repr(node.value)

    def _emit_lambda(self, node: ast.Lambda) -> str:
        """Emit a lambda as an arrow function."""
        # Build parameter list
        args = node.args
        params = []
        for arg in args.args:
            params.append(arg.arg)
        params_str = ", ".join(params)

        body = self.emit_expr(node.body)
        if len(params) == 1:
            return f"({params_str}) => {body}"
        return f"({params_str}) => {body}"

    def _emit_subscript(self, node: ast.Subscript) -> str:
        """Emit subscript access: x["key"] → x["key"]."""
        obj = self.emit_expr(node.value)
        key = self.emit_expr(node.slice)
        return f"{obj}[{key}]"

    def _emit_compare(self, node: ast.Compare) -> str:
        """Emit comparison: a == b → a === b."""
        left = self.emit_expr(node.left)
        parts = [left]
        for op, comparator in zip(node.ops, node.comparators):
            right = self.emit_expr(comparator)
            if isinstance(op, ast.Eq):
                parts.append(f"=== {right}")
            elif isinstance(op, ast.NotEq):
                parts.append(f"!== {right}")
            elif isinstance(op, ast.Lt):
                parts.append(f"< {right}")
            elif isinstance(op, ast.LtE):
                parts.append(f"<= {right}")
            elif isinstance(op, ast.Gt):
                parts.append(f"> {right}")
            elif isinstance(op, ast.GtE):
                parts.append(f">= {right}")
            elif isinstance(op, ast.Is):
                parts.append(f"=== {right}")
            elif isinstance(op, ast.IsNot):
                parts.append(f"!== {right}")
            elif isinstance(op, ast.In):
                parts.append(f"/* in */ {right}")
            elif isinstance(op, ast.NotIn):
                parts.append(f"/* not in */ {right}")
            else:
                parts.append(f"/* {ast.dump(op)} */ {right}")
        return " ".join(parts)

    def _emit_boolop(self, node: ast.BoolOp) -> str:
        """Emit boolean operation: and → &&, or → ||."""
        op = "&&" if isinstance(node.op, ast.And) else "||"
        values = [self.emit_expr(v) for v in node.values]
        return f" {op} ".join(values)

    def _emit_unaryop(self, node: ast.UnaryOp) -> str:
        """Emit unary operation: not → !."""
        operand = self.emit_expr(node.operand)
        if isinstance(node.op, ast.Not):
            return f"!{operand}"
        if isinstance(node.op, ast.USub):
            return f"-{operand}"
        if isinstance(node.op, ast.UAdd):
            return f"+{operand}"
        return f"/* {ast.dump(node.op)} */{operand}"

    # ------------------------------------------------------------------
    # Statement visitors → produce TypeScript statement lines
    # ------------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> Any:
        """Convert: x = expr → const x = expr;"""
        for target in node.targets:
            lhs = self.emit_expr(target)
            rhs = self.emit_expr(node.value)
            self._write(f"const {lhs} = {rhs};")

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        """Convert: x: Type = expr → const x: Type = expr;"""
        if node.target and node.value:
            lhs = self.emit_expr(node.target)
            rhs = self.emit_expr(node.value)
            self._write(f"const {lhs} = {rhs};")

    def visit_Expr(self, node: ast.Expr) -> Any:
        """Handle expression statements."""
        expr_str = self.emit_expr(node.value)
        self._write(f"{expr_str};")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        """Convert function definitions."""
        params = []
        for arg in node.args.args:
            params.append(arg.arg)
        params_str = ", ".join(params)

        self._write(f"function {to_camel_case(node.name)}({params_str}) {{")
        self._indent += 1
        self._write("// TODO: manually translate function body")
        self._indent -= 1
        self._write("}")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        """Convert async function definitions."""
        params = []
        for arg in node.args.args:
            params.append(arg.arg)
        params_str = ", ".join(params)

        self._write(f"async function {to_camel_case(node.name)}({params_str}) {{")
        self._indent += 1
        self._write("// TODO: manually translate function body")
        self._indent -= 1
        self._write("}")

    def visit_Import(self, node: ast.Import) -> Any:
        """Skip Python imports (TS imports are auto-generated from usage)."""
        self._write(f"// import {', '.join(a.name for a in node.names)} — auto-resolved")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        """Skip Python imports (TS imports are auto-generated from usage)."""
        names = ", ".join(a.name for a in node.names)
        self._write(f'// from {node.module} import {names} — auto-resolved')

    def visit_If(self, node: ast.If) -> Any:
        """Convert if statements."""
        cond = self.emit_expr(node.test)
        self._write(f"if ({cond}) {{")
        self._indent += 1
        for stmt in node.body:
            self.visit(stmt)
        self._indent -= 1
        if node.orelse:
            self._write("} else {")
            self._indent += 1
            for stmt in node.orelse:
                self.visit(stmt)
            self._indent -= 1
        self._write("}")

    def visit_Return(self, node: ast.Return) -> Any:
        """Convert return statements."""
        if node.value:
            self._write(f"return {self.emit_expr(node.value)};")
        else:
            self._write("return;")

    def visit_Pass(self, _node: ast.Pass) -> Any:
        """Convert pass → empty comment."""
        self._write("// pass")

    def visit_Comment(self, node: Any) -> Any:
        """Preserve comments."""
        self._write(f"// {getattr(node, 'value', '')}")

    def generic_visit(self, node: ast.AST) -> Any:
        """Fallback: emit TODO for unhandled nodes."""
        if isinstance(node, ast.Module):
            for stmt in node.body:
                self.visit(stmt)
        elif isinstance(node, (ast.ClassDef,)):
            self._write(f"// TODO: manually translate class {node.name}")
        else:
            # Don't emit TODO for every sub-node
            pass
