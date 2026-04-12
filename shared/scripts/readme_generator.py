#!/usr/bin/env python3
"""
README GENERATOR
================
Reads README.template.md and dynamically injects:
1. Mermaid diagram of a sample complex pipeline.
2. Changelog highlights (latest N releases from CHANGELOG.md).

Usage:
    python scripts/readme_generator.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Ensure adk_fluent is importable when invoked outside the python uv project.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "python" / "src"))

from adk_fluent import Agent, Pipeline


def build_sample_pipeline():
    """Build the complex customer support pipeline shown in the README to generate its Mermaid diagram."""

    def log_fn(ctx, req):
        pass

    def audit_fn(ctx, res):
        pass

    def lookup_customer(id):
        pass

    def create_ticket(issue):
        pass

    from adk_fluent import C

    pipeline = (
        Pipeline("customer_support")
        .step(
            Agent("classifier", "gemini-2.5-flash")
            .instruct("Classify the customer's intent.")
            .writes("intent")
            .before_model(log_fn)
        )
        .step(
            Agent("resolver", "gemini-2.5-flash")
            .instruct("Resolve the {intent} issue.")
            .tool(lookup_customer)
            .tool(create_ticket)
            .context(C.none())
        )
        .step(
            Agent("responder", "gemini-2.5-flash").instruct("Draft a response to the customer.").after_model(audit_fn)
        )
    )
    return pipeline


def extract_changelog_highlights(changelog_path: Path, max_releases: int = 5) -> str:
    """Extract one-line summaries for the latest N releases from CHANGELOG.md."""
    if not changelog_path.exists():
        return ""

    text = changelog_path.read_text()
    # Match version headers like: ## [0.13.2] - 2026-03-17
    release_pattern = re.compile(r"^## \[(\d+\.\d+\.\d+[^\]]*)\]\s*-\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
    releases = list(release_pattern.finditer(text))

    if not releases:
        return ""

    lines = []
    for match in releases[:max_releases]:
        version = match.group(1)
        # Extract the content between this header and the next
        start = match.end()
        # Find next release header or end of file
        next_match = release_pattern.search(text, start)
        end = next_match.start() if next_match else len(text)
        section = text[start:end]

        # Collect top-level bullet points from ### Added section (most interesting)
        highlights = []
        in_added = False
        for line in section.splitlines():
            if line.startswith("### Added"):
                in_added = True
                continue
            if line.startswith("### "):
                in_added = False
                continue
            if in_added and line.startswith("- **"):
                # Extract the bold title
                bold_match = re.match(r"- \*\*(.+?)\*\*", line)
                if bold_match:
                    highlights.append(bold_match.group(1))

        if not highlights:
            # Fallback: grab from any section
            for line in section.splitlines():
                if line.startswith("- **"):
                    bold_match = re.match(r"- \*\*(.+?)\*\*", line)
                    if bold_match:
                        highlights.append(bold_match.group(1))
                        if len(highlights) >= 3:
                            break

        summary = ", ".join(highlights[:3]) if highlights else "see changelog"
        lines.append(f"- **v{version}** -- {summary}")

    return "\n".join(lines)


def main():
    # File lives at <repo_root>/shared/scripts/readme_generator.py — three
    # parents up land at the repo root after the monorepo restructure.
    repo_root = Path(__file__).resolve().parent.parent.parent
    template_path = repo_root / "README.template.md"
    readme_path = repo_root / "README.md"
    changelog_path = repo_root / "CHANGELOG.md"

    if not template_path.exists():
        print("Error: README.template.md not found.", file=sys.stderr)
        sys.exit(1)

    template_content = template_path.read_text()

    # Generate the Mermaid diagram
    pipeline = build_sample_pipeline()
    mermaid_src = pipeline.to_mermaid()

    mermaid_block = f"""### Pipeline Architecture

```mermaid
{mermaid_src}
```
"""

    # Generate changelog highlights
    changelog_highlights = extract_changelog_highlights(changelog_path)

    # Inject dynamic content
    new_content = template_content.replace("<!-- INJECT_MERMAID_DIAGRAM -->", mermaid_block)
    new_content = new_content.replace("<!-- INJECT_CHANGELOG_HIGHLIGHTS -->", changelog_highlights)

    readme_path.write_text(new_content)

    # PyPI build (hatchling) reads `readme = "README.md"` from python/pyproject.toml
    # and the file must physically exist next to that pyproject.toml for both the
    # metadata read and the wheel-from-sdist step to succeed. Keep python/README.md
    # in lockstep with the repo-root README so PyPI shows the same content GitHub does.
    python_readme = repo_root / "python" / "README.md"
    if python_readme.parent.exists():
        python_readme.write_text(new_content)

    print("README.md successfully generated with dynamic content.")
    if changelog_highlights:
        count = changelog_highlights.count("\n") + 1
        print(f"  Changelog highlights: {count} releases injected.")


if __name__ == "__main__":
    main()
