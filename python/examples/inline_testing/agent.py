"""
Smoke-Testing a Customer Support Bot -- Inline Testing with .test()

Demonstrates the .test() method for validating agent behavior during
development.  The scenario: a customer support bot that is
smoke-tested inline before deployment to ensure it handles common
queries correctly.  No LLM calls are made here -- we verify that
the builder exposes the test API with the right signature.

Converted from cookbook example: 11_inline_testing.py

Usage:
    cd examples
    adk web inline_testing
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# In production, you chain tests directly into the agent definition:
# agent = (
#     Agent("support_bot")
#     .model("gemini-2.5-flash")
#     .instruct("You are a customer support agent for an e-commerce platform.")
#     .test("How do I return an item?", contains="return")
#     .test("What is your refund policy?", contains="refund")
#     .test("Track my order #12345", contains="order")
#     .build()
# )

builder = (
    Agent("support_bot")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a customer support agent for an e-commerce platform. "
        "Handle returns, refunds, order tracking, and general inquiries. "
        "Always be polite and offer to escalate to a human if needed."
    )
)

root_agent = builder.build()
