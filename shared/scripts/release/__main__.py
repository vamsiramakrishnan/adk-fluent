"""CLI entrypoint for release operations.

Usage::

    python -m shared.scripts.release version
    python -m shared.scripts.release bump patch|minor|major
    python -m shared.scripts.release sync [X.Y.Z]
    python -m shared.scripts.release preflight [--strict]
    python -m shared.scripts.release changelog-promote [--date YYYY-MM-DD]
    python -m shared.scripts.release status

The ``justfile.release`` module wraps every subcommand as a ``just rel-*`` recipe.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from . import changelog, preflight, version


def _cmd_version(_: argparse.Namespace) -> int:
    print(version.read_version())
    return 0


def _cmd_status(_: argparse.Namespace) -> int:
    state = version.current_versions()
    print(state.summary())
    try:
        cl = changelog.status()
        print(cl.summary())
    except changelog.ChangelogError as exc:
        print(f"changelog: {exc}")
    return 0 if state.consistent else 1


def _cmd_bump(args: argparse.Namespace) -> int:
    old, new = version.bump_version(args.level)
    print(f"bumped: {old} → {new}")
    print(f"  wrote: {version.VERSION_FILE.relative_to(version.REPO_ROOT)}")
    print(f"  wrote: {version.PYTHON_VERSION_FILE.relative_to(version.REPO_ROOT)}")
    print(f"  wrote: {version.TS_PACKAGE_FILE.relative_to(version.REPO_ROOT)}")
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    state = version.sync_versions(args.version)
    print(state.summary())
    return 0 if state.consistent else 1


def _cmd_preflight(args: argparse.Namespace) -> int:
    return preflight.run(strict=args.strict)


def _cmd_changelog_promote(args: argparse.Namespace) -> int:
    v = version.read_version()
    when = date.fromisoformat(args.date) if args.date else date.today()
    changelog.promote_unreleased(v, when)
    print(f"promoted [Unreleased] → [{v}] - {when.isoformat()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="release", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version", help="Print canonical version").set_defaults(func=_cmd_version)
    sub.add_parser("status", help="Show VERSION vs consumers + changelog state").set_defaults(
        func=_cmd_status
    )

    b = sub.add_parser("bump", help="Bump version in VERSION and sync consumers")
    b.add_argument("level", choices=("patch", "minor", "major"))
    b.set_defaults(func=_cmd_bump)

    s = sub.add_parser("sync", help="Propagate VERSION into Python + TS")
    s.add_argument("version", nargs="?", help="Optional explicit version to set first")
    s.set_defaults(func=_cmd_sync)

    pf = sub.add_parser("preflight", help="Pre-release readiness checks")
    pf.add_argument("--strict", action="store_true")
    pf.set_defaults(func=_cmd_preflight)

    cp = sub.add_parser(
        "changelog-promote",
        help="Rename [Unreleased] → [VERSION] - DATE in CHANGELOG.md",
    )
    cp.add_argument("--date", help="Override date (YYYY-MM-DD); default = today")
    cp.set_defaults(func=_cmd_changelog_promote)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
