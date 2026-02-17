"""
Production Runtime Setup

Converted from cookbook example: 15_production_runtime.py

Usage:
    cd examples
    adk web production_runtime
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# The fluent API reduces runtime setup too:
agent = (
    Agent("prod")
    .model("gemini-2.5-flash")
    .instruct("Production agent.")
    .describe("A production-ready agent with tools and callbacks.")
)

root_agent = agent.build()
