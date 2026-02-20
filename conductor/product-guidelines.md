# Product Guidelines - adk-fluent

## Documentation Style
- **Clarity First:** Use technical but accessible language. Explain the "why" before the "how".
- **Visual Evidence:** Every major concept should be accompanied by a side-by-side comparison (Native ADK vs. Fluent) or a Mermaid diagram.
- **Tone:** Professional, direct, and developer-obsessed. Assume the reader is an expert looking for efficiency.
- **Formatting:** Use GitHub-flavored Markdown. Ensure code blocks are syntax-highlighted and logically grouped.

## Code Ergonomics (DX)
- **Chainability:** Every configuration method must return \`self\` to maintain the fluent flow.
- **Discovery:** Leverage type stubs (\`.pyi\`) to ensure that \`dir()\` and IDE autocomplete provide 100% coverage of the API.
- **Fail-Fast:** Catch configuration errors at build time using the contract checker rather than letting them fail at runtime in ADK.
- **Immutability:** Treat builders as immutable blueprints. Operations like \`>>\` should create new IR nodes rather than mutating existing ones.

## Visual Branding
- **Mermaid Aesthetics:** Use standard, clean Mermaid graph styles for execution DAGs. Ensure nodes are clearly labeled with their roles (e.g., \`[Agent]\`, \`[Route]\`).
- **Terminal UI:** Use the \`rich\` library for terminal output to provide color-coded, structured information that is easy to scan.

## Quality Standards
- **Sync Integrity:** The library must never manually re-implement logic found in ADK. It must purely be a builder/orchestrator layer.
- **Test-Driven Codegen:** Any change to the codegen pipeline must be verified by both generated equivalence tests and manual edge-case tests.
- **Zero Token Waste:** Context Engineering defaults must aggressively prune redundant information from prompts.
