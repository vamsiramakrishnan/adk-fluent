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

  <!-- Architecture flow diagram -->
  <div class="hero-diagram">
    <svg viewBox="0 0 720 120" fill="none" xmlns="http://www.w3.org/2000/svg" class="hero-flow-svg" aria-label="adk-fluent builder flow: Builder → IR → Native ADK → Deploy">
      <defs>
        <linearGradient id="hero-grad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#E65100"/>
          <stop offset="50%" stop-color="#F57C00"/>
          <stop offset="100%" stop-color="#FFB74D"/>
        </linearGradient>
        <marker id="arrow-hero" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 4 L0 8Z" fill="#F57C00"/>
        </marker>
      </defs>

      <!-- Builder node -->
      <g class="hero-node" style="--delay: 0s">
        <rect x="16" y="24" width="140" height="72" rx="14" fill="#E6510008" stroke="#E65100" stroke-width="1.5"/>
        <text x="86" y="53" text-anchor="middle" fill="#F57C00" font-family="'IBM Plex Sans', sans-serif" font-size="11" font-weight="700" letter-spacing="0.05em">FLUENT BUILDER</text>
        <text x="86" y="72" text-anchor="middle" fill="#9E9E9E" font-family="'IBM Plex Mono', monospace" font-size="10">Agent("name")</text>
        <text x="86" y="85" text-anchor="middle" fill="#757575" font-family="'IBM Plex Mono', monospace" font-size="9">.instruct().tool()</text>
      </g>

      <!-- Arrow 1 -->
      <line x1="166" y1="60" x2="220" y2="60" stroke="#F57C00" stroke-width="1.5" marker-end="url(#arrow-hero)" class="hero-arrow" style="--delay: 0.3s"/>
      <text x="193" y="52" text-anchor="middle" fill="#F57C00" font-family="'IBM Plex Mono', monospace" font-size="8" font-weight="600" class="hero-label" style="--delay: 0.3s">.build()</text>

      <!-- IR node -->
      <g class="hero-node" style="--delay: 0.5s">
        <rect x="228" y="30" width="110" height="60" rx="14" fill="#F57C0008" stroke="#F57C00" stroke-width="1.5"/>
        <text x="283" y="55" text-anchor="middle" fill="#FFB74D" font-family="'IBM Plex Sans', sans-serif" font-size="11" font-weight="700" letter-spacing="0.05em">IR TREE</text>
        <text x="283" y="72" text-anchor="middle" fill="#757575" font-family="'IBM Plex Sans', sans-serif" font-size="9">Validated &amp; Typed</text>
      </g>

      <!-- Arrow 2 -->
      <line x1="348" y1="60" x2="402" y2="60" stroke="#F57C00" stroke-width="1.5" marker-end="url(#arrow-hero)" class="hero-arrow" style="--delay: 0.8s"/>
      <text x="375" y="52" text-anchor="middle" fill="#F57C00" font-family="'IBM Plex Mono', monospace" font-size="8" font-weight="600" class="hero-label" style="--delay: 0.8s">compile</text>

      <!-- Native ADK node -->
      <g class="hero-node" style="--delay: 1s">
        <rect x="410" y="24" width="140" height="72" rx="14" fill="#10b98108" stroke="#10b981" stroke-width="1.5"/>
        <text x="480" y="53" text-anchor="middle" fill="#34d399" font-family="'IBM Plex Sans', sans-serif" font-size="11" font-weight="700" letter-spacing="0.05em">NATIVE ADK</text>
        <text x="480" y="72" text-anchor="middle" fill="#9E9E9E" font-family="'IBM Plex Mono', monospace" font-size="10">LlmAgent</text>
        <text x="480" y="85" text-anchor="middle" fill="#757575" font-family="'IBM Plex Mono', monospace" font-size="9">SequentialAgent</text>
      </g>

      <!-- Arrow 3 -->
      <line x1="560" y1="60" x2="614" y2="60" stroke="#10b981" stroke-width="1.5" marker-end="url(#arrow-hero)" class="hero-arrow" style="--delay: 1.3s"/>

      <!-- Deploy node -->
      <g class="hero-node" style="--delay: 1.5s">
        <rect x="622" y="30" width="82" height="60" rx="14" fill="#f59e0b06" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3"/>
        <text x="663" y="56" text-anchor="middle" fill="#fbbf24" font-family="'IBM Plex Sans', sans-serif" font-size="10" font-weight="700" letter-spacing="0.05em">DEPLOY</text>
        <text x="663" y="72" text-anchor="middle" fill="#757575" font-family="'IBM Plex Sans', sans-serif" font-size="8">web · run · cloud</text>
      </g>
    </svg>
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
      <span class="stat-number">74</span>
      <span class="stat-label">Recipes</span>
    </div>
    <div class="hero-stat">
      <span class="stat-number">100%</span>
      <span class="stat-label">Native ADK</span>
    </div>
  </div>
