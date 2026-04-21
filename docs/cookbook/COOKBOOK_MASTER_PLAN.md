# Cookbook Master Plan: From Dictionary to Curriculum

> This document defines the curation strategy for the adk-fluent cookbook.
> It separates "feature snippets" from "hero workflows" and establishes
> a progressive-disclosure learning path.

---

## Phase 1: Taxonomy — Signal vs. Noise

### Demoted to "Snippets" (API Basics Cheat Sheet)

These 28 recipes demonstrate a single method or concept. They belong in
a condensed **Basics & Primitives Reference** section — not as standalone
pages competing for attention alongside real workflows.

| #  | File                        | Why it's a snippet                          |
|----|-----------------------------|--------------------------------------------|
| 01 | `simple_agent`              | Single `.build()` call                     |
| 02 | `agent_with_tools`          | Single `.tool()` method                    |
| 03 | `callbacks`                 | Single `before_model`/`after_model`        |
| 08 | `one_shot_ask`              | Single `.ask()` call                       |
| 09 | `streaming`                 | Single `.stream()` call                    |
| 10 | `cloning`                   | Single `.clone()` / `.with_()`             |
| 11 | `inline_testing`            | Single `.test()` call                      |
| 13 | `interactive_session`       | Single `.session()` call                   |
| 14 | `dynamic_forwarding`        | Single `__getattr__` validation            |
| 17 | `route_branching`           | Single `Route()` demo                      |
| 18 | `dict_routing`              | Single dict `>>` shorthand                 |
| 19 | `conditional_gating`        | Single `proceed_if()`                      |
| 20 | `loop_until`                | Single `.loop_until()`                     |
| 21 | `statekey`                  | Single `StateKey` usage                    |
| 22 | `presets`                   | Single `Preset()` usage                    |
| 23 | `with_variants`             | Single `.with_()` usage                    |
| 24 | `agent_decorator`           | Single `@agent` decorator                  |
| 26 | `serialization`             | Single `.to_dict()` / `.to_yaml()`         |
| 27 | `agent_tool_pattern`        | Single `.delegate_to()` usage               |
| 31 | `typed_output`              | Single `@` operator                        |
| 37 | `mock_testing`              | Single `.mock()` usage                     |
| 38 | `loop_while`                | Single `.loop_while()` usage               |
| 39 | `map_over`                  | Single `map_over()` usage                  |
| 40 | `timeout`                   | Single `.timeout()` usage                  |
| 41 | `gate_approval`             | Single `gate()` usage                      |
| 42 | `race`                      | Single `race()` usage                      |
| 44 | `ir_and_backends`           | Single `.to_ir()` / `.to_app()`            |
| 48 | `visualization`             | Single `.to_mermaid()`                     |
| 51 | `visibility_policies`       | Single visibility flag demo                |
| 54 | `transfer_control`          | Single `.isolate()` demo                   |

### Elevated to "Hero Workflows" (7 recipes)

These recipes demonstrate **module interplay** — multiple adk-fluent
subsystems (agents, operators, state, context, routing, guards, middleware)
working together to solve a real problem. They are the showcase.

| #  | Hero Workflow                     | Modules in play                                                       |
|----|-----------------------------------|-----------------------------------------------------------------------|
| 55 | **Deep Research Agent**           | `>>`, `\|`, `*until`, `@`, `S.*`, `C.*` — 6+ modules                  |
| 56 | **Customer Support Triage**       | `S.capture`, `C.none`, `Route`, `gate`, `>>` — 5 modules              |
| 57 | **Code Review Agent**             | `>>`, `\|`, `@`, `tap`, `proceed_if` — 5 modules                      |
| 28 | **Investment Analysis Pipeline**  | `Route`, `\|`, `>>`, `loop_until`, `proceed_if`, `Preset` — 6 modules |
| 43 | **E-Commerce Order Pipeline**     | `tap`, `expect`, `gate`, `Route`, `S.*`, `C.*`, `>>` — 7 modules      |
| 58 | **Multi-Tool Task Agent**         | `.tool()`, `.guard()`, `.inject()`, `.context()`, `>>` — 5 modules     |
| 59 | **Dispatch & Join Pipeline**      | `dispatch`, `join`, `>>`, callbacks, progress — 4 modules              |

### "Bridge" Recipes (keep as intermediate examples)

These 14 recipes combine 2-3 features and serve as stepping stones
between basics and hero workflows:

