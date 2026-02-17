# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2025-02-17

### Added
- 6 ADK sample ports: LLM Auditor, Financial Advisor, Short Movie, Deep Search, Brand Search, Travel Concierge
- Pipeline operators (`>>`, `* until()`, `@ Schema`) on Deep Search example
- `.sub_agent()` as canonical method for adding sub-agents
- `.include_history()` alias for `include_contents`
- `FanOut.step()` alias for `.branch()` (API consistency with Pipeline/Loop)
- `deprecation_alias` behavior in code generator
- Per-alias `field_docs` support in generator for alias-specific docstrings
- Cookbook #43: primitives showcase (`tap`, `expect`, `gate`, `Route`, `S.*`)
- `py.typed` marker (PEP 561)

### Changed
- `.tool()` docstring clarifies append semantics vs `.tools()` replace
- `.output_schema()` docstring clarifies relationship with `@` operator
- `.tap()` and `.timeout()` docstrings warn about builder type change
- Updated cookbook #07 to use `.sub_agent()` instead of `.member()`

### Deprecated
- `.member()` — use `.sub_agent()` instead (emits `DeprecationWarning`)

## [0.3.1] - 2025-02-17

### Changed
- Migrated CI/CD and project URLs from GitLab to GitHub
- Updated documentation URL to GitHub Pages

## [0.3.0] - 2025-02-16

### Added
- New primitives: `tap`, `expect`, `gate`, `race`, `map_over`, `mock`, `retry_if`, `timeout`
- `Route` builder for deterministic state-based branching
- `S` state transform factories (`pick`, `drop`, `rename`, `default`, `merge`, `transform`, `compute`, `guard`, `log`)
- `Prompt` builder for structured multi-section prompt composition
- `Preset` for reusable configuration bundles
- `@agent` decorator for FastAPI-style agent definition
- `StateKey` typed state descriptors
- Fallback operator `//`
- Function steps via `>> fn`
- Dict routing shorthand `>> {"key": agent}`
- `.proceed_if()` conditional gating
- `.loop_until()` conditional loop exit
- `.inject_context()` for dynamic context injection
- `.static()` for context-cacheable instructions
- `.clone()` and `.with_()` for immutable variants
- `.validate()` and `.explain()` introspection
- `.to_dict()`, `.to_yaml()`, `.from_dict()`, `.from_yaml()` serialization
- `.ask()`, `.stream()`, `.session()`, `.map()` one-shot execution
- `.test()` inline smoke testing
- Cookbook examples 17-42
- Sphinx documentation site with Furo theme
- Generated API reference, migration guide, cookbook docs

## [0.2.0] - 2025-02-15

### Added
- Expression algebra: `>>` (sequence), `|` (parallel), `*` (loop), `@` (typed output)
- Conditional `_if` callback variants
- Variadic callback methods
- `__getattr__` forwarding with typo detection
- `.pyi` type stubs for all builders
- Cookbook examples 01-16

## [0.1.0] - 2025-02-14

### Added
- Initial release
- `Agent`, `Pipeline`, `FanOut`, `Loop` fluent builders
- 130+ auto-generated builders from ADK Pydantic schemas
- Code generator pipeline: scanner -> seed_generator -> generator
- justfile development workflow
- CI/CD with GitHub Actions
- PyPI publishing via Trusted Publishing (OIDC)

[0.4.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/vamsiramakrishnan/adk-fluent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/vamsiramakrishnan/adk-fluent/releases/tag/v0.1.0
