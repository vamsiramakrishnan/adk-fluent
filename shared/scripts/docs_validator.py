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
    """Return one anchor string per heading or explicit anchor declaration.

    Anchor sources:

      * Markdown headings (``## Foo Bar``) → ``foo-bar`` (slugified).
      * MyST explicit anchors (``(builder-Agent)=`` on its own line) →
        ``builder-Agent`` (case preserved).

    If a heading is immediately preceded by an explicit anchor (ignoring
    blank lines), only the explicit anchor is emitted — the explicit
    anchor is the canonical link target and supersedes the auto-slug.
    This lets generators scope colliding method headings (``.ask`` on
    Loop/FanOut/Pipeline) with anchors like ``(method-loop-ask)=``
    without the validator flagging the auto-slug collision.
    """
    out: list[str] = []
    pending_anchor = False
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        # Track fenced code blocks (``` or ~~~, optionally with a language or
        # MyST ``{mermaid}``-style directive). Lines inside a fence never
        # contribute headings — a comment like ``# foo`` inside ```python``` is
        # code, not markdown.
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            pending_anchor = False
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            if not pending_anchor:
                out.append(_slugify(m.group(2)))
            pending_anchor = False
            continue
        a = EXPLICIT_ANCHOR_RE.match(line)
        if a:
            out.append(a.group("name"))
            pending_anchor = True
            continue
        if stripped == "":
            # blank line between anchor and heading — keep pending
            continue
        pending_anchor = False
    return out


def _find_md_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.md"))


def _extract_python_fences(text: str) -> list[tuple[int, str]]:
    """Yield (start_line, body) tuples for every ```python fenced block."""
    out: list[tuple[int, str]] = []
    in_fence = False
    fence_start = 0
    buf: list[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not in_fence:
            if stripped.startswith("```python") or stripped.startswith("```py"):
                in_fence = True
                fence_start = i
                buf = []
        else:
            if stripped.startswith("```"):
                out.append((fence_start, "\n".join(buf)))
                in_fence = False
            else:
                buf.append(line)
    return out


_SIGNATURE_ONLY_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*\([^)]*:\s")


def _check_python_syntax(code: str) -> str | None:
    """Return error message if the block has a syntax error, else None.

    We deliberately ignore blocks that look like REPL transcripts (``>>> ``),
    partial method bodies (leading indentation with no def/class), signature
    documentation (``ClassName(arg: type)``), or shell commands.  The goal
    is to catch typo-level breakage, not to execute code.
    """
    if not code.strip():
        return None
    first = code.lstrip().splitlines()[0].strip()
    if first.startswith((">>> ", "$ ", "# ")):
        return None
    if code.lstrip().startswith((" ", "\t")) and "def " not in code and "class " not in code:
        return None
    # Single-line signature documentation (``BaseAgent(name: str) -> None``).
    if "\n" not in code.strip() and _SIGNATURE_ONLY_RE.match(first):
        return None
    # Allow top-level ``await``/``async for`` inside fenced samples (common in docs).
    try:
        compile(code, "<fence>", "exec", flags=0x2000)  # PyCF_ALLOW_TOP_LEVEL_AWAIT
    except SyntaxError as exc:
        return f"line {exc.lineno}: {exc.msg}"
    return None


def validate_tree(root: Path, *, check_code_fences: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    files = _find_md_files(root)
    known = {p.resolve() for p in files}

    # Directories that are excluded from the Sphinx build (see conf.py
    # exclude_patterns) — we skip code-fence checks there because design
    # notes and historical specs routinely contain illustrative pseudocode.
    code_fence_skip_parts = {"plans", "other_specs", "architecture", "superpowers"}

    # Generic section-heading slugs that recur once per builder in API
    # pages (agent.md, tool.md, workflow.md). They are never link targets
    # — every builder has an explicit ``(builder-<name>)=`` anchor above
    # it — so their collisions are benign and should not be reported.
    ignored_duplicate_slugs = {
        "constructor",
        "callbacks",
        "configuration",
        "core-configuration",
        "control-flow-execution",
        "forwarded-fields",
        "composition-operators",
        "state-transforms",
        # Generic sub-section headers that recur inside narrative pages
        # (comparison matrices, error catalogs, side-by-side examples).
        # They are never used as link targets — local per-entry anchors
        # live above them where needed.
        "fluent",
        "native",
        "native-adk-equivalent",
        "equivalent-to",
        "fix",
        "common-causes",
        "adk-fluent",
        "langgraph",
        "same-pipeline-definition-just-add-engine",
        "declarative-surface",
        "llm-guided-mode",
        "approvalmemory",
        "permissiondecision",
        # Plan-doc skeleton headings — these files are excluded from
        # the Sphinx build but live under ``docs/plans/`` for history.
        "mechanism",
        "problem",
        "solution",
        "generated-code",
        "implementation",
        "verification",
    }

    plan_tree_parts = {"plans", "other_specs"}

    for md in files:
        text = md.read_text()
        headings = _collect_headings(text)
        headings_lower = {h.lower() for h in headings}
        in_plan_tree = bool(plan_tree_parts.intersection(md.parts))

        if check_code_fences and not code_fence_skip_parts.intersection(md.parts):
            for start, body in _extract_python_fences(text):
                err = _check_python_syntax(body)
                if err:
                    findings.append(Finding(md, start, "bad-python", err))

        # Plan/spec docs live under docs/plans/ and docs/other_specs/ and
        # are excluded from the Sphinx build. Their internal link hygiene
        # is not part of the published site, so we skip duplicate-anchor
        # and dangling-link reporting for them.
        if in_plan_tree:
            continue

        dupes = {
            h
            for h in headings
            if headings.count(h) > 1 and h != "" and h not in ignored_duplicate_slugs
        }
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
                    if anchor and anchor.lower() not in headings_lower:
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
                    target_lower = {h.lower() for h in _collect_headings(resolved.read_text())}
                    if anchor.lower() not in target_lower:
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
    parser.add_argument(
        "--check-code-fences",
        action="store_true",
        help="Also compile every ```python fenced block to catch syntax errors",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"docs_validator: root {root} is not a directory", file=sys.stderr)
        return 2

    findings = validate_tree(root, check_code_fences=args.check_code_fences)
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
