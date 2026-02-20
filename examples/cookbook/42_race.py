"""Race: Fastest-Response Search Across Multiple Providers"""

# --- NATIVE ---
# Native ADK's ParallelAgent runs all branches and merges results.
# There is no built-in "first to finish" mechanism. You'd need to:
#   1. Subclass BaseAgent
#   2. Use asyncio.create_task for each sub-agent
#   3. asyncio.wait(FIRST_COMPLETED) to get the winner
#   4. Cancel remaining tasks
# This is ~40 lines of async boilerplate.

# --- FLUENT ---
from adk_fluent import Agent, Pipeline, race

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

# --- ASSERT ---
from adk_fluent._base import _RaceBuilder, BuilderBase

# race() creates a _RaceBuilder
assert isinstance(fastest_result, _RaceBuilder)
assert isinstance(fastest_result, BuilderBase)

# Builds with correct number of sub-agents
built = fastest_result.build()
assert len(built.sub_agents) == 2
assert built.sub_agents[0].name == "westlaw_search"
assert built.sub_agents[1].name == "lexis_search"

# Three-way race
built3 = best_strategy.build()
assert len(built3.sub_agents) == 3

# Name includes agent names for tracing
assert "westlaw_search" in fastest_result._config["name"]
assert "lexis_search" in fastest_result._config["name"]

# Composable in pipeline
assert isinstance(research_pipeline, Pipeline)
built_pipeline = research_pipeline.build()
assert len(built_pipeline.sub_agents) == 3
