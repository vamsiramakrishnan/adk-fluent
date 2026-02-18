"""Full Expression Algebra: All Operators Together"""

# --- NATIVE ---
# The equivalent native ADK code would be 100+ lines of explicit agent
# construction, custom BaseAgent subclasses for transforms and fallbacks,
# manual checkpoint agents for conditional loops, and Pydantic schema wiring.
# The fluent algebra expresses all of this as a single readable expression.

# --- FLUENT ---
from pydantic import BaseModel
from adk_fluent import Agent, S, Pipeline, until
from adk_fluent._base import _FallbackBuilder


class Report(BaseModel):
    title: str
    body: str
    confidence: float


# The complete proof: all operators compose into one expression
#
#   |   parallel research
#   >>  sequence
#   fn  state transform
#   @   typed output
#   //  fallback
#   *   conditional loop
#   S   state transforms
pipeline = (
    # Step 1: Parallel research (|)
    (
        Agent("web").model("gemini-2.5-flash").instruct("Search the web for information.")
        | Agent("scholar").model("gemini-2.5-flash").instruct("Search academic papers.")
    )
    # Step 2: Merge research results (S transform via >>)
    >> S.merge("web", "scholar", into="research")
    # Step 3: Write with typed output (@) and fallback (//)
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write a report.")
    @ Report
    // Agent("writer_b").model("gemini-2.5-pro").instruct("Write a report.")
    @ Report
    # Step 4: Quality loop (* until)
    >> (
        Agent("critic").model("gemini-2.5-flash").instruct("Score the report.").outputs("confidence")
        >> Agent("reviser").model("gemini-2.5-flash").instruct("Improve the report.")
    )
    * until(lambda s: s.get("confidence", 0) >= 0.85, max=4)
)

# Sub-expression reuse — immutable operators make this safe
review = Agent("reviewer").model("gemini-2.5-flash").instruct("Review quality.") >> Agent("scorer").model(
    "gemini-2.5-flash"
).instruct("Score.").outputs("score")
quality_gate = until(lambda s: float(s.get("score", 0)) > 0.8, max=3)

# Same sub-expression in two independent pipelines
pipeline_a = (
    Agent("writer_a").model("gemini-2.5-flash").instruct("Write version A.")
    >> review * quality_gate
    >> S.rename(score="final_score_a")
)

pipeline_b = (
    Agent("writer_b").model("gemini-2.5-flash").instruct("Write version B.")
    >> review * quality_gate
    >> S.rename(score="final_score_b")
)

# --- ASSERT ---
# Main pipeline builds correctly
assert isinstance(pipeline, Pipeline)
built = pipeline.build()
assert len(built.sub_agents) == 4  # fanout, merge, fallback, loop

# Sub-expression reuse: both build independently
built_a = pipeline_a.build()
built_b = pipeline_b.build()
assert len(built_a.sub_agents) == 3
assert len(built_b.sub_agents) == 3
# Different agents — not shared
assert built_a.sub_agents[0].name != built_b.sub_agents[0].name
