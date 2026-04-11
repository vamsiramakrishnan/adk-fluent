"""Main transpiler entry point: Python adk-fluent → TypeScript adk-fluent-ts.

Usage:
    python -m scripts.transpiler input.py -o output.ts
    python -m scripts.transpiler input.py  # prints to stdout
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

from .ast_walker import TSEmitter


def transpile(source: str, *, filename: str = "<input>") -> str:
    """Transpile Python adk-fluent source code to TypeScript.

    Args:
        source: Python source code string.
        filename: Source filename (for error messages).

    Returns:
        TypeScript source code string.
    """
    tree = ast.parse(source, filename=filename)
    emitter = TSEmitter()
    emitter.visit(tree)
    return emitter.output


def transpile_file(input_path: str | Path, output_path: str | Path | None = None) -> str:
    """Transpile a Python file to TypeScript.

    Args:
        input_path: Path to the Python source file.
        output_path: If provided, write the TypeScript output here.

    Returns:
        TypeScript source code string.
    """
    input_path = Path(input_path)
    source = input_path.read_text(encoding="utf-8")
    ts_source = transpile(source, filename=str(input_path))

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(ts_source, encoding="utf-8")

    return ts_source


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Transpile Python adk-fluent agent definitions to TypeScript",
        prog="adk-fluent transpile",
    )
    parser.add_argument("input", help="Python source file to transpile")
    parser.add_argument("-o", "--output", help="TypeScript output file (default: stdout)")
    parser.add_argument("--check", action="store_true", help="Check mode: verify output matches existing file")

    args = parser.parse_args()

    ts_source = transpile_file(args.input)

    if args.check:
        if not args.output:
            print("ERROR: --check requires --output", file=sys.stderr)
            sys.exit(1)
        output_path = Path(args.output)
        if not output_path.exists():
            print(f"ERROR: {output_path} does not exist", file=sys.stderr)
            sys.exit(1)
        existing = output_path.read_text(encoding="utf-8")
        if existing != ts_source:
            print(f"ERROR: {output_path} is out of date. Run transpiler to update.", file=sys.stderr)
            sys.exit(1)
        print(f"OK: {output_path} is up to date.")
    elif args.output:
        transpile_file(args.input, args.output)
        print(f"Transpiled {args.input} → {args.output}", file=sys.stderr)
    else:
        print(ts_source)


if __name__ == "__main__":
    main()
