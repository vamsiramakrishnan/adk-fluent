"""
Operator Composition: >>, |, *

Converted from cookbook example: 16_operator_composition.py

Usage:
    cd examples
    adk web operator_composition
"""

from adk_fluent import Agent, Pipeline

r = Agent("researcher").model("gemini-2.5-flash").instruct("Research.")
w = Agent("writer").model("gemini-2.5-flash").instruct("Write.")
e = Agent("editor").model("gemini-2.5-flash").instruct("Edit.")

# >> creates Pipeline (SequentialAgent)
pipeline_fluent = r >> w >> e

# | creates FanOut (ParallelAgent)
web_f = Agent("web").model("gemini-2.5-flash").instruct("Search web.")
db_f = Agent("db").model("gemini-2.5-flash").instruct("Search DB.")
parallel_fluent = web_f | db_f

# * creates Loop (LoopAgent)
c = Agent("critic").model("gemini-2.5-flash").instruct("Critique.")
rv = Agent("reviser").model("gemini-2.5-flash").instruct("Revise.")
loop_fluent = (c >> rv) * 3

root_agent = loop_fluent.build()
