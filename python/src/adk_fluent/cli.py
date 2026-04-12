"""adk-fluent CLI — visualization and inspection utilities."""

from __future__ import annotations

import argparse
import importlib
import inspect
import sys
import webbrowser
from pathlib import Path

from adk_fluent._base import BuilderBase

_MERMAID_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>adk-fluent — {title}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
</head>
<body>
  <pre class="mermaid">
{mermaid_source}
  </pre>
  <script>mermaid.initialize({{ startOnLoad: true }});</script>
</body>
</html>
"""


def _find_builders(module) -> dict[str, BuilderBase]:
    """Auto-detect all BuilderBase instances in a module."""
    builders: dict[str, BuilderBase] = {}
    for name, obj in inspect.getmembers(module):
        if name.startswith("_"):
            continue
        if isinstance(obj, BuilderBase):
            builders[name] = obj
    return builders


def _cmd_visualize(args: argparse.Namespace) -> None:
    """Import module, find builders, render mermaid."""
    module = importlib.import_module(args.module)

    if args.var:
        obj = getattr(module, args.var, None)
        if obj is None:
            print(f"Error: '{args.var}' not found in {args.module}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(obj, BuilderBase):
            print(f"Error: '{args.var}' is not a BuilderBase instance", file=sys.stderr)
            sys.exit(1)
        builders = {args.var: obj}
    else:
        builders = _find_builders(module)
        if not builders:
            print(f"No BuilderBase instances found in {args.module}", file=sys.stderr)
            sys.exit(1)

    for var_name, builder in builders.items():
        mermaid_source = builder.to_mermaid()

        if args.format == "mermaid":
            print(mermaid_source)
        else:
            title = builder._config.get("name", var_name)
            html = _MERMAID_HTML_TEMPLATE.format(title=title, mermaid_source=mermaid_source)
            if args.output:
                out_path = Path(args.output)
                out_path.write_text(html)
                print(f"Written to {out_path}")
            else:
                import tempfile

                with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
                    f.write(html)
                    tmp_path = f.name
                print(f"Opening {tmp_path}")
                webbrowser.open(f"file://{tmp_path}")


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(prog="adk-fluent", description="adk-fluent CLI utilities")
    sub = parser.add_subparsers(dest="command")

    vis = sub.add_parser("visualize", help="Render a builder as a Mermaid diagram")
    vis.add_argument("module", help="Python module path (e.g. examples.my_agent)")
    vis.add_argument("--var", help="Variable name to visualize (auto-detects if omitted)")
    vis.add_argument("--output", "-o", help="Output file path")
    vis.add_argument("--format", choices=["html", "mermaid"], default="html", help="Output format (default: html)")

    args = parser.parse_args(argv)

    if args.command == "visualize":
        _cmd_visualize(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