</div>
```

## Your first agent — three lines

::::{tab-set}
:::{tab-item} adk-fluent — Python
:sync: python

```python
from adk_fluent import Agent

answer = Agent("helper", "gemini-2.5-flash").ask("Say hello.")
```
:::
:::{tab-item} adk-fluent — TypeScript
:sync: ts

```ts
import { Agent } from "adk-fluent-ts";

const answer = await new Agent("helper", "gemini-2.5-flash").ask("Say hello.");
```
:::
:::{tab-item} Native ADK
```python
# See the "22 lines" tab below for the native equivalent of the pipeline sample.
```
:::
::::

That is the complete code. When you are ready to compose multiple agents in
parallel or in sequence, scroll to *Pipeline flex* below.

## Pipeline flex — when you need more

This is the same fluent API at scale. Skim it now, come back after the
getting-started page.

::::{tab-set}
:::{tab-item} adk-fluent — Python
:sync: python

```python
from adk_fluent import Agent, C

research = (
    Agent("analyzer", "gemini-2.5-flash").instruct("Decompose the query.").writes("plan")
    >> (Agent("web", "gemini-2.5-flash").instruct("Search web.").context(C.from_state("plan")).writes("web")
        | Agent("papers", "gemini-2.5-flash").instruct("Search papers.").context(C.from_state("plan")).writes("papers"))
    >> Agent("writer", "gemini-2.5-flash").instruct("Synthesize findings from {web} and {papers}.")
).build()
```
:::
:::{tab-item} adk-fluent — TypeScript
:sync: ts

```ts
import { Agent, C } from "adk-fluent-ts";

const research = new Agent("analyzer", "gemini-2.5-flash")
  .instruct("Decompose the query.")
  .writes("plan")
  .then(
    new Agent("web", "gemini-2.5-flash")
      .instruct("Search web.")
      .context(C.fromState("plan"))
      .writes("web")
      .parallel(
        new Agent("papers", "gemini-2.5-flash")
          .instruct("Search papers.")
          .context(C.fromState("plan"))
          .writes("papers"),
      ),
  )
  .then(
    new Agent("writer", "gemini-2.5-flash")
      .instruct("Synthesize findings from {web} and {papers}."),
  )
  .build();
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

Every `.build()` returns a real ADK object -- fully compatible with `adk web`, `adk run`, and `adk deploy`. **Click a tab** — your Python/TypeScript choice is remembered across every code sample on this site.

:::{note} Python + TypeScript monorepo
adk-fluent ships as two sibling packages from a single monorepo:

