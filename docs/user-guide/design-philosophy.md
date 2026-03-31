# Design Philosophy

:::{admonition} At a Glance
:class: tip

- Why fluent builders? Why immutable operators? Why auto-generated code?
- The "why" behind the "what" --- understanding these principles helps you use adk-fluent effectively
:::

## Core Principles

### 1. Builders are configuration, not abstraction

adk-fluent doesn't abstract ADK --- it makes ADK **easier to configure**. Every `.build()` returns an identical native ADK object. There is no adk-fluent runtime, no custom execution engine, no behavior changes. If you can do it with ADK, you can do it with adk-fluent. If adk-fluent can't express it, use `.native()` as an escape hatch.

### 2. Compile-time over runtime

Catch errors at `.build()` time, not when an LLM call fails in production. Typo detection, contract verification, and data flow analysis all happen before any tokens are spent. The IR tree is a static artifact you can inspect, test, and validate --- cheaply and deterministically.

### 3. Immutable operators

All expression operators (`>>`, `|`, `*`, `@`, `//`) produce **new** objects. Sub-expressions are safely reusable:

```python
review = agent_a >> agent_b    # Define once
pipeline_1 = review >> agent_c  # Reuse freely
pipeline_2 = review >> agent_d  # No interference
```

This follows the same principle as functional data structures: composition without fear of mutation.

### 4. Orthogonal concerns

The five data flow concerns (Context, Input, Output, Storage, Contract) are independent. Setting `.writes("intent")` doesn't affect what the agent sees. Setting `.context(C.none())` doesn't affect where the agent stores its output. This orthogonality makes pipelines predictable and debuggable.

### 5. Auto-generated, always in sync

The 132 builders are auto-generated from the installed ADK version by a codegen pipeline (scan → seed → generate). This means:

- Every ADK class has a corresponding builder
- Every ADK field is accessible (via explicit methods or `__getattr__` forwarding)
- Upgrades to ADK automatically surface new builders and fields

You never wait for adk-fluent to "support" a new ADK feature.

### 6. Progressive disclosure

The API has three complexity levels:

| Level | API | Example |
|-------|-----|---------|
| **Simple** | `Agent("name", "model").instruct("...").build()` | 1-3 lines |
| **Compositional** | `a >> b \| c * 3` | Operators |
| **Advanced** | `.context(C.window(3) + C.from_state("k"))` | Module composition |

You never need the advanced features to get started. Each level builds on the previous one.

---

## Why Fluent Builders?

ADK's `LlmAgent` takes 15+ keyword arguments. In a pipeline with 5 agents, that's 75+ kwargs to manage. Fluent builders solve this with:

1. **Autocomplete** --- IDE shows available methods
2. **Typo detection** --- misspelled fields caught at definition time
3. **Chainability** --- each method returns `self`, reads naturally
4. **Discoverability** --- `.explain()`, `.data_flow()`, `.llm_anatomy()` for introspection

## Why Expression Operators?

The `>>` and `|` syntax isn't sugar for its own sake. It encodes **topology** --- the shape of your agent graph. When you read `a >> b | c`, you immediately see: "a runs first, then b and c in parallel." The equivalent native ADK code (nested `SequentialAgent` and `ParallelAgent` constructors) obscures this shape in boilerplate.

## Why Modules (S, C, P, A, M, T, E, G)?

Each module owns one orthogonal concern. They compose independently:

- `S` transforms state between agents
- `C` controls what agents see
- `P` structures the prompt
- `M` adds pipeline-wide middleware

This separation means you can change your context strategy (`C`) without touching your state flow (`S`) or your prompt structure (`P`). Concerns don't leak across boundaries.

## Why Auto-Generation?

Hand-maintaining 132 builders would be:

1. **Error-prone** --- miss a field, introduce a typo
2. **Always stale** --- ADK updates faster than manual wrappers
3. **Incomplete** --- easy to skip edge cases

Auto-generation from `manifest.json` ensures every ADK class, field, and type annotation is covered. The codegen pipeline is the single source of truth.

---

:::{seealso}
- {doc}`architecture-and-concepts` --- system architecture
- {doc}`../contributing/codegen-pipeline` --- how auto-generation works
- {doc}`concept-map` --- visual map of all concepts
:::
