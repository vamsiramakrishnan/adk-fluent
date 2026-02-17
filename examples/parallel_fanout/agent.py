"""
Parallel FanOut

Converted from cookbook example: 05_parallel_fanout.py

Usage:
    cd examples
    adk web parallel_fanout
"""

from adk_fluent import Agent, FanOut

fanout_fluent = (
    FanOut("parallel_search")
    .branch(Agent("web").model("gemini-2.5-flash").instruct("Search web."))
    .branch(Agent("db").model("gemini-2.5-flash").instruct("Search database."))
    .build()
)

root_agent = fanout_fluent
