#!/usr/bin/env python3
"""
docs_validator — lint the rendered docs tree for broken internal references.

Runs against ``docs/generated/`` (and optionally the hand-written ``docs/``
tree) and reports:

  * relative links to .md files that don't exist on disk
  * fragment/anchor links where the target heading isn't present
  * duplicate heading anchors inside a single file

This is a *validator only* — it does not modify any file and is not part of
the generator pipeline. It is wired into the justfile under its own
``validate-docs`` target so it can be run independently of ``just docs``.

Usage:
    python shared/scripts/docs_validator.py                    # validate docs/
    python shared/scripts/docs_validator.py --strict           # exit 1 on any finding
    python shared/scripts/docs_validator.py --root docs/generated
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

LINK_RE = re.compile(r"(?<!\!)\[[^\]]+\]\(([^)\s]+?)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    kind: str
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: [{self.kind}] {self.message}"


def _slugify(heading: str) -> str:
    """Approximate MyST/Sphinx heading anchor slugification.

    This is intentionally permissive — the validator's job is to flag
    obvious breakage, not to replicate every theme-specific edge case.
    """
    slug = heading.lower()
    slug = re.sub(r"[^a-z0-9\s\-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug


def _collect_headings(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            out.append(_slugify(m.group(2)))
    return out


def _find_md_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.md"))


def validate_tree(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    files = _find_md_files(root)
    known = {p.resolve() for p in files}

    for md in files:
        text = md.read_text()
        headings = _collect_headings(text)

        dupes = {h for h in headings if headings.count(h) > 1}
        for dup in sorted(dupes):
            findings.append(
                Finding(md, 0, "duplicate-anchor", f"heading slug '{dup}' appears more than once")
            )

        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in LINK_RE.finditer(line):
                target = match.group(1)

                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if target.startswith("#"):
                    anchor = target.lstrip("#")
                    if anchor and anchor not in headings:
                        findings.append(
                            Finding(md, lineno, "missing-anchor", f"in-page anchor '#{anchor}' not found")
                        )
                    continue

                # Strip fragment for path resolution
                if "#" in target:
                    path_part, anchor = target.split("#", 1)
                else:
                    path_part, anchor = target, ""

                if not path_part:
                    continue

                resolved = (md.parent / path_part).resolve()
                if resolved.suffix == "" and (resolved.with_suffix(".md")).exists():
                    resolved = resolved.with_suffix(".md")

                if resolved.suffix == ".md" and resolved not in known and not resolved.exists():
                    findings.append(
                        Finding(md, lineno, "missing-file", f"link target '{path_part}' not found")
                    )
                    continue

                if anchor and resolved.suffix == ".md" and resolved.exists():
                    target_headings = _collect_headings(resolved.read_text())
                    if anchor not in target_headings:
                        findings.append(
                            Finding(
                                md,
                                lineno,
                                "missing-anchor",
                                f"anchor '#{anchor}' not found in {resolved.name}",
                            )
                        )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--root", default="docs", help="Docs root to scan (default: docs)")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when any finding is reported")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"docs_validator: root {root} is not a directory", file=sys.stderr)
        return 2

    findings = validate_tree(root)
    for f in findings:
        print(f.format())

    print(f"\ndocs_validator: {len(findings)} finding(s) across {root}")
    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
