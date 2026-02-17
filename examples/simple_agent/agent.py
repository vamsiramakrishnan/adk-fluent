"""
Simple Agent Creation

Converted from cookbook example: 01_simple_agent.py

Usage:
    cd examples
    adk web simple_agent
"""

from adk_fluent import Agent

agent_fluent = (
    Agent("helper")
    .model("gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
    .describe("A simple helper agent")
    .build()
)

root_agent = agent_fluent
