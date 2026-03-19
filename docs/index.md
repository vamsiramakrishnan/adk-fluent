---
hide-toc: true
---

# adk-fluent

```{raw} html
<div class="hero-section">
  <h1>adk-fluent</h1>
  <p class="hero-tagline">
    Fluent builder API for Google ADK. 22 lines &rarr; 3 lines. Same native objects.
  </p>

  <div class="badges">
    <a href="https://pypi.org/project/adk-fluent/"><img src="https://img.shields.io/pypi/v/adk-fluent?color=E65100&style=flat-square" alt="PyPI version"></a>
    <a href="https://pypi.org/project/adk-fluent/"><img src="https://img.shields.io/pypi/dm/adk-fluent?color=F57C00&style=flat-square" alt="Downloads"></a>
    <a href="https://pypi.org/project/adk-fluent/"><img src="https://img.shields.io/pypi/pyversions/adk-fluent?color=FFB74D&style=flat-square" alt="Python versions"></a>
    <a href="https://github.com/vamsiramakrishnan/adk-fluent/blob/master/LICENSE"><img src="https://img.shields.io/github/license/vamsiramakrishnan/adk-fluent?color=424242&style=flat-square" alt="License"></a>
    <a href="https://github.com/vamsiramakrishnan/adk-fluent/actions"><img src="https://img.shields.io/github/actions/workflow/status/vamsiramakrishnan/adk-fluent/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
    <a href="https://vamsiramakrishnan.github.io/adk-fluent/"><img src="https://img.shields.io/badge/docs-latest-E65100?style=flat-square" alt="Docs"></a>
  </div>

  <div class="hero-install">
    <span style="color: var(--adk-text-faint)">$</span>
    <code>pip install adk-fluent</code>
  </div>
  <div class="hero-stats">
    <div class="hero-stat">
      <span class="stat-number">135</span>
      <span class="stat-label">Builders</span>
    </div>
    <div class="hero-stat">
      <span class="stat-number">9</span>
      <span class="stat-label">Modules</span>
    </div>
    <div class="hero-stat">
      <span class="stat-number">67</span>
      <span class="stat-label">Recipes</span>
    </div>
    <div class="hero-stat">
      <span class="stat-number">100%</span>
      <span class="stat-label">Native ADK</span>
    </div>
  </div>
</div>
```

## Before / After

::::{tab-set}
:::{tab-item} adk-fluent (5 lines)
```python
from adk_fluent import Agent, S, C

research = (
    Agent("analyzer", "gemini-2.5-flash").instruct("Decompose the query.").writes("plan")
    >> (Agent("web", "gemini-2.5-flash").instruct("Search web.").context(C.from_state("plan")).writes("web")
        | Agent("papers", "gemini-2.5-flash").instruct("Search papers.").context(C.from_state("plan")).writes("papers"))
    >> Agent("writer", "gemini-2.5-flash").instruct("Synthesize findings from {web} and {papers}.")
)
```
:::
:::{tab-item} Native ADK (22 lines)
```python
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.parallel_agent import ParallelAgent

analyzer = LlmAgent(name="analyzer", model="gemini-2.5-flash",
    instruction="Decompose the query.", output_key="plan")
web = LlmAgent(name="web", model="gemini-2.5-flash",
    instruction="Search web.", output_key="web",
    include_contents="none")  # context filtering
papers = LlmAgent(name="papers", model="gemini-2.5-flash",
    instruction="Search papers.", output_key="papers",
    include_contents="none")
writer = LlmAgent(name="writer", model="gemini-2.5-flash",
    instruction="Synthesize findings from {web} and {papers}.")

parallel = ParallelAgent(name="search", sub_agents=[web, papers])
research = SequentialAgent(
    name="research",
    sub_agents=[analyzer, parallel, writer],
)
```
:::
::::

Every `.build()` returns a real ADK object -- fully compatible with `adk web`, `adk run`, and `adk deploy`.

## Why adk-fluent?

::::{grid} 1 1 3 3
---
gutter: 3
---
:::{grid-item-card} 130+ Builders, Full Autocomplete
Every builder ships with `.pyi` stubs. Type `Agent("name").` and your IDE shows all methods with type hints, parameter docs, and ADK mapping.
:::
:::{grid-item-card} Expression Algebra
`>>` for sequential, `|` for parallel, `*` for loops, `@` for typed output, `//` for fallback. Compose any topology in a single expression.
:::
:::{grid-item-card} Always in Sync
Builders are auto-generated from installed ADK. When ADK updates, regenerate and get new features immediately. Zero maintenance.
:::
::::

## Quick Navigation

````{grid} 1 2 2 4
---
gutter: 3
---
```{grid-item-card} Getting Started
:link: getting-started
:link-type: doc
Install and build your first agent in 5 minutes.
```

```{grid-item-card} User Guide
:link: user-guide/index
:link-type: doc
Builders, operators, context engineering, prompts, callbacks, middleware.
```

```{grid-item-card} API Reference
:link: generated/api/index
:link-type: doc
Complete reference for all 135 builders.
```

```{grid-item-card} Cookbook
:link: cookbook/index
:link-type: doc
68 recipes from fundamentals to hero workflows.
```
````

## Common Starting Points

**"I have native ADK code and want to simplify it"** -- Start with the [Migration Guide](generated/migration/from-native-adk.md), then browse the [Cookbook](cookbook/index.md) for your pattern.

**"I'm building agents from scratch"** -- Start with [Getting Started](getting-started.md), then follow the [User Guide](user-guide/index.md) sequentially.

**"I need a specific pattern (routing, loops, parallel)"** -- Jump to [Patterns](user-guide/patterns.md) or search the [Cookbook by use case](generated/cookbook/recipes-by-use-case.md).

**"I want my AI coding agent to know adk-fluent"** -- Set up [Editor & AI Agent Setup](editor-setup/index.md) for rules files and MCP servers.

---

[PyPI](https://pypi.org/project/adk-fluent/) · [GitHub](https://github.com/vamsiramakrishnan/adk-fluent) · [Changelog](changelog.md) · [Contributing](contributing/index.md)

```{toctree}
---
maxdepth: 2
caption: Getting Started
---
getting-started
editor-setup/index
```

```{toctree}
---
maxdepth: 2
caption: User Guide
---
user-guide/index
```

```{toctree}
---
maxdepth: 2
caption: API Reference
---
generated/api/index
```

```{toctree}
---
maxdepth: 2
caption: Cookbook
---
cookbook/index
```

```{toctree}
---
maxdepth: 2
caption: All Recipes (Auto-Generated)
---
generated/cookbook/index
```

```{toctree}
---
maxdepth: 2
caption: Examples
---
runnable-examples
```

```{toctree}
---
maxdepth: 1
caption: Guides
---
decision-guide
generated/migration/from-native-adk
```

```{toctree}
---
maxdepth: 2
caption: Contributing
---
contributing/index
```

```{toctree}
---
maxdepth: 1
caption: Research
---
research/a2a-fluent-integration
research/a2a-spec-audit
research/durable-execution-five-layer-decoupling
research/execution-backend-compatibility-matrix
research/execution-backend-devex-audit
research/packaging-deployment-dx-radical-improvement
research/dx-appendix-a-self-critique
research/dx-appendix-b-deployment-targets
research/dx-appendix-c-scaffolding-codegen
research/dx-appendix-d-local-dev-infra
research/dx-appendix-e-adk-web-lessons
research/tech-debt-audit
```

```{toctree}
---
maxdepth: 1
caption: Project
---
changelog
```
