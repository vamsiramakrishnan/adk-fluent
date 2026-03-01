# Framework Comparison Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add framework comparison content to README, a dedicated comparison doc, and enhance cookbook docstrings with real-world use-case framing.

**Architecture:** Three parallel deliverables -- a README section with side-by-side code, a detailed comparison doc page, and enhanced docstrings in 15 cookbook examples. All changes are documentation/content only, no code changes.

**Tech Stack:** Markdown, Python docstrings, `scripts/readme_generator.py` for README regeneration.

______________________________________________________________________

### Task 1: Add "Why adk-fluent" section to README template

**Files:**

- Modify: `README.template.md:17-28` (ToC update)
- Modify: `README.template.md:205-206` (insert new section before Expression Language)

**Step 1: Update Table of Contents**

Add `- [Why adk-fluent](#why-adk-fluent)` after `[Zero to Running]` and before `[Expression Language]` in the ToC at line 22.

**Step 2: Insert "Why adk-fluent" section**

Insert the following section between "Zero to Running" (ends line 205) and "Expression Language" (starts line 206):

````markdown
## Why adk-fluent

Real patterns. Real reduction. Every adk-fluent expression compiles to the same native ADK objects you'd build by hand.

### Document Processing Pipeline

A contract review system that extracts terms, analyzes risks, and summarizes findings.

**LangGraph** (~35 lines):

```python
class State(TypedDict):
    document: str
    terms: str
    risks: str
    summary: str

def extract(state): ...
def analyze(state): ...
def summarize(state): ...

graph = StateGraph(State)
graph.add_node("extract", extract)
graph.add_node("analyze", analyze)
graph.add_node("summarize", summarize)
graph.add_edge("extract", "analyze")
graph.add_edge("analyze", "summarize")
graph.add_edge(START, "extract")
graph.add_edge("summarize", END)
app = graph.compile()
```

**adk-fluent** (1 expression):

```python
pipeline = extractor >> analyst >> summarizer
```

[Full example with native ADK comparison →](examples/cookbook/04_sequential_pipeline.py)

### Multi-Source Research with Quality Loop

A deep-research pipeline: decompose query, search 3 sources in parallel, synthesize, review in a loop until quality threshold is met.

**LangGraph** (~60 lines):

```python
class ResearchState(TypedDict):
    query: str
    web_results: str
    academic_results: str
    news_results: str
    synthesis: str
    quality_score: float

def analyze_query(state): ...
def search_web(state): ...
def search_academic(state): ...
def search_news(state): ...
def synthesize(state): ...
def review_quality(state): ...
def should_continue(state):
    return "revise" if state["quality_score"] < 0.85 else "report"

graph = StateGraph(ResearchState)
graph.add_node("analyze", analyze_query)
graph.add_node("search_web", search_web)
graph.add_node("search_academic", search_academic)
graph.add_node("search_news", search_news)
graph.add_node("synthesize", synthesize)
graph.add_node("review", review_quality)
graph.add_node("revise", revise)
graph.add_node("report", write_report)
# ... 10+ add_edge / add_conditional_edges calls
app = graph.compile()
```

**adk-fluent** (1 expression):

```python
research = (
    analyzer
    >> (web | papers | news)
    >> synthesizer
    >> (reviewer >> reviser) * until(lambda s: s["quality_score"] >= 0.85)
    >> writer @ ResearchReport
)
```

[Full example with typed output and state wiring →](examples/cookbook/55_deep_research.py)

### Customer Support Triage

A helpdesk that classifies intent and routes to the right specialist.

**LangGraph** (~45 lines):

```python
class SupportState(TypedDict):
    message: str
    intent: str
    response: str

def classify(state): ...
def handle_billing(state): ...
def handle_technical(state): ...
def handle_general(state): ...
def route_intent(state):
    return state["intent"]  # conditional edge

graph = StateGraph(SupportState)
graph.add_node("classify", classify)
graph.add_node("billing", handle_billing)
graph.add_node("technical", handle_technical)
graph.add_node("general", handle_general)
graph.add_conditional_edges("classify", route_intent, {...})
app = graph.compile()
```

**adk-fluent** (1 expression):

```python
support = (
    S.capture("message")
    >> classifier
    >> Route("intent")
        .eq("billing", billing)
        .eq("technical", technical)
        .otherwise(general)
)
```

[Full example with escalation gates →](examples/cookbook/56_customer_support_triage.py)

### The Pattern

| What | LangGraph | Native ADK | adk-fluent |
| --- | --- | --- | --- |
| Sequential pipeline | ~35 lines | ~20 lines | 1 expression |
| Parallel + loop | ~60 lines | ~45 lines | 1 expression |
| Routing | ~45 lines | ~35 lines | 1 expression |
| Boilerplate | StateGraph, TypedDict, edges | Agent, Runner, Session | None |
| Result type | LangGraph graph | ADK agent | ADK agent |

