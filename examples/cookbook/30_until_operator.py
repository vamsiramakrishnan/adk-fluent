"""Conditional Loops: * until(pred) Operator"""

# --- NATIVE ---
# Native ADK has no conditional loop exit built in. You'd need:
#   1. A custom BaseAgent subclass evaluating the predicate
#   2. Yield Event(actions=EventActions(escalate=True)) to break
#   3. Wire it into LoopAgent.sub_agents manually
# This is ~25 lines of boilerplate per loop condition.

# --- FLUENT ---
from adk_fluent import Agent, Pipeline, until

# until() creates a spec for the * operator
quality_ok = until(lambda s: s.get("quality") == "good", max=5)

# agent * until(pred) — loop until predicate is satisfied
loop = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write a draft.").outputs("quality")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Review and rate quality.")
) * quality_ok

# Default max is 10
conservative = (
    Agent("drafter").model("gemini-2.5-flash").instruct("Draft.")
    >> Agent("checker").model("gemini-2.5-flash").instruct("Check.")
) * until(lambda s: s.get("done"))

# Works in larger expressions: a >> (loop) * until(pred) >> b
full_pipeline = (
    Agent("intake").model("gemini-2.5-flash").instruct("Gather requirements.")
    >> (
        Agent("builder").model("gemini-2.5-flash").instruct("Build solution.")
        >> Agent("tester").model("gemini-2.5-flash").instruct("Test solution.")
    )
    * until(lambda s: s.get("tests_pass"), max=3)
    >> Agent("deployer").model("gemini-2.5-flash").instruct("Deploy.")
)

# int * agent still works as before
simple_loop = Agent("polisher").model("gemini-2.5-flash").instruct("Polish.") * 3

# --- ASSERT ---
from adk_fluent.workflow import Loop

# * until() creates a Loop
assert isinstance(loop, Loop)
assert loop._config["max_iterations"] == 5
assert loop._config["_until_predicate"] is not None

# Default max is 10
assert conservative._config["max_iterations"] == 10

# Builds with checkpoint agent for loop exit
built = loop.build()
assert built.sub_agents[-1].name == "_until_check"

# In larger expression — pipeline with loop in middle
assert isinstance(full_pipeline, Pipeline)
built_full = full_pipeline.build()
assert len(built_full.sub_agents) == 3  # intake, loop, deployer

# int * agent still works
assert isinstance(simple_loop, Loop)
assert simple_loop._config["max_iterations"] == 3
