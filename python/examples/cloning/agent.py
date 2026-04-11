"""
A/B Testing Agent Variants -- Agent Cloning with .clone()

Demonstrates .clone() for creating independent agent variants from
a shared base configuration.  The scenario: A/B testing two customer
support agents -- one using a formal tone and one using a casual tone
-- while sharing the same underlying tool (order lookup).

Converted from cookbook example: 10_cloning.py

Usage:
    cd examples
    adk web cloning
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


def lookup_order(order_id: str) -> str:
    """Look up the status of a customer order by its ID."""
    return f"Order {order_id}: shipped, arriving Thursday"


base = (
    Agent("support_base")
    .model("gemini-2.5-flash")
    .instruct("You are a customer support agent. Help customers with order inquiries.")
    .tool(lookup_order)
)

variant_a = base.clone("formal_support").instruct(
    "You are a customer support agent. Use formal, professional language. "
    "Address the customer as Sir or Madam. Be thorough and precise."
)
variant_b = base.clone("casual_support").instruct(
    "You are a customer support agent. Use friendly, casual language. "
    "Be warm and personable. Use the customer's first name."
)

root_agent = variant_b.build()
