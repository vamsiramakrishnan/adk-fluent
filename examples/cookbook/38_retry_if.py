"""Retry If: Conditional Retry Based on Output Quality"""

# --- NATIVE ---
# Native ADK has no built-in conditional retry. You'd need to:
#   1. Wrap the agent in a LoopAgent
#   2. Create a custom checkpoint BaseAgent that evaluates a predicate
#   3. Yield Event(actions=EventActions(escalate=True)) to exit when satisfied
# This is the same boilerplate as loop_until but with inverted logic.

# --- FLUENT ---
from adk_fluent import Agent, Loop

# .retry_if(): retry while the predicate returns True
# Semantically: "keep retrying as long as quality is not good"
writer = (
    Agent("writer")
    .model("gemini-2.5-flash")
    .instruct("Write a high-quality draft.")
    .outputs("quality")
    .retry_if(lambda s: s.get("quality") != "good", max_retries=3)
)

# retry_if on a pipeline -- retry the whole pipeline
pipeline_retry = (
    Agent("drafter").model("gemini-2.5-flash").instruct("Write.").outputs("draft")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Score quality.").outputs("score")
).retry_if(lambda s: float(s.get("score", "0")) < 8.0, max_retries=5)

# Equivalence: retry_if(p) == loop_until(not p)
# These produce identical behavior:
via_retry = Agent("a").model("gemini-2.5-flash").retry_if(
    lambda s: s.get("ok") != "yes", max_retries=4
)
via_loop = Agent("a").model("gemini-2.5-flash").loop_until(
    lambda s: s.get("ok") == "yes", max_iterations=4
)

# --- ASSERT ---
from adk_fluent.workflow import Loop as LoopBuilder

# retry_if creates a Loop builder
assert isinstance(writer, LoopBuilder)

# Default max_retries is 3
assert writer._config["max_iterations"] == 3

# Pipeline retry also creates a Loop
assert isinstance(pipeline_retry, LoopBuilder)
assert pipeline_retry._config["max_iterations"] == 5

# The predicate is inverted: retry_if(p) stores not-p as until_predicate
until_pred = writer._config["_until_predicate"]
assert until_pred({"quality": "good"}) is True   # exit: stop retrying
assert until_pred({"quality": "bad"}) is False    # continue retrying

# Both retry_if and loop_until produce Loop builders
assert isinstance(via_retry, LoopBuilder)
assert isinstance(via_loop, LoopBuilder)
assert via_retry._config["max_iterations"] == via_loop._config["max_iterations"]

# Build verifies checkpoint agent is injected
built = writer.build()
assert len(built.sub_agents) >= 2
assert built.sub_agents[-1].name == "_until_check"
