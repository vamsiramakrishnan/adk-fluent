"""
Conditional Loops: * until(pred) Operator

Converted from cookbook example: 30_until_operator.py

Usage:
    cd examples
    adk web until_operator
"""

from adk_fluent import Agent, Pipeline, until
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

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
    ) * until(lambda s: s.get("tests_pass"), max=3)
    >> Agent("deployer").model("gemini-2.5-flash").instruct("Deploy.")
)

# int * agent still works as before
simple_loop = Agent("polisher").model("gemini-2.5-flash").instruct("Polish.") * 3

root_agent = simple_loop.build()
