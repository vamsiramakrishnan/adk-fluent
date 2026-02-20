import sys
from pathlib import Path


def main():
    repo_root = Path(__file__).parent.parent
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

        # Extract everything from "## The Three Channels" down to the next H1 or end
        extracting = False
        for line in lines:
            if line.startswith("## The Three Channels"):
                extracting = True
            elif extracting and line.startswith("# "):
                break

            if extracting:
                content.append(line)

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

        extracting = False
        for line in lines:
            if "| Operation |" in line:
                extracting = True
            elif extracting and not line.strip().startswith("|"):
                extracting = False
                break

            if extracting:
                content.append(line)

        content.append("")

    output_path.write_text("\n".join(content))
    print(f"Generated {output_path}")

    # Inject into index.md
    index_path = repo_root / "docs" / "user-guide" / "index.md"
    index_content = index_path.read_text()
    if "architecture-and-concepts" not in index_content:
        # insert it as the first item in the toctree
        index_content = index_content.replace(":maxdepth: 2\n", ":maxdepth: 2\n\narchitecture-and-concepts")
        index_path.write_text(index_content)
        print("Injected architecture-and-concepts into user-guide/index.md")


if __name__ == "__main__":
    main()
