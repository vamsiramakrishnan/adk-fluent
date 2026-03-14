# Code Review Agent — Parallel Analysis with Structured Verdicts

> **Modules in play:** `>>` sequential, `|` parallel fan-out, `@` typed output,
> `tap()` observation, `proceed_if()` conditional gating

## The Real-World Problem

Your engineering team runs code reviews manually. Every PR gets the same three
passes: style, security, and logic. Reviewers context-switch between concerns,
miss issues when fatigued, and produce unstructured comments that are hard to
track. You need an automated pre-merge gate that runs all three review passes
*concurrently*, aggregates findings into a structured verdict (approved/rejected
with counts), and only writes a comment when there are actual findings — not
a boilerplate "LGTM" on every clean PR.

## The Fluent Solution

```python
from pydantic import BaseModel
from adk_fluent import Agent, Pipeline, tap

MODEL = "gemini-2.5-flash"
review_log = []


class ReviewResult(BaseModel):
    """Aggregated code review verdict."""
    approved: bool
    findings_count: int
    critical_count: int
    summary: str


# Stage 1: Parse the diff into reviewable chunks
diff_parser = (
    Agent("diff_parser", MODEL)
    .instruct(
        "Parse the git diff into individual file changes. "
        "Extract changed lines with context. Identify language and framework."
    )
    .writes("parsed_changes")
)

# Stage 2: Three review passes — run IN PARALLEL
style_review = (
    Agent("style_checker", MODEL)
    .instruct(
        "Review code style: naming conventions, function length, "
        "missing docstrings, dead code, unused imports."
    )
    .writes("style_findings")
)
security_review = (
    Agent("security_scanner", MODEL)
    .instruct(
        "Scan for security vulnerabilities: SQL injection, XSS, "
        "hardcoded secrets, missing input validation."
    )
    .writes("security_findings")
)
logic_review = (
    Agent("logic_reviewer", MODEL)
    .instruct(
        "Review business logic: edge cases, error handling, "
        "race conditions, off-by-one errors."
    )
    .writes("logic_findings")
)

# Stage 3: Aggregate into structured verdict
aggregator = (
    Agent("finding_aggregator", MODEL)
    .instruct("Aggregate findings from all reviews. Count criticals. Determine approval.")
    @ ReviewResult
)

# Stage 4: Write comment ONLY if findings exist
comment_writer = (
    Agent("comment_writer", MODEL)
    .instruct("Write a constructive review comment. Group by file. Lead with praise.")
    .proceed_if(lambda s: s.get("findings_count", 0) > 0)
)

# THE SYMPHONY
code_review = (
    diff_parser
    >> (style_review | security_review | logic_review)
    >> tap(lambda s: review_log.append("reviews_complete"))
    >> aggregator
    >> comment_writer
)
```

## The Interplay Breakdown

**Why `|` for the three review passes?**
Style, security, and logic reviews are independent — they examine the same diff
but check different concerns. Running them sequentially would 3x the review time.
The `|` operator composes them into a `ParallelAgent` that runs all three
concurrently and merges their `*_findings` keys into shared state.

**Why `@` on the aggregator?**
The aggregator must produce a machine-readable verdict — not prose. The
`@ ReviewResult` binding forces output into `{approved: bool, findings_count: int, ...}`.
Downstream systems (CI pipelines, PR status checks) can consume this directly.
If the LLM returns malformed JSON, it fails fast rather than silently producing
garbage.

**Why `tap()` between fan-out and aggregation?**
`tap()` is a pure observation point — it executes a function but never mutates
state. Here it logs "reviews_complete" for monitoring. Unlike inserting a
logging agent (which costs an LLM call), `tap` is zero-cost. It's the
difference between instrumenting your pipeline and bloating it.

**Why `proceed_if()` on the comment writer?**
Clean PRs don't need review comments. `proceed_if(lambda s: s.get("findings_count", 0) > 0)`
skips the comment writer entirely when there are no findings. Without this,
every clean PR gets a meaningless "no issues found" comment — noise that trains
developers to ignore review comments.

## Pipeline Topology

```
diff_parser ──► ┌─ style_checker ────┐
                │  security_scanner  │──► tap(log) ──► aggregator @ ReviewResult
                │  logic_reviewer ───┘                     │
                                                    proceed_if(findings > 0)
                                                           │
                                                    comment_writer
```

## Framework Comparison

| Framework    | Lines | Parallel reviews? | Typed verdict? | Conditional output? |
|-------------|-------|-------------------|---------------|-------------------|
| **adk-fluent** | ~40 | `\|` operator      | `@` operator   | `proceed_if()`    |
| Native ADK   | ~80  | Manual `ParallelAgent` | Manual `output_schema` | Custom `BaseAgent` |
| LangGraph    | ~55  | Fan-out subgraph   | Pydantic integration | Conditional edge |
