"""flux codegen CLI entry point.

Usage::

    python -m shared.scripts.flux <subcommand>

Subcommands::

    load    — parse all specs via the TS loader, dump as JSON to stdout
    check   — validate specs against token packs and basic-catalog whitelist
    emit    — write ``catalog/flux/catalog.json`` (load + check + emit)
    py      — write ``python/src/adk_fluent/_flux_gen.py`` (requires catalog)
    ts      — write ``ts/src/flux/index.ts`` (requires catalog)
    react   — write ``ts/src/flux/renderer/*.tsx`` scaffolds + wiring
    docs    — write ``docs/flux/components/*.md``
    all     — run every stage in order (load → check → emit → py → ts → react → docs)
    clean   — remove every generated artifact
"""

from __future__ import annotations

import sys
from pathlib import Path

from shared.scripts.flux.build import run


def _find_repo_root() -> Path:
    """Walk upward from this file until we find the monorepo root marker.

    The marker is the presence of a ``catalog/flux/`` sub-tree AND a
    top-level ``justfile``. This lets ``python -m shared.scripts.flux``
    work regardless of the caller's cwd.
    """
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "catalog" / "flux").is_dir() and (parent / "justfile").is_file():
            return parent
    raise RuntimeError("Could not locate the monorepo root (no catalog/flux + justfile ancestor).")


_VALID = {"load", "check", "emit", "py", "ts", "react", "docs", "all", "clean"}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: python -m shared.scripts.flux <subcommand>", file=sys.stderr)
        print(f"subcommands: {', '.join(sorted(_VALID))}", file=sys.stderr)
        return 2
    cmd = args[0]
    if cmd in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    if cmd not in _VALID:
        print(f"unknown subcommand: {cmd!r}", file=sys.stderr)
        print(f"valid: {', '.join(sorted(_VALID))}", file=sys.stderr)
        return 2
    root = _find_repo_root()
    return run(cmd, root=root)


if __name__ == "__main__":
    raise SystemExit(main())
