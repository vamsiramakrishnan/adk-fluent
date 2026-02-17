"""
Fallback Chains: // Operator

Converted from cookbook example: 32_fallback_operator.py

Usage:
    cd examples
    adk web fallback_operator
"""

from adk_fluent import Agent, Pipeline
from adk_fluent._base import _FallbackBuilder
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# // creates a fallback chain — first success wins
fast = Agent("fast").model("gemini-2.0-flash").instruct("Quick answer.")
slow = Agent("slow").model("gemini-2.5-pro").instruct("Thorough answer.")

answer = fast // slow  # Try fast first, fall back to slow

# Three-way fallback
tier1 = Agent("cache").model("gemini-2.0-flash").instruct("Check cache.")
tier2 = Agent("search").model("gemini-2.5-flash").instruct("Search for answer.")
tier3 = Agent("expert").model("gemini-2.5-pro").instruct("Deep analysis.")

resilient = tier1 // tier2 // tier3

# Composes with >> in pipelines
pipeline = (
    Agent("classifier").model("gemini-2.5-flash").instruct("Classify request.")
    >> (fast // slow)
    >> Agent("formatter").model("gemini-2.5-flash").instruct("Format output.")
)

# Composes with | in parallel
branch_a = Agent("a1").model("gemini-2.0-flash") // Agent("a2").model("gemini-2.5-pro")
branch_b = Agent("b1").model("gemini-2.0-flash") // Agent("b2").model("gemini-2.5-pro")
parallel_fallbacks = branch_a | branch_b

# // works with functions too
fallback_with_fn = (
    Agent("primary").model("gemini-2.5-flash").instruct("Try this.")
    // (lambda s: {"result": "static fallback"})
)

root_agent = fallback_with_fn.build()
