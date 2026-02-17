"""
Conditional Loop Exit with loop_until

Converted from cookbook example: 20_loop_until.py

Usage:
    cd examples
    adk web loop_until
"""

from adk_fluent import Agent, Loop
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# loop_until: wraps in a loop that exits when predicate is satisfied
writer = Agent("writer").model("gemini-2.5-flash").instruct("Write a draft.").outputs("quality")
reviewer = Agent("reviewer").model("gemini-2.5-flash").instruct("Review the draft.")

refinement = (writer >> reviewer).loop_until(
    lambda s: s.get("quality") == "good",
    max_iterations=5
)

# .until() on a Loop — alternative syntax
manual_loop = (
    Loop("polish")
    .step(Agent("drafter").model("gemini-2.5-flash").instruct("Draft."))
    .step(Agent("checker").model("gemini-2.5-flash").instruct("Check.").outputs("done"))
    .until(lambda s: s.get("done") == "yes")
    .max_iterations(10)
)

root_agent = manual_loop.build()