- **`adk-fluent`** ([PyPI](https://pypi.org/project/adk-fluent/)) — Python 3.11+, under [`python/`](https://github.com/vamsiramakrishnan/adk-fluent/tree/master/python). Reference implementation; this site is Python-first.
- **`adk-fluent-ts`** (npm, coming soon) — TypeScript, under [`ts/`](https://github.com/vamsiramakrishnan/adk-fluent/tree/master/ts). Mirrors the same builders and namespaces with method-chained operators. See the [TypeScript user guide](user-guide/typescript.md) and the [TS README](https://github.com/vamsiramakrishnan/adk-fluent/blob/master/ts/README.md).

Both packages are generated from the same `shared/manifest.json`, so parity is enforced at generation time. Throughout this site, conceptual guides apply to both languages; code samples with a `Python` / `TypeScript` tab selector stay in sync once you pick one.
:::

## What's New in v{{version}}

::::{grid} 1 1 2 3
:gutter: 3

:::{grid-item-card} A2UI (Agent-to-UI)
:link: user-guide/a2ui
:link-type: doc

Declarative UI composition with `UI.text()`, `UI.button()`, `UI.form()`. Expression operators `|` and `>>` for layouts. Data binding and validation built in.
:::

:::{grid-item-card} Skills & Harness
:link: user-guide/skills
:link-type: doc

Declarative agent packages with `SKILL.md`. Autonomous coding runtimes with `H` namespace. Five layers from tools to REPL.
:::

:::{grid-item-card} Guards (G Module)
:link: user-guide/guards
:link-type: doc

Output validation with `G.pii()`, `G.toxicity()`, `G.length()`, `G.schema()`. Compose with `|` pipe operator.
:::

:::{grid-item-card} Lazy Imports
Zero-cost `import adk_fluent` — loads 1 module instead of ~1,468. ADK dependencies deferred to `.build()` time.
:::

:::{grid-item-card} Eval Suite (E Module)
:link: user-guide/evaluation
:link-type: doc

Fluent evaluation with `E.case()`, `E.criterion()`, `E.persona()`. `LLMJudge` for LLM-powered evaluation.
:::

:::{grid-item-card} Version Dropdown
Docs now include a version switcher. Browse docs for any release, with `/latest/` always pointing to the most recent build.
:::

::::

```{button-link} changelog.html
:color: primary
:outline:
:expand:

Full Changelog
```

## Why adk-fluent?

```{raw} html
<div class="feature-grid">

  <div class="feature-card">
    <div class="feature-header">
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <rect x="2" y="2" width="28" height="28" rx="6" stroke="#E65100" stroke-width="1.5" fill="#E6510010"/>
        <path d="M10 10 h4 a2 2 0 0 1 2 2 v2 h-4 a2 2 0 0 1-2-2z" fill="#E65100" opacity="0.8"/>
        <path d="M12 14 h4 a2 2 0 0 1 2 2 v2 h-4 a2 2 0 0 1-2-2z" fill="#F57C00" opacity="0.5"/>
        <rect x="19" y="10" width="5" height="1.5" rx="0.75" fill="#FFB74D" opacity="0.6"/>
        <rect x="19" y="13" width="3" height="1.5" rx="0.75" fill="#FFB74D" opacity="0.4"/>
        <rect x="19" y="16" width="4" height="1.5" rx="0.75" fill="#FFB74D" opacity="0.3"/>
        <rect x="8" y="20" width="16" height="1" rx="0.5" fill="#E0E0E0" opacity="0.3"/>
        <rect x="8" y="22.5" width="12" height="1" rx="0.5" fill="#E0E0E0" opacity="0.2"/>
      </svg>
      <h3>135 Builders, Full Autocomplete</h3>
    </div>
    <p>Every builder ships with <code>.pyi</code> stubs. Type <code>Agent("name").</code> and your IDE shows all methods with type hints, parameter docs, and ADK mapping.</p>
  </div>

  <div class="feature-card">
    <div class="feature-header">
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <circle cx="8" cy="16" r="5" stroke="#E65100" stroke-width="1.5" fill="#E6510010"/>
        <circle cx="24" cy="10" r="4" stroke="#F57C00" stroke-width="1.5" fill="#F57C0010"/>
        <circle cx="24" cy="22" r="4" stroke="#FFB74D" stroke-width="1.5" fill="#FFB74D10"/>
        <line x1="13" y1="14" x2="20" y2="11" stroke="#F57C00" stroke-width="1.2"/>
        <line x1="13" y1="18" x2="20" y2="21" stroke="#FFB74D" stroke-width="1.2"/>
        <text x="8" y="18.5" text-anchor="middle" fill="#E65100" font-size="6" font-weight="700" font-family="monospace">&gt;&gt;</text>
        <text x="24" y="12.5" text-anchor="middle" fill="#F57C00" font-size="5" font-weight="700" font-family="monospace">|</text>
        <text x="24" y="24.5" text-anchor="middle" fill="#FFB74D" font-size="5" font-weight="700" font-family="monospace">*</text>
      </svg>
      <h3>Expression Algebra</h3>
    </div>
    <p><code>&gt;&gt;</code> sequential, <code>|</code> parallel, <code>*</code> loops, <code>@</code> typed output, <code>//</code> fallback. Compose any topology in a single expression.</p>
  </div>

  <div class="feature-card">
    <div class="feature-header">
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
        <rect x="4" y="6" width="24" height="20" rx="4" stroke="#E65100" stroke-width="1.5" fill="#E6510010"/>
        <path d="M10 14 l3 3 l7-7" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="24" cy="8" r="4" fill="#F57C00"/>
        <path d="M22.5 8 l1.5 1.5 l2.5-2.5" stroke="white" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
      </svg>
      <h3>Always in Sync</h3>
    </div>
    <p>Builders are auto-generated from installed ADK. When ADK updates, regenerate and get new features immediately. Zero maintenance.</p>
  </div>

</div>
```

## Three Pathways

Once you know the builder basics, adk-fluent splits into three distinct development pathways -- a **fork in the road** that matches how you think about agent building.

```{raw} html
<div class="pathway-grid">

  <div class="pathway-card pathway-card--pipeline">
    <div class="pathway-header">
      <div class="pathway-icon">&gt;&gt;</div>
      <h3>Pipeline Path</h3>
    </div>
    <p class="pathway-subtitle">Python-first builders</p>
    <p class="pathway-desc">Full Python control with expression operators (<code>&gt;&gt;</code> <code>|</code> <code>*</code> <code>@</code> <code>//</code>) and 9 namespace modules. Build any topology with type-checked, IDE-friendly builders.</p>
    <code class="pathway-code">Agent("a") >> Agent("b") | Agent("c")</code>
    <p class="pathway-best-for"><strong>Best for:</strong> Custom workflows, complex routing, dynamic topologies</p>
    <a href="user-guide/expression-language.html" class="pathway-link">Expression Language &rarr;</a>
  </div>

  <div class="pathway-card pathway-card--skills">
    <div class="pathway-header">
      <div class="pathway-icon">S</div>
      <h3>Skills Path</h3>
    </div>
    <p class="pathway-subtitle">Declarative agent packages</p>
    <p class="pathway-desc">YAML + Markdown &rarr; executable agent graphs. Domain experts write prompts and topology. One file is docs, coding-agent context, and a runnable pipeline.</p>
    <code class="pathway-code">Skill("research/") >> Skill("writing/")</code>
    <p class="pathway-best-for"><strong>Best for:</strong> Stable topologies, reusable libraries, non-Python teams</p>
    <a href="user-guide/skills.html" class="pathway-link">Skills Guide &rarr;</a>
  </div>

  <div class="pathway-card pathway-card--harness">
    <div class="pathway-header">
      <div class="pathway-icon">H</div>
      <h3>Harness Path</h3>
    </div>
    <p class="pathway-subtitle">Autonomous coding runtimes</p>
    <p class="pathway-desc">Build Claude-Code-class agents with the H namespace. Five layers: intelligence, tools, safety, observability, runtime. Permissions, sandboxing, token budgets.</p>
    <code class="pathway-code">H.workspace() + H.web() + H.git()</code>
    <p class="pathway-best-for"><strong>Best for:</strong> Autonomous agents, file/shell access, multi-turn runtimes</p>
    <a href="user-guide/harness.html" class="pathway-link">Harness Guide &rarr;</a>
  </div>

</div>
```

**All three compose together** -- a harness loads skills for domain expertise, skills wire agents as pipelines internally, and pipelines use the full expression algebra. See the [Decision Guide](decision-guide.md) for a flowchart.

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
74 recipes from fundamentals to hero workflows.
```
````

## Common Starting Points

**"I'm building agents from scratch"** -- Start with [Getting Started](getting-started.md), then [choose your path](#three-pathways).

**"I want full Python control with operators"** -- Take the [Pipeline Path](user-guide/expression-language.md). `>>` `|` `*` `@` `//` compose any topology.

**"I want declarative, reusable agent packages"** -- Take the [Skills Path](user-guide/skills.md). YAML + Markdown = docs + runtime.

**"I want an autonomous coding agent"** -- Take the [Harness Path](user-guide/harness.md). Five layers from tools to REPL.

**"I have native ADK code and want to simplify it"** -- Start with the [Migration Guide](generated/migration/from-native-adk.md), then browse the [Cookbook](cookbook/index.md) for your pattern.

**"I need a specific pattern (routing, loops, parallel)"** -- Jump to [Patterns](user-guide/patterns.md) or search the [Cookbook by use case](generated/cookbook/recipes-by-use-case.md).

**"I want my AI coding agent to know adk-fluent"** -- Set up [Editor & AI Agent Setup](editor-setup/index.md) for rules files, skills, and MCP servers.

**"I'm using TypeScript, not Python"** -- Start with the [TypeScript user guide](user-guide/typescript.md). Every conceptual chapter in this site applies to both languages; code samples have a synced `Python` / `TypeScript` tab.

---

[PyPI](https://pypi.org/project/adk-fluent/) · [GitHub](https://github.com/vamsiramakrishnan/adk-fluent) · [Changelog](changelog.md) · [Contributing](contributing/index.md)

```{toctree}
---
maxdepth: 2
caption: Getting Started
---
getting-started
user-guide/typescript
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
caption: Project
---
changelog
```

```{toctree}
---
maxdepth: 1
caption: Research
hidden: true
---
research/skill-based-agents
research/missing-verbs-and-idioms
research/new-structural-types
```
