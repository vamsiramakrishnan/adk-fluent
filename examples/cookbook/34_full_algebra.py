"""News Processing Pipeline: Full Expression Algebra with All Operators"""

# --- NATIVE ---
# The equivalent native ADK code would be 100+ lines of explicit agent
# construction, custom BaseAgent subclasses for transforms and fallbacks,
# manual checkpoint agents for conditional loops, and Pydantic schema wiring.
# The fluent algebra expresses this entire news processing system as
# a single readable expression.

# --- FLUENT ---
from pydantic import BaseModel
from adk_fluent import Agent, S, Pipeline, until
from adk_fluent._base import _FallbackBuilder


class Article(BaseModel):
    headline: str
    body: str
    credibility_score: float


# The complete proof: all operators compose into one expression.
# A news processing pipeline that ingests from multiple sources,
# verifies facts, writes an article, and iterates until quality is met.
#
#   |   parallel source collection
#   >>  sequential processing
#   fn  state transform
#   @   typed output schema
#   //  fallback between models
#   *   conditional quality loop
#   S   state transforms
pipeline = (
    # Step 1: Parallel news collection from multiple sources (|)
    (
        Agent("wire_service").model("gemini-2.5-flash")
        .instruct("Collect breaking news from AP, Reuters, and AFP wire services.")
        | Agent("social_monitor").model("gemini-2.5-flash")
        .instruct("Monitor social media for trending news topics and eyewitness reports.")
    )
    # Step 2: Merge all source data into unified research (S transform via >>)
    >> S.merge("wire_service", "social_monitor", into="raw_sources")
    # Step 3: Write article with typed output (@) and model fallback (//)
    >> Agent("senior_writer").model("gemini-2.5-flash")
    .instruct("Write a balanced, fact-checked news article from the source material.")
    @ Article
    // Agent("backup_writer").model("gemini-2.5-pro")
    .instruct("Write a balanced, fact-checked news article from the source material.")
    @ Article
    # Step 4: Editorial quality loop (* until) — editor reviews until credible
    >> (
        Agent("fact_checker").model("gemini-2.5-flash")
        .instruct("Verify all claims in the article against primary sources. Score credibility.")
        .outputs("credibility_score")
        >> Agent("copy_editor").model("gemini-2.5-flash")
        .instruct("Improve clarity, fix errors, and ensure AP style compliance.")
    )
    * until(lambda s: float(s.get("credibility_score", 0)) >= 0.90, max=4)
)

# Sub-expression reuse — immutable operators make this safe.
# An editorial review loop can be reused across different content pipelines.
editorial_review = (
    Agent("editor").model("gemini-2.5-flash")
    .instruct("Review article quality: accuracy, clarity, and engagement.")
    >> Agent("scorer").model("gemini-2.5-flash")
    .instruct("Score the article on a 0-1 scale.")
    .outputs("edit_score")
)
quality_gate = until(lambda s: float(s.get("edit_score", 0)) > 0.8, max=3)

# Same editorial review in two independent content pipelines
breaking_news = (
    Agent("breaking_writer").model("gemini-2.5-flash")
    .instruct("Write a concise breaking news alert.")
    >> editorial_review * quality_gate
    >> S.rename(edit_score="breaking_score")
)

feature_story = (
    Agent("feature_writer").model("gemini-2.5-flash")
    .instruct("Write an in-depth feature story with narrative structure.")
    >> editorial_review * quality_gate
    >> S.rename(edit_score="feature_score")
)

# --- ASSERT ---
# Main pipeline builds correctly
assert isinstance(pipeline, Pipeline)
built = pipeline.build()
assert len(built.sub_agents) == 4  # fanout, merge, fallback, loop

# Sub-expression reuse: both build independently
built_a = breaking_news.build()
built_b = feature_story.build()
assert len(built_a.sub_agents) == 3
assert len(built_b.sub_agents) == 3
# Different agents — not shared
assert built_a.sub_agents[0].name != built_b.sub_agents[0].name