For a detailed comparison including CrewAI and native ADK code, see the [Framework Comparison](https://vamsiramakrishnan.github.io/adk-fluent/user-guide/comparison/) guide.
````

**Step 3: Verify template renders**

Run: `uv run python scripts/readme_generator.py`
Expected: README.md generated with new "Why adk-fluent" section.

**Step 4: Run preflight**

Run: `uv run pre-commit run --all-files`
Expected: All hooks pass (mdformat may reformat tables -- stage and re-run).

**Step 5: Commit**

```bash
git add README.template.md README.md
git commit -m "docs: add Why adk-fluent section with framework comparisons"
```

______________________________________________________________________

### Task 2: Create comparison doc

**Files:**

- Create: `docs/user-guide/comparison.md`

**Step 1: Write comparison doc**

Create `docs/user-guide/comparison.md` with:

1. **Introduction**: What this page covers, who it's for
1. **Feature matrix**: 8-dimension table comparing LangGraph, CrewAI, native ADK, adk-fluent
1. **Pattern 1: Sequential Pipeline** -- full code in all 4 frameworks
1. **Pattern 2: Parallel Research** -- full code in all 4 frameworks
1. **Pattern 3: Routing** -- full code in all 4 frameworks
1. **When to use each framework** -- honest guidance
1. **Links** to cookbook examples

Feature matrix dimensions:

- Lines of code (typical agent)
- Testing support
- Type safety
- Visualization
- Streaming
- State management
- Routing/branching
- Composability

**Step 2: Run preflight**

Run: `uv run pre-commit run --all-files`

**Step 3: Commit**

```bash
git add docs/user-guide/comparison.md
git commit -m "docs: add framework comparison guide"
```

______________________________________________________________________

### Task 3: Enhance cookbook docstrings -- sequential pipeline examples

**Files:**

- Modify: `examples/cookbook/04_sequential_pipeline.py` (docstring only)
- Modify: `examples/cookbook/28_real_world_pipeline.py` (docstring only)
- Modify: `examples/cookbook/15_production_runtime.py` (docstring only)
- Modify: `examples/cookbook/09_streaming.py` (docstring only)

**Step 1: Add real-world framing to each docstring**

For each file, add `Real-world use case:` and `In other frameworks:` blocks to the existing docstring. Do NOT change any code -- only the module docstring between `"""..."""`.

Example for 04:

```python
"""Document Processing Pipeline -- Sequential Pipeline

Real-world use case: Contract review system that extracts key terms,
identifies legal risks, and produces executive summaries. Used by legal
teams processing high volumes of vendor agreements.

In other frameworks: LangGraph requires a StateGraph with TypedDict state,
3 node functions, and 5 edge declarations (~35 lines). Native ADK requires
3 LlmAgent + 1 SequentialAgent declarations (~20 lines). adk-fluent
composes the same pipeline in a single expression.

Pipeline topology:
    extractor >> risk_analyst >> summarizer
"""
```

**Step 2: Run tests to verify docstrings don't break anything**

Run: `uv run pytest tests/test_cookbook.py -x --tb=short -q`
Expected: All cookbook tests pass.

**Step 3: Commit**

```bash
git add examples/cookbook/04_sequential_pipeline.py examples/cookbook/28_real_world_pipeline.py examples/cookbook/15_production_runtime.py examples/cookbook/09_streaming.py
git commit -m "docs: enhance sequential pipeline cookbook docstrings with real-world framing"
```

______________________________________________________________________

### Task 4: Enhance cookbook docstrings -- parallel and loop examples

**Files:**

- Modify: `examples/cookbook/05_parallel_fanout.py` (docstring only)
- Modify: `examples/cookbook/34_full_algebra.py` (docstring only)
- Modify: `examples/cookbook/55_deep_research.py` (docstring only)
- Modify: `examples/cookbook/06_loop_agent.py` (docstring only)
- Modify: `examples/cookbook/30_until_operator.py` (docstring only)

**Step 1: Add real-world framing to each docstring**

Same pattern as Task 3 -- add `Real-world use case:` and `In other frameworks:` blocks.

**Step 2: Run cookbook tests**

Run: `uv run pytest tests/test_cookbook.py -x --tb=short -q`

**Step 3: Commit**

```bash
git add examples/cookbook/05_parallel_fanout.py examples/cookbook/34_full_algebra.py examples/cookbook/55_deep_research.py examples/cookbook/06_loop_agent.py examples/cookbook/30_until_operator.py
git commit -m "docs: enhance parallel and loop cookbook docstrings with real-world framing"
```

______________________________________________________________________

### Task 5: Enhance cookbook docstrings -- routing and composite examples

**Files:**

- Modify: `examples/cookbook/56_customer_support_triage.py` (docstring only)
- Modify: `examples/cookbook/50_capture_and_route.py` (docstring only)
- Modify: `examples/cookbook/17_route_branching.py` (docstring only)
- Modify: `examples/cookbook/49_context_engineering.py` (docstring only)
- Modify: `examples/cookbook/53_structured_schemas.py` (docstring only)
- Modify: `examples/cookbook/57_code_review_agent.py` (docstring only)

**Step 1: Add real-world framing to each docstring**

Same pattern -- add `Real-world use case:` and `In other frameworks:` blocks.

**Step 2: Run cookbook tests**

Run: `uv run pytest tests/test_cookbook.py -x --tb=short -q`

**Step 3: Commit**

```bash
git add examples/cookbook/56_customer_support_triage.py examples/cookbook/50_capture_and_route.py examples/cookbook/17_route_branching.py examples/cookbook/49_context_engineering.py examples/cookbook/53_structured_schemas.py examples/cookbook/57_code_review_agent.py
git commit -m "docs: enhance routing and composite cookbook docstrings with real-world framing"
```

______________________________________________________________________

### Task 6: Regenerate README and run full verification

**Files:**

- Regenerate: `README.md`

**Step 1: Regenerate README**

Run: `uv run python scripts/readme_generator.py`

**Step 2: Run full preflight**

Run: `uv run pre-commit run --all-files`
Stage any fixes, re-run until idempotent.

**Step 3: Run full test suite**

Run: `uv run pytest tests/ -x --tb=short -q`
Expected: All tests pass.

**Step 4: Verify new content**

Check README.md contains:

- "Why adk-fluent" section header
- LangGraph comparison code blocks
- Summary table
- Link to comparison doc

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: regenerate README with framework comparison section"
```
