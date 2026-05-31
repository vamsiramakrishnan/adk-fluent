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


def _load_builder(spec: str) -> BuilderBase:
    """Load a builder from a ``module:attr`` (or ``module.attr``) spec.

    Accepts ``package.module:variable``. If no ``:attr`` is given, the module
    is imported and its sole BuilderBase instance is used (error if ambiguous).
    """
    if ":" in spec:
        module_path, _, attr = spec.partition(":")
    else:
        module_path, attr = spec, None

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        print(f"Error: could not import '{module_path}': {exc}", file=sys.stderr)
        sys.exit(1)

    if attr:
        obj = getattr(module, attr, None)
        if obj is None:
            print(f"Error: '{attr}' not found in {module_path}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(obj, BuilderBase):
            print(f"Error: '{attr}' is not a BuilderBase instance", file=sys.stderr)
            sys.exit(1)
        return obj

    builders = _find_builders(module)
    if not builders:
        print(f"No BuilderBase instances found in {module_path}", file=sys.stderr)
        sys.exit(1)
    if len(builders) > 1:
        names = ", ".join(sorted(builders))
        print(
            f"Error: multiple builders found in {module_path} ({names}); specify one with 'module:attr'",
            file=sys.stderr,
        )
        sys.exit(1)
    return next(iter(builders.values()))


def _cmd_doctor(args: argparse.Namespace) -> None:
    """Import a builder and print its diagnostic report."""
    builder = _load_builder(args.target)
    if hasattr(builder, "doctor"):
        # doctor() already prints the report.
        builder.doctor()
    elif hasattr(builder, "diagnose"):
        print(builder.diagnose())
    else:
        builder.validate()
        print("OK: builder validated with no errors.")


def _cmd_run(args: argparse.Namespace) -> None:
    """Import a builder and execute one prompt synchronously."""
    builder = _load_builder(args.target)

    prompt = args.prompt
    if prompt is None:
        if sys.stdin.isatty():
            print("Error: provide a prompt via --prompt or stdin", file=sys.stderr)
            sys.exit(1)
        prompt = sys.stdin.read().strip()
    if not prompt:
        print("Error: empty prompt", file=sys.stderr)
        sys.exit(1)

    response = builder.ask(prompt)  # type: ignore[attr-defined]
    print(response)


_AGENT_TEMPLATE = '''\
"""Minimal adk-fluent agent for {name}."""

from adk_fluent import Agent

# `root_agent` is the conventional name ADK looks for (adk web / adk run).
root_agent = (
    Agent("{name}", "gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .build()
)
'''

_README_TEMPLATE = """\
# {name}

A minimal [adk-fluent](https://pypi.org/project/adk-fluent/) agent project.

## Run

    pip install adk-fluent
    adk web {name}        # or: adk run {name}

## Develop

The agent lives in `{name}/agent.py` as `root_agent`. Edit it with the
fluent builder API, then re-run.

    adk-fluent doctor {name}.agent:root_agent
    adk-fluent run {name}.agent:root_agent --prompt "Hello"
"""

_INIT_TEMPLATE = '''\
"""Package marker for the {name} agent."""

from .agent import root_agent

__all__ = ["root_agent"]
'''


def _cmd_new(args: argparse.Namespace) -> None:
    """Scaffold a minimal agent project."""
    base = Path(args.dir) / args.name
    if base.exists():
        print(f"Error: '{base}' already exists", file=sys.stderr)
        sys.exit(1)

    base.mkdir(parents=True)
    created: list[Path] = []

    agent_py = base / "agent.py"
    agent_py.write_text(_AGENT_TEMPLATE.format(name=args.name))
    created.append(agent_py)

    init_py = base / "__init__.py"
    init_py.write_text(_INIT_TEMPLATE.format(name=args.name))
    created.append(init_py)

    readme = base / "README.md"
    readme.write_text(_README_TEMPLATE.format(name=args.name))
    created.append(readme)

    print(f"Created project '{args.name}':")
    for path in created:
        print(f"  {path}")


def _cmd_serve(args: argparse.Namespace) -> None:
    """Print guidance for serving the built agent via the ADK CLI."""
    # Validate the target loads — fail fast on a bad spec.
    _load_builder(args.target)

    module_path = args.target.split(":")[0]
    package_hint = module_path.split(".")[0]

    print("adk-fluent agents build to native ADK objects, so the ADK CLI serves them directly.")
    print()
    print("To serve a web UI:")
    print(f"  adk web {package_hint} --port {args.port}")
    print()
    print("To run interactively in the terminal:")
    print(f"  adk run {package_hint}")
    print()
    print("Note: the target module must expose a `root_agent` (built ADK object) for the ADK CLI to discover it.")


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

    doc = sub.add_parser("doctor", help="Print a builder's diagnostic report")
    doc.add_argument("target", help="Builder spec, e.g. examples.my_agent:root_agent")

    run = sub.add_parser("run", help="Execute one prompt against a builder (sync)")
    run.add_argument("target", help="Builder spec, e.g. examples.my_agent:root_agent")
    run.add_argument("--prompt", help="Prompt text (reads from stdin if omitted)")

    new = sub.add_parser("new", help="Scaffold a minimal agent project")
    new.add_argument("name", help="Project / agent name")
    new.add_argument("--dir", default=".", help="Parent directory for the project (default: .)")

    serve = sub.add_parser("serve", help="Print the ADK command to serve a builder")
    serve.add_argument("target", help="Builder spec, e.g. examples.my_agent:root_agent")
    serve.add_argument("--port", type=int, default=8000, help="Port for adk web (default: 8000)")

    args = parser.parse_args(argv)

    dispatch = {
        "visualize": _cmd_visualize,
        "doctor": _cmd_doctor,
        "run": _cmd_run,
        "new": _cmd_new,
        "serve": _cmd_serve,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()
