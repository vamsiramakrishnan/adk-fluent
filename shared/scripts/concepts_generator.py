import re
import sys
from pathlib import Path


def _extract_three_channels(lines: list[str]) -> list[str]:
    """Extract the '## The Three Channels' H2 block up to the next H1.

    Raises ValueError if the heading is not found so drift in the source
    spec surfaces loudly instead of producing a silent 4-line stub.
    """
    extracting = False
    collected: list[str] = []
    for line in lines:
        if line.startswith("## The Three Channels"):
            extracting = True
        elif extracting and line.startswith("# "):
            break
        if extracting:
            collected.append(line)

    if not collected:
        raise ValueError(
            "concepts_generator: '## The Three Channels' heading not found in "
            "adk_fluent_v51_state_thesis.md. Was the heading renamed?"
        )
    return collected


def _extract_operations_table(lines: list[str]) -> list[str]:
    """Extract the '| Operation |' markdown table.

    Raises ValueError when the table header is missing — a missing table
    used to silently produce an empty section.
    """
    header_re = re.compile(r"^\|\s*Operation\s*\|")
    extracting = False
    collected: list[str] = []
    for line in lines:
        if header_re.match(line):
            extracting = True
        elif extracting and not line.strip().startswith("|"):
            break
        if extracting:
            collected.append(line)

    if not collected:
        raise ValueError(
            "concepts_generator: '| Operation |' table not found in "
            "adk_fluent_v51_context.md. Was the table restructured?"
        )
    return collected


def _inject_into_toctree(index_path: Path, entry: str) -> bool:
    """Insert `entry` as the first item in the user-guide toctree.

    Returns True if a write happened. The previous implementation only
    checked for substring presence before replacing a hard-coded
    ``:maxdepth: 2\\n`` marker; a `:maxdepth: 3` index would silently
    pass the guard but never receive the injection. This version
    matches any maxdepth and any trailing whitespace, then checks that
    the replacement actually took effect before writing.
    """
    index_content = index_path.read_text()
    if entry in index_content:
        return False

    pattern = re.compile(r"(:maxdepth:\s*\d+\s*\n)")
    new_content, n_subs = pattern.subn(r"\1\n" + entry, index_content, count=1)
    if n_subs == 0:
        raise ValueError(
            f"concepts_generator: could not find a toctree ':maxdepth:' directive in "
            f"{index_path} to inject '{entry}'. Did the toctree format change?"
        )
    if entry not in new_content:
        raise RuntimeError(
            f"concepts_generator: TOC injection of '{entry}' produced no change in "
            f"{index_path}; refusing to write."
        )
    index_path.write_text(new_content)
    return True


def main():
    # File lives at <repo_root>/shared/scripts/concepts_generator.py — three
    # parents up land at the repo root after the monorepo restructure.
    repo_root = Path(__file__).resolve().parent.parent.parent
    specs_dir = repo_root / "docs" / "other_specs"
    output_path = repo_root / "docs" / "user-guide" / "architecture-and-concepts.md"

    if not specs_dir.exists():
        print(f"Error: {specs_dir} not found.", file=sys.stderr)
        return

    content = [
        "# Architecture & Core Concepts",
        "",
        "Before diving into builders and operators, it's crucial to understand the underlying mechanics of ADK and how `adk-fluent` interacts with them. This conceptual foundation will help you design robust, predictable agent systems.",
        "",
    ]

    # 1. State Thesis
    state_thesis_file = specs_dir / "adk_fluent_v51_state_thesis.md"
    if state_thesis_file.exists():
        lines = state_thesis_file.read_text().splitlines()
        content.extend(_extract_three_channels(lines))
        content.append("")
        content.append("---")
        content.append("")

    # 2. Context Engineering
    context_file = specs_dir / "adk_fluent_v51_context.md"
    if context_file.exists():
        lines = context_file.read_text().splitlines()

        content.append("## Context Engineering: The Five Operations")
        content.append("")
        content.append(
            "Context engineering is not just overflow handling. It is the *continuous discipline* of assembling the smallest, highest-signal token set that maximizes an agent's likelihood of producing the desired outcome."
        )
        content.append("")
        content.extend(_extract_operations_table(lines))

    # Strip trailing empty strings to avoid double newlines at EOF
    while content and content[-1] == "":
        content.pop()
    output_path.write_text("\n".join(content) + "\n")
    print(f"Generated {output_path}")

    # Inject into user-guide/index.md toctree (idempotent, format-tolerant)
    index_path = repo_root / "docs" / "user-guide" / "index.md"
    if _inject_into_toctree(index_path, "architecture-and-concepts"):
        print("Injected architecture-and-concepts into user-guide/index.md")


if __name__ == "__main__":
    main()
