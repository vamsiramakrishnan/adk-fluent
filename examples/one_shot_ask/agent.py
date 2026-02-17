"""
One-Shot Execution with .ask()

Converted from cookbook example: 08_one_shot_ask.py

Usage:
    cd examples
    adk web one_shot_ask
"""

from adk_fluent import Agent

# One line:
# result = Agent("q").model("gemini-2.5-flash").instruct("Answer concisely.").ask("What is 2+2?")

# Builder mechanics verification (no LLM call):
builder = Agent("q").model("gemini-2.5-flash").instruct("Answer concisely.")

root_agent = builder.build()
