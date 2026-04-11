"""
Document Processing Pipeline -- Sequential Pipeline

Real-world use case: Contract review system used by legal teams to process
vendor agreements at scale. Extracts key terms, identifies legal risks,
and produces executive summaries -- replacing hours of manual review.

In other frameworks: LangGraph requires a StateGraph with TypedDict state,
3 node functions, and 5 edge declarations (~35 lines). CrewAI needs 3 Agent
objects with role/goal/backstory plus 3 Task objects (~30 lines). Native ADK
needs 3 LlmAgent + 1 SequentialAgent (~20 lines). adk-fluent composes the
same pipeline in a single expression.

Pipeline topology:
    extractor >> risk_analyst >> summarizer

Converted from cookbook example: 04_sequential_pipeline.py

Usage:
    cd examples
    adk web sequential_pipeline
"""

from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

pipeline_fluent = (
    Pipeline("contract_review")
    .describe("Extract, analyze, and summarize contracts")
    .step(
        Agent("extractor")
        .model("gemini-2.5-flash")
        .instruct(
            "Extract key terms from the contract: parties involved, "
            "effective dates, payment terms, and termination clauses."
        )
    )
    .step(
        Agent("risk_analyst")
        .model("gemini-2.5-flash")
        .instruct(
            "Analyze the extracted terms for legal risks. Flag any "
            "unusual clauses, missing protections, or liability concerns."
        )
    )
    .step(
        Agent("summarizer")
        .model("gemini-2.5-flash")
        .instruct(
            "Produce a one-page executive summary combining the extracted "
            "terms and risk analysis. Use clear, non-legal language."
        )
    )
    .build()
)

root_agent = pipeline_fluent
