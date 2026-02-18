"""
Retry If: Conditional Retry Based on Output Quality

Converted from cookbook example: 38_retry_if.py

Usage:
    cd examples
    adk web retry_if
"""

from adk_fluent import Agent, Loop
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

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
via_retry = Agent("a").model("gemini-2.5-flash").retry_if(lambda s: s.get("ok") != "yes", max_retries=4)
via_loop = Agent("a").model("gemini-2.5-flash").loop_until(lambda s: s.get("ok") == "yes", max_iterations=4)

root_agent = via_loop.build()