| #  | Bridge Recipe                  | Bridge between                          |
|----|-------------------------------|-----------------------------------------|
| 04 | Sequential Pipeline           | Basics → `>>` operator                  |
| 05 | Parallel FanOut                | Basics → `\|` operator                   |
| 06 | Loop Agent                    | Basics → `*` operator                   |
| 07 | Team Coordinator              | Basics → `sub_agents`                   |
| 12 | Guards                        | Basics → `G` module                     |
| 15 | Production Runtime            | Basics → Middleware                     |
| 16 | Operator Composition          | Operators → Combined expressions        |
| 25 | Validate & Explain            | Basics → Introspection                  |
| 29 | Function Steps                | `>>` → Functions as pipeline steps      |
| 30 | Until Operator                | Loops → Conditional loops               |
| 32 | Fallback Operator             | `>>` → `//` fallback chains             |
| 33 | State Transforms              | State → `S` module                      |
| 34 | Full Algebra                  | Operators → All 4 in one expression     |
| 49 | Context Engineering           | Prompts → `C` module                    |

### Module Deep-Dives (keep as reference)

These 10 recipes are comprehensive module showcases, valuable
as reference material:

| #  | Module Reference               | Module                                  |
|----|-------------------------------|-----------------------------------------|
| 35 | Tap Observation               | `tap` primitive                         |
| 36 | Expect Assertions             | `expect` primitive                      |
| 45 | Middleware                    | `M` module basics                       |
| 46 | Contracts & Testing           | Contract checking                       |
| 47 | Dependency Injection          | `.inject()` pattern                     |
| 50 | Capture & Route               | `S.capture` + `Route` combo             |
| 52 | Contract Checking             | `check_contracts()` API                 |
| 53 | Structured Schemas            | `@` + `.returns()` patterns             |
| 60 | Stream Runner                 | `StreamRunner` + `Source`               |
| 61-67 | Module compositions        | `M`, `T`, `G`, topology, middleware schemas |

---

## Phase 2: The "World-Class" Recipe Anatomy

Every Hero recipe page follows this exact structure:

```
# [Title] — [One-line hook]

## The Real-World Problem
2-3 sentences describing a business scenario a developer will recognize.
No abstract "this demonstrates X" — concrete pain that makes them nod.

## The Fluent Solution
The complete adk-fluent code — no ellipsis, no "imagine this" —
copy-pasteable and runnable.

## The Interplay Breakdown
A punchy explanation of WHY these modules were combined:
- Why Route instead of LLM routing? (cost + determinism)
- Why C.none() on the classifier? (prevent history leaking)
- Why gate() at the end? (human escalation)

## Pipeline Topology (Mermaid)
Auto-generated or hand-drawn topology diagram.

## Framework Comparison
Brief comparison showing line count vs native ADK / LangGraph.
```

---

## Phase 3: The "Zero to Symphony" Learning Path

### Proposed Navigation Structure

```
docs/
├── index.md                          # Landing page
├── getting-started.md                # Install + first agent
│
├── user-guide/                       # Conceptual docs (existing)
│   ├── index.md
│   ├── builders.md
│   ├── expression-language.md
│   ├── state-transforms.md
│   ├── context-engineering.md
│   ├── middleware.md
│   ├── guards.md
│   └── ...
│
├── generated/
│   ├── api/                          # API reference (existing)
│   │
│   └── cookbook/
│       ├── index.md                  # NEW: Narrative landing page
│       │
│       ├── basics/                   # Tier 1: Fundamentals
│       │   └── (snippets grouped into cheat-sheet pages)
│       │
│       ├── building-blocks/          # Tier 2: Intermediate patterns
│       │   └── (bridge recipes — 2-3 features each)
│       │
│       ├── hero-workflows/           # Tier 3: The Showcases
│       │   ├── deep-research.md
│       │   ├── customer-support-triage.md
│       │   ├── code-review-agent.md
│       │   ├── investment-pipeline.md
│       │   ├── ecommerce-orders.md
│       │   ├── multi-tool-agent.md
│       │   └── dispatch-join-pipeline.md
│       │
│       ├── module-reference/         # Tier 4: Module deep-dives
│       │   └── (S, C, M, T, G, E module showcases)
│       │
│       └── recipes-by-use-case.md    # Cross-reference index
```

### The Learning Path Flow

```
1. FUNDAMENTALS          → "I can create an agent"
   01-03, 08-11            Agent, tools, callbacks, .ask(), .test()

2. THE FLUENT API         → "I understand the operators"
   04-06, 16-20            >>, |, *, Route, loop_until, proceed_if

3. BUILDING BLOCKS        → "I can combine 2-3 features"
   29, 30, 32-34, 49       Functions as steps, fallback, state, context

4. HERO WORKFLOWS         → "I see the symphony"
   55, 56, 57, 28, 43,     Deep research, support triage, code review,
   58, 59                   investment analysis, e-commerce, multi-tool,
                            dispatch/join

5. ENTERPRISE PATTERNS    → "I can ship this to production"
   15, 45, 47, 60-67       Middleware, DI, streaming, module compositions
```

---

## The Gold Standard Recipe

See `hero-workflows/deep-research.md` for the fully rewritten
Hero recipe using the new anatomy format.
