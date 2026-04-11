"""
Email Classifier Agent -- Simple Agent Creation

Demonstrates creating a minimal LLM agent using both native ADK and
the fluent builder.  The scenario: an agent that classifies incoming
customer emails into categories (billing, technical, general).

Converted from cookbook example: 01_simple_agent.py

Usage:
    cd examples
    adk web simple_agent
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

agent_fluent = (
    Agent("email_classifier")
    .model("gemini-2.5-flash")
    .instruct(
        "You are an email classifier for a SaaS company. "
        "Read the incoming email and classify it as one of: "
        "billing, technical, or general."
    )
    .describe("Classifies customer emails by intent")
    .build()
)

root_agent = agent_fluent
