# User Guide

This guide covers every aspect of adk-fluent in depth. Read sequentially for
a complete understanding, or jump to the topic you need.

## Foundations

Start here if you're new to adk-fluent.

| Chapter | What you'll learn |
|---|---|
| [Architecture & Concepts](architecture-and-concepts.md) | How builders wrap ADK, the IR tree, and the compilation pipeline |
| [Best Practices](best-practices.md) | Opinionated guidance on when to use what |
| [Framework Comparison](comparison.md) | Side-by-side with LangGraph, CrewAI, and native ADK |

## Building Agents

The core of the library.

| Chapter | What you'll learn |
|---|---|
| [Builders](builders.md) | Constructor args, method chaining, `.build()`, typo detection, `.explain()`, serialization |
| [Expression Language](expression-language.md) | All 9 operators (`>>`, `\|`, `*`, `@`, `//`, `>>` with functions, `Route`, `race`, `dispatch`) |
| [Data Flow](data-flow.md) | `.writes()`, `.reads()`, `{key}` templates, state propagation between agents |
| [Prompts](prompts.md) | The P module: `P.role()`, `P.task()`, `P.constraint()`, section ordering, composition |
| [Execution](execution.md) | `.ask()`, `.stream()`, `.session()`, `.map()`, `.events()` |

## Advanced Capabilities

Where adk-fluent's power shows.

| Chapter | What you'll learn |
|---|---|
| [Callbacks](callbacks.md) | `.before_agent()`, `.after_model()`, `.guard()`, error callbacks |
| [Presets](presets.md) | Reusable configuration bundles with `.use()` |
| [State Transforms](state-transforms.md) | The S module: `S.pick()`, `S.merge()`, `S.guard()`, `S.branch()`, composition |
| [Structured Data](structured-data.md) | `@ Schema`, `.returns()`, `.produces()`, `.consumes()`, contract checking |
| [Context Engineering](context-engineering.md) | The C module: `C.none()`, `C.from_state()`, `C.window()`, token budgets |
| [Patterns](patterns.md) | `review_loop`, `map_reduce`, `cascade`, `fan_out_merge`, `conditional`, `supervised` |

## Infrastructure

Production concerns.

| Chapter | What you'll learn |
|---|---|
| [Visibility](visibility.md) | `.show()`, `.hide()`, `.transparent()`, topology control |
| [Transfer Control](transfer-control.md) | `.isolate()`, `.stay()`, `.no_peers()` |
| [Memory](memory.md) | `.memory()`, `.memory_auto_save()`, persistent agent memory |
| [IR & Backends](ir-and-backends.md) | `.to_ir()`, compilation, backend abstraction |
| [Middleware](middleware.md) | The M module: `M.retry()`, `M.log()`, `M.cost()`, `M.circuit_breaker()`, composition |
| [Guards](guards.md) | The G module: `G.pii()`, `G.toxicity()`, `G.schema()`, input/output validation |
| [Evaluation](evaluation.md) | The E module: `E.case()`, `E.criterion()`, eval suites, comparison reports |
| [Testing](testing.md) | `.mock()`, `.test()`, `check_contracts()`, `AgentHarness`, pytest integration |

## Reference

| Resource | Description |
|---|---|
| [Error Reference](error-reference.md) | Every error with cause and fix-it code |
| [ADK Samples](adk-samples/index.md) | Official ADK samples ported to adk-fluent |
| [Decision Guide](../decision-guide.md) | "Which pattern should I use?" flowchart |

```{toctree}
---
maxdepth: 2
hidden: true
---
architecture-and-concepts
best-practices
comparison
builders
expression-language
data-flow
prompts
execution
callbacks
presets
state-transforms
structured-data
context-engineering
patterns
visibility
transfer-control
memory
ir-and-backends
middleware
guards
evaluation
testing
error-reference
adk-samples/index
```

## Interactive References

Standalone HTML pages -- open in browser for the full interactive experience:

- [Module Lifecycle Reference](/module-lifecycle-reference.html) -- Where each module (S, C, P, A, M, T, E, G) fires during execution. Swim-lane timeline, interaction grid, step-through walkthrough, and auto-generated sequence diagrams
- [P*C*S Visual Reference](/pcs-visual-reference.html) -- Pipeline, Context, and State module reference
- [Operator Algebra Reference](/operator-algebra-reference.html) -- All 9 operators with SVG diagrams and composition rules
