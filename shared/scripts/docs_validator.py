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

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

LINK_RE = re.compile(r"(?<!\!)\[[^\]]+\]\(([^)\s]+?)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# MyST explicit anchors: `(anchor-name)=` on its own line.
EXPLICIT_ANCHOR_RE = re.compile(r"^\((?P<name>[A-Za-z0-9_\-.:]+)\)=\s*$")


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
    """Return every anchor available in the file.

    Two anchor sources:

      * Markdown headings (``## Foo Bar``) → ``foo-bar`` (slugified).
      * MyST explicit anchors (``(builder-Agent)=`` on its own line) →
        ``builder-agent`` **and** the raw case-preserving form. Both are
        kept because upstream generators may emit mixed-case links for
        historical reasons; lowering case makes the validator tolerant
        of either convention.
    """
    out: list[str] = []
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            out.append(_slugify(m.group(2)))
            continue
        a = EXPLICIT_ANCHOR_RE.match(line)
        if a:
            name = a.group("name")
            out.append(name)
            out.append(name.lower())
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
                    if anchor and anchor not in headings and anchor.lower() not in headings:
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
                    if anchor not in target_headings and anchor.lower() not in target_headings:
                        findings.append(
                            Finding(
                                md,
                                lineno,
                                "missing-anchor",
                                f"anchor '#{anchor}' not found in {resolved.name}",
                            )
                        )

    return findings


def validate_against_doc_ir(doc_ir_path: Path, docs_root: Path) -> list[Finding]:
    """Check that every builder in DocIR has a rendered page with its anchor.

    Returns structured findings. Does not import generator internals — only
    reads the JSON snapshot produced by ``doc_ir.py``.
    """
    if not doc_ir_path.exists():
        return [Finding(doc_ir_path, 0, "doc-ir-missing", "DocIR snapshot not built; run 'just doc-ir'")]

    from doc_ir import DocIR  # local import to keep validator cheap without DocIR

    ir = DocIR.read_json(doc_ir_path)
    findings: list[Finding] = []
    generated_root = docs_root / "generated"

    for builder in ir.builders:
        target = generated_root / "api" / f"{builder.module}.md"
        if not target.exists():
            findings.append(
                Finding(target, 0, "doc-ir-missing-page", f"no rendered page for builder {builder.name}")
            )
            continue
        text = target.read_text()
        if f"(builder-{builder.name})=" not in text and f"(builder-{builder.name.lower()})=" not in text:
            findings.append(
                Finding(target, 0, "doc-ir-missing-anchor", f"builder {builder.name} has no explicit anchor in {target.name}")
            )

    expected_ns = {n.symbol for n in ir.namespaces}
    ns_index = generated_root / "namespaces" / "index.md"
    if ns_index.exists():
        ns_text = ns_index.read_text()
        for symbol in expected_ns:
            if f"`{symbol}`" not in ns_text and f"`{symbol}." not in ns_text and f"#{symbol}" not in ns_text:
                findings.append(
                    Finding(ns_index, 0, "doc-ir-namespace-missing", f"namespace {symbol} not referenced in namespaces/index.md")
                )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--root", default="docs", help="Docs root to scan (default: docs)")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when any finding is reported")
    parser.add_argument(
        "--doc-ir",
        default="docs/_generated/doc_ir.json",
        help="Path to DocIR JSON (set to empty string to skip DocIR cross-check)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"docs_validator: root {root} is not a directory", file=sys.stderr)
        return 2

    findings = validate_tree(root)
    if args.doc_ir:
        findings.extend(validate_against_doc_ir(Path(args.doc_ir).resolve(), root))

    for f in findings:
        print(f.format())

    print(f"\ndocs_validator: {len(findings)} finding(s) across {root}")
    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
