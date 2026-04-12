"""
Code Review Pipeline -- Expression Algebra in Practice

Demonstrates how composition operators (>>, |, @, //) combine naturally
in a real-world code review system. A diff parser extracts changes,
parallel reviewers check style, security, and logic independently,
then findings are aggregated into a structured verdict.

Real-world use case: Automated code review pipeline that runs style, security,
and logic reviewers in parallel, then merges findings. Used by engineering teams
as a pre-merge quality gate.

In other frameworks: LangGraph models this as a fan-out subgraph with merge
node (~45 lines). adk-fluent composes parallel reviewers with | and sequences
with >> in a single expression.

Pipeline topology:
    diff_parser
        >> ( style_checker | security_scanner | logic_reviewer )
        >> ( finding_aggregator @ ReviewVerdict // backup_aggregator @ ReviewVerdict )

Converted from cookbook example: 34_full_algebra.py

Usage:
    cd examples
    adk web full_algebra
"""

from pydantic import BaseModel

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


class ReviewVerdict(BaseModel):
    """Structured output from the code review pipeline."""

    has_issues: bool
    critical_count: int
    summary: str


# The code review pipeline uses 4 operators:
#   >>  sequential flow (parse -> review -> aggregate)
#   |   parallel fan-out (style + security + logic run concurrently)
#   @   typed output (aggregator returns ReviewVerdict)
#   //  fallback (primary model -> backup model)

review_pipeline = (
    # Step 1: Parse the diff into reviewable chunks
    Agent("diff_parser")
    .model("gemini-2.5-flash")
    .instruct("Parse the git diff into individual file changes with context.")
    .writes("parsed_diff")
    # Step 2: Three reviewers run in parallel
    >> (
        Agent("style_checker")
        .model("gemini-2.5-flash")
        .instruct("Check code style: naming conventions, formatting, docstrings.")
        | Agent("security_scanner")
        .model("gemini-2.5-flash")
        .instruct("Scan for security issues: injection, auth bypass, secrets in code.")
        | Agent("logic_reviewer")
        .model("gemini-2.5-flash")
        .instruct("Review business logic: edge cases, error handling, race conditions.")
    )
    # Step 3: Aggregate findings with typed output and model fallback
    >> (
        Agent("finding_aggregator")
        .model("gemini-2.5-flash")
        .instruct("Aggregate all review findings into a final verdict.")
        @ ReviewVerdict
        // Agent("backup_aggregator")
        .model("gemini-2.5-pro")
        .instruct("Aggregate all review findings into a final verdict.")
        @ ReviewVerdict
    )
)

root_agent = review_pipeline.build()
