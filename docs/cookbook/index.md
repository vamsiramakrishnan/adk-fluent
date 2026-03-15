# Cookbook — Zero to Symphony

The adk-fluent cookbook is organized as a **learning path**, not a dictionary.
Start with fundamentals, graduate to the fluent API, then see how modules
orchestrate together in real-world "hero" workflows.

---

## The Learning Path

````{grid} 1 2 2 2
---
gutter: 3
---

```{grid-item-card} 1. Fundamentals
:link: ../generated/cookbook/index
:link-type: doc

Create agents, attach tools, register callbacks, execute with `.ask()`.
The building blocks everything else depends on.

**Recipes:** 01-11
```

```{grid-item-card} 2. The Fluent Operators
:link: ../generated/cookbook/16_operator_composition
:link-type: doc

Master `>>` (sequence), `|` (parallel), `*` (loop), `@` (typed output),
`//` (fallback), and `Route` (deterministic branching).

**Recipes:** 04-06, 16-20, 29-34
```

```{grid-item-card} 3. Hero Workflows
:link: hero-workflows/index
:link-type: doc

The showcase. Real-world systems combining 5-7 modules in one pipeline.
Deep research, customer support, code review, investment analysis.

**7 hero recipes**
```

```{grid-item-card} 4. Enterprise Patterns
:link: ../generated/cookbook/15_production_runtime
:link-type: doc

Middleware, dependency injection, streaming, guards, contracts.
Everything between "it works" and "it ships."

**Recipes:** 15, 45-47, 60-67
```
````

---

## Hero Workflows — The Showcases

These 7 recipes demonstrate **module interplay** — how agents, operators, state
transforms, context engineering, routing, guards, and middleware work together
to solve real problems. Each follows a strict anatomy: the business problem,
the fluent solution, and an interplay breakdown explaining *why* the modules
were combined this way.

```{toctree}
---
maxdepth: 1
caption: Hero Workflows
---
hero-workflows/index
hero-workflows/deep-research
hero-workflows/customer-support-triage
hero-workflows/code-review-agent
hero-workflows/investment-pipeline
hero-workflows/ecommerce-orders
hero-workflows/multi-tool-agent
hero-workflows/dispatch-join-pipeline
```

### At a Glance

| Hero Workflow | Real-World Problem | Modules in Play |
|---|---|---|
| [Deep Research Agent](hero-workflows/deep-research.md) | Multi-source research with quality loop | `>>`, `\|`, `* until`, `@`, `S.*`, `C.*` |
| [Customer Support Triage](hero-workflows/customer-support-triage.md) | Ticket routing with escalation | `S.capture`, `C.none`, `Route`, `gate` |
| [Code Review Agent](hero-workflows/code-review-agent.md) | Parallel analysis with structured verdicts | `>>`, `\|`, `@`, `tap`, `proceed_if` |
| [Investment Pipeline](hero-workflows/investment-pipeline.md) | Asset-class routing with quality review | `Route`, `\|`, `>>`, `loop_until`, `Preset` |
| [E-Commerce Orders](hero-workflows/ecommerce-orders.md) | Order routing with fraud detection | `tap`, `expect`, `gate`, `Route`, `S.*` |
| [Multi-Tool Agent](hero-workflows/multi-tool-agent.md) | Tools with DI and safety guards | `.tool()`, `.guard()`, `.inject()` |
| [Dispatch & Join](hero-workflows/dispatch-join-pipeline.md) | Fire-and-continue background tasks | `dispatch`, `join`, callbacks |

---

## All Recipes

For the complete flat listing of all 68 recipes with side-by-side native ADK
comparisons, see the [auto-generated cookbook](../generated/cookbook/index.md).

For recipes organized by use case (support, e-commerce, research, etc.), see
[Recipes by Use Case](../generated/cookbook/recipes-by-use-case.md).
