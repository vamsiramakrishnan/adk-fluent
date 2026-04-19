"""Release preflight — declarative readiness checks.

Run as ``python -m shared.scripts.release preflight`` (or ``just rel-preflight``)
before tagging. Every check is:

- non-destructive: reads files and git state only,
- self-describing: prints a ``[ok]`` / ``[warn]`` / ``[fail]`` line per check,
- composable: ``--strict`` turns warnings into failures for CI.

The checks themselves are trivially inspectable; add new ones by appending to
:data:`CHECKS`.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable

from . import changelog, version

Level = str  # "ok" | "warn" | "fail"


@dataclass(frozen=True)
class CheckResult:
    name: str
    level: Level
    message: str


def _run(cmd: list[str]) -> tuple[int, str]:
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, (res.stdout + res.stderr).strip()


def check_versions_agree() -> CheckResult:
    state = version.current_versions()
    if state.consistent:
        return CheckResult("versions", "ok", state.summary())
    return CheckResult(
        "versions",
        "fail",
        state.summary() + "  run: just rel-sync",
    )


def check_tag_available() -> CheckResult:
    """Tag check, environment-aware.

    Local / branch push:  tag must NOT exist yet (we're about to create it).
    Tag push (GITHUB_REF=refs/tags/vX.Y.Z): tag MUST exist and match VERSION.
    """
    v = version.read_version()
    tag = f"v{v}"
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/"):
        actual = ref[len("refs/tags/") :]
        if actual != tag:
            return CheckResult("tag", "fail", f"on tag {actual!r} but VERSION says {tag!r}")
        return CheckResult("tag", "ok", f"{tag} matches triggering tag")
    code, _ = _run(["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"])
    if code == 0:
        return CheckResult("tag", "fail", f"{tag} already exists locally")
    code, out = _run(["git", "ls-remote", "--tags", "origin", tag])
    if code == 0 and tag in out:
        return CheckResult("tag", "fail", f"{tag} already exists on origin")
    return CheckResult("tag", "ok", f"{tag} is free")


def check_clean_tree() -> CheckResult:
    code, out = _run(["git", "status", "--porcelain"])
    if code != 0:
        return CheckResult("tree", "fail", f"git status failed: {out}")
    if out:
        return CheckResult(
            "tree",
            "warn",
            f"{out.count(chr(10)) + 1} uncommitted change(s) — commit or stash before tagging",
        )
    return CheckResult("tree", "ok", "working tree clean")


def check_changelog() -> CheckResult:
    try:
        st = changelog.status()
    except changelog.ChangelogError as exc:
        return CheckResult("changelog", "fail", str(exc))
    v = version.read_version()
    if changelog.has_entry(v):
        return CheckResult("changelog", "ok", f"entry for {v} present")
    if st.has_unreleased and st.unreleased_has_content:
        return CheckResult(
            "changelog",
            "warn",
            f"no entry for {v} yet — will be promoted from [Unreleased] on prepare",
        )
    return CheckResult(
        "changelog",
        "fail",
        "no ## [Unreleased] section populated — write release notes before tagging",
    )


def check_python_build_ready() -> CheckResult:
    # Hatch build metadata lives in python/pyproject.toml; just confirm it exists.
    pyproject = version.REPO_ROOT / "python" / "pyproject.toml"
    if not pyproject.exists():
        return CheckResult("python/pyproject", "fail", f"{pyproject} missing")
    return CheckResult("python/pyproject", "ok", "present")


def check_ts_build_ready() -> CheckResult:
    pkg = version.TS_PACKAGE_FILE
    if not pkg.exists():
        return CheckResult("ts/package.json", "fail", f"{pkg} missing")
    text = pkg.read_text()
    if '"files"' not in text:
        return CheckResult(
            "ts/package.json",
            "warn",
            'no "files" allowlist — tarball will include everything in ts/',
        )
    return CheckResult("ts/package.json", "ok", 'present with "files" allowlist')


CHECKS: tuple[Callable[[], CheckResult], ...] = (
    check_versions_agree,
    check_changelog,
    check_python_build_ready,
    check_ts_build_ready,
    check_tag_available,
    check_clean_tree,
)


def run(strict: bool = False) -> int:
    results = [fn() for fn in CHECKS]
    width = max(len(r.name) for r in results)
    for r in results:
        marker = {"ok": "[ok]  ", "warn": "[warn]", "fail": "[fail]"}[r.level]
        print(f"{marker} {r.name.ljust(width)}  {r.message}")
    bad_levels = {"fail", "warn"} if strict else {"fail"}
    failing = [r for r in results if r.level in bad_levels]
    if failing:
        print(f"\n{len(failing)} check(s) blocking release.", file=sys.stderr)
        return 1
    v = version.read_version()
    print(f"\nReady to release v{v}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Release preflight checks")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures (use in CI gates)",
    )
    args = p.parse_args(argv)
    return run(strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
