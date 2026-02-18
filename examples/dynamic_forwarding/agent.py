"""
Dynamic Field Forwarding via __getattr__

Converted from cookbook example: 14_dynamic_forwarding.py

Usage:
    cd examples
    adk web dynamic_forwarding
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Fields not explicitly aliased still work via __getattr__:
agent_fluent = (
    Agent("dynamic").model("gemini-2.5-flash").instruct("test").output_key("result").include_contents("none").build()
)

root_agent = agent_fluent
