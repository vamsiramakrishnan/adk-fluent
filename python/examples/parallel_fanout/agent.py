"""
Market Research Fan-Out -- Parallel FanOut

Demonstrates a ParallelAgent that runs branches concurrently.  The
scenario: a market research system that simultaneously gathers
intelligence from web sources, academic papers, and social media
to produce a comprehensive competitive analysis.

Real-world use case: Competitive intelligence system that simultaneously
gathers data from web, academic, and social media sources. Used by market
research teams to produce comprehensive analysis in minutes instead of days.

In other frameworks: LangGraph requires a StateGraph with fan-out nodes and
edge wiring (~30 lines). CrewAI supports parallel via Crew(process="parallel")
but lacks explicit fan-out composition. adk-fluent uses the | operator for
declarative parallel execution.

Pipeline topology:
    ( web_analyst | academic_analyst | social_analyst )

Converted from cookbook example: 05_parallel_fanout.py

Usage:
    cd examples
    adk web parallel_fanout
"""

from adk_fluent import Agent, FanOut
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

fanout_fluent = (
    FanOut("market_research")
    .branch(
        Agent("web_analyst")
        .model("gemini-2.5-flash")
        .instruct(
            "Search the web for recent news articles, press releases, "
            "and blog posts about competitors in this market segment."
        )
    )
    .branch(
        Agent("academic_analyst")
        .model("gemini-2.5-flash")
        .instruct("Search academic databases for recent research papers and industry reports relevant to this market.")
    )
    .branch(
        Agent("social_analyst")
        .model("gemini-2.5-flash")
        .instruct("Analyze social media sentiment and trending discussions about products and brands in this market.")
    )
    .build()
)

root_agent = fanout_fluent
