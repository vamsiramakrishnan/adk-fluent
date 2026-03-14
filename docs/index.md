# adk-fluent

```{raw} html
<div class="hero-section">
  <h1>adk-fluent</h1>
  <p class="hero-tagline">
    The fluent builder API for Google's Agent Development Kit.<br>
    Go from idea to production agent in lines, not pages.
  </p>
  <div class="hero-stats">
    <div class="hero-stat">
      <span class="stat-number">132</span>
      <span class="stat-label">Builders</span>
    </div>
    <div class="hero-stat">
      <span class="stat-number">9</span>
      <span class="stat-label">Namespace Modules</span>
    </div>
    <div class="hero-stat">
      <span class="stat-number">67</span>
      <span class="stat-label">Cookbook Recipes</span>
    </div>
    <div class="hero-stat">
      <span class="stat-number">100%</span>
      <span class="stat-label">Native ADK</span>
    </div>
  </div>
</div>
```

## The Problem

Building agents with native ADK means writing 15-25 lines of constructor
boilerplate per agent, manually wiring `SequentialAgent`, `ParallelAgent`,
and `LoopAgent` hierarchies, and hoping you didn't misspell a keyword argument
that gets silently ignored. adk-fluent fixes this.

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

:::{admonition} For the skeptic
:class: tip

adk-fluent doesn't replace ADK. It **is** ADK. Every builder produces an
identical native object -- same classes, same runtime, same deployment targets.
You get type-safe method chaining, typo detection at definition time, and
composable operators. You lose nothing.
:::

| Pain point | Native ADK | adk-fluent |
|---|---|---|
| Typo in `instruction` kwarg | Silently ignored | `AttributeError` with "Did you mean?" |
| Pipeline composition | Manual `sub_agents=[]` wiring | `a >> b >> c` |
| Parallel execution | `ParallelAgent(sub_agents=[...])` | `a \| b \| c` |
| Conditional loops | Custom `BaseAgent` subclass | `(a >> b) * until(pred)` |
| Typed output | `output_schema=Model` | `agent @ Model` |
| Context isolation | `include_contents="none"` | `C.none()` |
| Testing without LLM | Not built-in | `.mock()`, `.test()`, `check_contracts()` |
| Visualization | Not built-in | `.explain()`, `.to_mermaid()`, `.diagnose()` |

## Install

```bash
pip install adk-fluent
```

Autocomplete works immediately -- the package ships `.pyi` stubs for every builder.

## Your Learning Path

```{raw} html
<div class="journey-step" data-step="1">
  <div class="journey-content">
    <h4><a href="getting-started.html">Getting Started</a></h4>
    <p>Install, configure your IDE, and build your first agent in 5 minutes. Learn the builder pattern and expression operators.</p>
  </div>
</div>
<div class="journey-step" data-step="2">
  <div class="journey-content">
    <h4><a href="user-guide/index.html">User Guide</a></h4>
    <p>Deep dive into builders, data flow, context engineering, prompts, callbacks, middleware, and testing. Master the 9 namespace modules (S, C, P, A, M, T, E, G).</p>
  </div>
</div>
<div class="journey-step" data-step="3">
  <div class="journey-content">
    <h4><a href="cookbook/index.html">Cookbook &mdash; Zero to Symphony</a></h4>
    <p>67 copy-pasteable recipes progressing from fundamentals through hero workflows. Every recipe shows adk-fluent and native ADK side by side.</p>
  </div>
</div>
<div class="journey-step" data-step="4">
  <div class="journey-content">
    <h4><a href="generated/api/index.html">API Reference</a></h4>
    <p>Complete method reference for all 132 builders across 9 modules. Every method includes type signature, ADK mapping, and code example.</p>
  </div>
</div>
```

## Quick Navigation

````{grid} 1 2 2 3
---
gutter: 3
---
```{grid-item-card} Getting Started
:link: getting-started
:link-type: doc
Install and build your first agent in 5 minutes.
```

```{grid-item-card} Editor & AI Agent Setup
:link: editor-setup/index
:link-type: doc
Configure Claude Code, Cursor, Copilot, and other AI coding agents.
```

```{grid-item-card} User Guide
:link: user-guide/index
:link-type: doc
Builders, operators, context engineering, prompts, callbacks, middleware.
```

```{grid-item-card} Cookbook
:link: cookbook/index
:link-type: doc
67 recipes from fundamentals to hero workflows.
```

```{grid-item-card} API Reference
:link: generated/api/index
:link-type: doc
Complete reference for all 132 builders.
```

```{grid-item-card} Framework Comparison
:link: user-guide/comparison
:link-type: doc
Side-by-side with LangGraph, CrewAI, and native ADK.
```

```{grid-item-card} Migration Guide
:link: generated/migration/from-native-adk
:link-type: doc
Migrate existing native ADK code incrementally.
```

```{grid-item-card} Error Reference
:link: user-guide/error-reference
:link-type: doc
Every error explained with fix-it examples.
```

```{grid-item-card} Decision Guide
:link: decision-guide
:link-type: doc
"Which pattern should I use?" — flowchart for common decisions.
```

```{grid-item-card} Agent Skills
:link: editor-setup/agent-skills
:link-type: doc
8 portable skills for AI coding agents — develop, test, debug, and review adk-fluent projects.
```
````

## Common Starting Points

**"I have native ADK code and want to simplify it"** -- Start with the [Migration Guide](generated/migration/from-native-adk.md), then browse the [Cookbook](cookbook/index.md) for your pattern.

**"I'm building agents from scratch"** -- Start with [Getting Started](getting-started.md), then follow the [User Guide](user-guide/index.md) sequentially.

**"I need a specific pattern (routing, loops, parallel)"** -- Jump to [Patterns](user-guide/patterns.md) or search the [Cookbook by use case](generated/cookbook/recipes-by-use-case.md).

**"I want to understand what the LLM actually sees"** -- Read [Context Engineering](user-guide/context-engineering.md) and [Prompts](user-guide/prompts.md).

**"I need to test my agents without API calls"** -- Read [Testing](user-guide/testing.md) for `.mock()`, `.test()`, and `check_contracts()`.

**"I want my AI coding agent to know adk-fluent"** -- Set up [Editor & AI Agent Setup](editor-setup/index.md) for rules files and MCP servers, then install [Agent Skills](editor-setup/agent-skills.md) for step-by-step procedures.

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
caption: Cookbook — Zero to Symphony
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
caption: Project
---
changelog
```
