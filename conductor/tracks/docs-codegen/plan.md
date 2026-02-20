# Plan: Auto-Generated World-Class Docs & README ("Rising with the Tide")

## Context
The user wants to elevate the documentation and `README.md` to world-class OSS standards by heavily leveraging the `@scripts/**` codegen pipeline. By automating documentation generation alongside the code, the docs will automatically "rise with the tide" whenever the underlying ADK updates, ensuring zero drift between implementation and documentation. 

The goal is also to innovate on the `README.md` to make it visually wonderful and functionally bulletproof.

## [DONE] Phase 1: Dynamic README Generation
Currently, the `README.md` is static. We will convert it into an auto-generated artifact driven by the codegen pipeline.

- **Create `README.template.md`**: Move the core narrative of the current README into a template file with injection markers (e.g., `<!-- INJECT_API_OVERVIEW -->`, `<!-- INJECT_EXPRESSION_ALGEBRA -->`).
- **Implement `scripts/readme_generator.py`**:
  - Parse `seed.toml` and `manifest.json` to dynamically generate the "API Overview" and "Expression Language" tables.
  - Automatically pull the latest "Quick Start" code directly from verified, runnable cookbook examples (e.g., `examples/cookbook/01_simple_agent.py`) so the README examples are continuously tested and never break.
  - Automatically generate and inject a `Mermaid` architecture diagram using the library's `.to_mermaid()` capability on a sample pipeline.
- **Hook into `justfile`**: Add `python scripts/readme_generator.py` to the `just all` target.

## [DONE] Phase 2: Supercharging `scripts/doc_generator.py`
We will enhance the existing `doc_generator.py` to produce richer, semantically grouped documentation.

- **Semantic Grouping**: Instead of listing all methods alphabetically, update `doc_generator.py` to categorize methods based on their function (e.g., *Core Configuration*, *Control Flow*, *State Transforms*, *Callbacks*).
- **Auto-Extracting Docstring Examples**: Parse `Example:` blocks from the Python source/manifest and inject them as syntax-highlighted code blocks in the generated API markdown.
- **Architecture & Thesis Auto-Generation**: Extract core concepts from `docs/other_specs/*` and integrate them as the front-page conceptual onboarding in `docs/generated/user-guide/`.

## [DONE] Phase 3: Visuals and Aesthetics (The "Wonderful" Factor)
- **Mermaid DAG Auto-rendering**: Update `cookbook_generator.py` and `doc_generator.py` to compile an agent pipeline to a Mermaid graph (`pipeline.to_mermaid()`) and inject it into the generated documentation.
- **Side-by-Side Code Comparisons**: Ensure the cookbook generation script creates rich Sphinx `tab-set` comparisons showing Native ADK vs. Fluent ADK, proving the brevity and elegance of the library automatically.

## Track Summary
All phases of the "Rising with the Tide" documentation infrastructure are complete. The project now features a fully automated documentation pipeline that:
1. Keeps the `README.md` in sync with real code and visualizes its architecture.
2. Organizes the API reference semantically with inline examples.
3. Distills deep architectural theory from raw specs into an accessible User Guide.
4. Dynamically generates visuals for every cookbook recipe by "dry-running" the examples during documentation build.
