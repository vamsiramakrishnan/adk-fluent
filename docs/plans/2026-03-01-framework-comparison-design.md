# Framework Comparison & Cookbook Enhancement Design

## Problem

Developers evaluating adk-fluent have no frame of reference for how it compares to LangGraph, CrewAI, or native ADK. The 66 cookbook examples use synthetic scenarios. New users cannot answer: "Why should I use this instead of X?"

## Scope

Three deliverables, all additive:

1. **"Why adk-fluent" README section** -- side-by-side code comparisons in `README.template.md`
1. **Comparison doc** -- detailed breakdown at `docs/user-guide/comparison.md`
1. **Cookbook docstring enhancement** -- real-world use-case framing in ~15 key examples

## Changes

### 1. "Why adk-fluent" README Section

Insert after Quick Start / Zero to Running (before Expression Language, ~line 206 of `README.template.md`). Shows 3 real-world patterns with side-by-side code:

**Pattern 1: Document Processing Pipeline (Sequential)**

LangGraph version (~35 lines): StateGraph, TypedDict, node functions, add_node, add_edge, compile.

adk-fluent version (1 expression):

```python
pipeline = extractor >> analyst >> summarizer
```

**Pattern 2: Multi-Source Research (Parallel + Loop)**

LangGraph version (~55 lines): Conditional edges, branching logic, custom state merging.

adk-fluent version (1 expression):

```python
research = analyzer >> (web | papers | news) >> synthesizer >> (reviewer >> reviser) * until(quality_ok)
```

**Pattern 3: Customer Support Triage (Routing)**

LangGraph version (~50 lines): Conditional edges, routing functions, StateGraph wiring.

adk-fluent version:

```python
support = capture >> classifier >> Route("intent").eq("billing", billing).eq("tech", tech).otherwise(general)
```

Each pattern shows: problem statement, LangGraph code (simplified pseudocode), adk-fluent code, and line-count comparison. The README shows only the contrast -- not runnable LangGraph code.

Link to full comparison doc and relevant cookbook examples.

### 2. Comparison Doc (`docs/user-guide/comparison.md`)

Detailed page covering:

- **Feature matrix**: LangGraph vs CrewAI vs native ADK vs adk-fluent on 8 dimensions (LOC, testing, typing, visualization, streaming, state management, routing, composability)
- **3 pattern deep-dives** (same as README but with full code for all frameworks)
- **When to use each**: honest guidance on when LangGraph or CrewAI is the better choice
- **Migration guide**: quick tips for users coming from each framework

### 3. Cookbook Docstring Enhancement

Enhance docstrings on ~15 key real-world examples with structured format:

```python
"""Customer Support Triage -- ADK-Samples Inspired Multi-Tier Support

Real-world use case: Multi-tier IT helpdesk that classifies incoming tickets
by urgency and routes them to the appropriate specialist team.

In other frameworks: LangGraph requires a StateGraph with conditional_edges
for routing (~50 lines). CrewAI requires separate Agent + Task objects for
each handler (~40 lines). adk-fluent uses Route() with 8 lines of
composition.

Pipeline topology:
    S.capture("customer_message")
        >> intent_classifier
        >> Route("intent")
            ├─ "billing"   -> billing_specialist
            └─ otherwise   -> general_support
"""
```

The format adds two optional blocks to existing docstrings:

- `Real-world use case:` -- one-sentence business context
- `In other frameworks:` -- brief comparison with line counts

Target examples (grouped by comparison pattern):

**Sequential pipelines** (4): 04, 28, 15, 09
**Parallel fan-out** (3): 05, 34, 55
**Routing** (3): 56, 50, 17
**Loops** (2): 06, 30
**Composite** (3): 49, 53, 57

## Files Changed

| File                            | Action                                         |
| ------------------------------- | ---------------------------------------------- |
| `README.template.md`            | Edit: add "Why adk-fluent" section (~60 lines) |
| `docs/user-guide/comparison.md` | Create: framework comparison page              |
| `examples/cookbook/*.py`        | Edit: enhance ~15 docstrings                   |
| `README.md`                     | Regenerate from template                       |

## Out of Scope

- Runnable LangGraph/CrewAI code in the repo (no new dependencies)
- Benchmark comparisons (already covered in Performance section)
- Video or interactive demos
