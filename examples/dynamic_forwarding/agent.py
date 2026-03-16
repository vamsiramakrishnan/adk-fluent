"""
Multi-Department Ticket Routing via Dynamic Field Forwarding

Converted from cookbook example: 14_dynamic_forwarding.py

Usage:
    cd examples
    adk web dynamic_forwarding
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Fields not explicitly aliased (like output_key, include_contents) still
# work via __getattr__ dynamic forwarding. The builder validates field names
# against the ADK LlmAgent class, catching typos at build time.
agent_fluent = (
    Agent("ticket_router")
    .model("gemini-2.5-flash")
    .instruct("Classify incoming support tickets by department.")
    .writes("department")
    .include_contents("none")
    .build()
)

root_agent = agent_fluent
