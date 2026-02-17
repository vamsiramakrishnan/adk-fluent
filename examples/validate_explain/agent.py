"""
Validate and Explain

Converted from cookbook example: 25_validate_explain.py

Usage:
    cd examples
    adk web validate_explain
"""

from adk_fluent import Agent

# .validate() — catch config errors at definition time, not runtime
agent = (
    Agent("helper")
    .model("gemini-2.5-flash")
    .instruct("You are helpful.")
    .validate()  # Tries .build(), raises ValueError on failure
)

# .explain() — inspect builder state for debugging
explanation = agent.explain()

root_agent = agent
