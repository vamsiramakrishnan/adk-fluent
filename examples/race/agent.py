"""
Race: Fastest-Response Search Across Multiple Providers

Pipeline topology:
    race( westlaw_search, lexis_search )    -- first to finish wins

    Research pipeline:
        query_classifier >> race( federal_search, state_search ) >> citation_formatter

Converted from cookbook example: 42_race.py

Usage:
    cd examples
    adk web race
"""

from adk_fluent import Agent, Pipeline, race
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Scenario: A legal research platform that queries multiple search providers.
# The first provider to return results wins -- minimizing user wait time
# while maximizing coverage through diverse sources.

westlaw = (
    Agent("westlaw_search")
    .model("gemini-2.5-flash")
    .instruct("Search Westlaw for relevant case law and statutes matching the query.")
)
lexis = (
    Agent("lexis_search")
    .model("gemini-2.5-flash")
    .instruct("Search LexisNexis for relevant legal opinions and secondary sources.")
)

# race(): run agents concurrently, keep only the first to finish
fastest_result = race(westlaw, lexis)

# Three-way race across different search strategies
keyword_search = (
    Agent("keyword_search")
    .model("gemini-2.5-flash")
    .instruct("Perform keyword-based search across the legal database.")
)
semantic_search = (
    Agent("semantic_search")
    .model("gemini-2.5-flash")
    .instruct("Perform semantic similarity search for conceptually related cases.")
)
citation_search = (
    Agent("citation_search").model("gemini-2.5-flash").instruct("Follow citation networks from known relevant cases.")
)

best_strategy = race(keyword_search, semantic_search, citation_search)

# Race in a pipeline: classify the query, race search strategies, format results
research_pipeline = (
    Agent("query_classifier")
    .model("gemini-2.5-flash")
    .instruct("Classify the legal research query by jurisdiction and area of law.")
    >> race(
        Agent("federal_search").model("gemini-2.5-flash").instruct("Search federal case law databases."),
        Agent("state_search").model("gemini-2.5-flash").instruct("Search state case law databases."),
    )
    >> Agent("citation_formatter")
    .model("gemini-2.5-flash")
    .instruct("Format the search results with proper Bluebook citations.")
)

root_agent = research_pipeline.build()
