"""
Loop Agent

Converted from cookbook example: 06_loop_agent.py

Usage:
    cd examples
    adk web loop_agent
"""

from adk_fluent import Agent, Loop

loop_fluent = (
    Loop("refine")
    .max_iterations(3)
    .step(Agent("critic").model("gemini-2.5-flash").instruct("Critique."))
    .step(Agent("reviser").model("gemini-2.5-flash").instruct("Revise."))
    .build()
)

root_agent = loop_fluent
