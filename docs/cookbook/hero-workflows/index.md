# Hero Workflows

These 7 recipes are the showcase of adk-fluent. Each demonstrates how
multiple modules — agents, operators, state transforms, context engineering,
routing, guards, middleware — **orchestrate together** to solve a real problem.

Unlike the [basic recipes](../../generated/cookbook/index.md), which demonstrate
individual features in isolation, hero workflows show the *interplay*.

## Every Hero Recipe Follows This Anatomy

1. **The Real-World Problem** — A business scenario you'll recognize. Not
   "this demonstrates X" but concrete pain that makes you nod.

2. **The Fluent Solution** — Complete, copy-pasteable adk-fluent code.
   No ellipsis, no "imagine this."

3. **The Interplay Breakdown** — Why these modules were combined. Why `Route`
   instead of LLM routing? Why `C.none()` on the classifier? Why `gate()` at
   the end?

---

## The Workflows

```{toctree}
---
maxdepth: 1
---
deep-research
customer-support-triage
code-review-agent
investment-pipeline
ecommerce-orders
multi-tool-agent
dispatch-join-pipeline
```

---

## Module Coverage

Between these 7 workflows, every major adk-fluent module is demonstrated:

| Module | Used in |
|--------|---------|
| `>>` sequential | All 7 |
| `\|` parallel | Deep Research, Code Review, Investment |
| `* until()` loop | Deep Research, Investment |
| `@` typed output | Deep Research, Code Review |
| `Route` branching | Support Triage, Investment, E-Commerce |
| `S.*` state transforms | Support Triage, E-Commerce |
| `C.*` context engineering | Deep Research, Support Triage, Multi-Tool |
| `gate()` human-in-the-loop | Support Triage, E-Commerce |
| `tap()` observation | Code Review, E-Commerce |
| `expect()` assertions | E-Commerce |
| `proceed_if()` gating | Code Review, Investment |
| `.tool()` / `.inject()` | Multi-Tool |
| `.guard()` safety | Multi-Tool |
| `dispatch()` / `join()` | Dispatch & Join |
| `Preset` shared config | Investment |
