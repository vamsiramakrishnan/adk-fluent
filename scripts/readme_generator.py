#!/usr/bin/env python3
"""
README GENERATOR
================
Reads README.template.md and dynamically injects:
1. Mermaid diagram of a sample complex pipeline.

Usage:
    python scripts/readme_generator.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure adk_fluent is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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

    pipeline = (
        Pipeline("customer_support")
        .step(
            Agent("classifier", "gemini-2.5-flash")
            .instruct("Classify the customer's intent.")
            .outputs("intent")
            .before_model(log_fn)
        )
        .step(
            Agent("resolver", "gemini-2.5-flash")
            .instruct("Resolve the {intent} issue.")
            .tool(lookup_customer)
            .tool(create_ticket)
            .history("none")
        )
        .step(
            Agent("responder", "gemini-2.5-flash").instruct("Draft a response to the customer.").after_model(audit_fn)
        )
    )
    return pipeline


def main():
    repo_root = Path(__file__).parent.parent
    template_path = repo_root / "README.template.md"
    readme_path = repo_root / "README.md"

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

    # Inject it
    new_content = template_content.replace("<!-- INJECT_MERMAID_DIAGRAM -->", mermaid_block)

    readme_path.write_text(new_content)
    print("README.md successfully generated with dynamic content.")


if __name__ == "__main__":
    main()
