# Changelog

## v0.3.0

- Sphinx documentation site with Furo theme, deployed to GitHub Pages
- New primitives: `.tap()`, `.expect()`, `.mock()`, `.retry_if()`, `.map_over()`, `.timeout()`, `.gate()`, `.race()`
- Overhauled `doc_generator.py` with MyST cross-references, tabbed cookbook, enriched migration guide
- Auto-generated API index and cookbook index pages
- CI docs stage for Sphinx build validation
- GitHub Actions workflow for docs deployment
- 8 new cookbook examples (35-42)
- Regenerated builders for latest ADK

## v0.2.2

- Fix: exclude `.pip-cache` from sdist

## v0.2.1

- Internal improvements

## v0.2.0

- Expression algebra release (`>>`, `|`, `*`, `@`, `//`, `Route`, `S` operators)
- Prompt builder
- State transforms
