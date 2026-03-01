"""
Retry If: Conditional Retry Based on Output Quality

Converted from cookbook example: 38_loop_while.py

Usage:
    cd examples
    adk web loop_while
"""

from adk_fluent import Agent, Loop
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# .loop_while(): retry while the predicate returns True
# Semantically: "keep retrying as long as quality is not good"
writer = (
    Agent("writer")
    .model("gemini-2.5-flash")
    .instruct("Write a high-quality draft.")
    .writes("quality")
    .loop_while(lambda s: s.get("quality") != "good", max_iterations=3)
)

# loop_while on a pipeline -- retry the whole pipeline
pipeline_retry = (
    Agent("drafter").model("gemini-2.5-flash").instruct("Write.").writes("draft")
    >> Agent("reviewer").model("gemini-2.5-flash").instruct("Score quality.").writes("score")
).loop_while(lambda s: float(s.get("score", "0")) < 8.0, max_iterations=5)

# Equivalence: loop_while(p) == loop_until(not p)
# These produce identical behavior:
via_retry = Agent("a").model("gemini-2.5-flash").loop_while(lambda s: s.get("ok") != "yes", max_iterations=4)
via_loop = Agent("a").model("gemini-2.5-flash").loop_until(lambda s: s.get("ok") == "yes", max_iterations=4)

root_agent = via_loop.build()
