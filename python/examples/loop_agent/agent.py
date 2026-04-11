"""
Essay Refinement Loop -- Loop Agent

Demonstrates a LoopAgent that iterates sub-agents until a maximum
iteration count.  The scenario: an essay refinement workflow where
a critic evaluates the draft and a reviser improves it, repeating
up to 3 times until quality standards are met.

Real-world use case: Essay refinement loop where a writer drafts and a critic
provides feedback iteratively. Used by content teams to improve quality through
structured iteration.

In other frameworks: LangGraph models loops as conditional back-edges in a
StateGraph, requiring a routing function to decide continue vs stop (~25 lines).
adk-fluent uses * N for fixed iterations or * until() for conditional loops.

Pipeline topology:
    ( critic >> reviser ) * 3

Converted from cookbook example: 06_loop_agent.py

Usage:
    cd examples
    adk web loop_agent
"""

from adk_fluent import Agent, Loop
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

loop_fluent = (
    Loop("essay_refiner")
    .max_iterations(3)
    .step(
        Agent("critic")
        .model("gemini-2.5-flash")
        .instruct(
            "Evaluate the essay for clarity, structure, grammar, "
            "and argument strength. Provide specific, actionable "
            "feedback. If the essay meets a high quality bar, "
            "say APPROVED."
        )
    )
    .step(
        Agent("reviser")
        .model("gemini-2.5-flash")
        .instruct(
            "Revise the essay based on the critic's feedback. "
            "Improve clarity, fix grammatical issues, and strengthen "
            "weak arguments while preserving the author's voice."
        )
    )
    .build()
)

root_agent = loop_fluent
