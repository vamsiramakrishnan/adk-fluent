"""
Customer Service Hub: Agent Transfer Control

Demonstrates controlling how agents transfer between each other using
disallow_transfer_to_parent, disallow_transfer_to_peers, and the
.isolate() convenience method.  The scenario: a customer service system
where a coordinator routes to specialist agents that must complete their
task before returning control.

Converted from cookbook example: 54_transfer_control.py

Usage:
    cd examples
    adk web transfer_control
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Using explicit .disallow_transfer_to_parent() and .disallow_transfer_to_peers()
billing_explicit = (
    Agent("billing_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You handle billing inquiries: refunds, payment disputes, "
        "invoice corrections, and subscription changes. Resolve the "
        "issue completely before finishing."
    )
    .describe("Handles billing, payment, and subscription issues")
    .disallow_transfer_to_parent(True)
    .disallow_transfer_to_peers(True)
)

# Using .isolate() -- sets both flags in one call
billing_isolated = (
    Agent("billing_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You handle billing inquiries: refunds, payment disputes, "
        "invoice corrections, and subscription changes. Resolve the "
        "issue completely before finishing."
    )
    .describe("Handles billing, payment, and subscription issues")
    .isolate()
)

technical_fluent = (
    Agent("technical_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You handle technical support: bug reports, integration issues, "
        "API errors, and configuration problems. Walk the customer "
        "through troubleshooting steps."
    )
    .describe("Handles technical support and troubleshooting")
    .isolate()
)

general_fluent = (
    Agent("general_support")
    .model("gemini-2.5-flash")
    .instruct(
        "You handle general inquiries: account information, product "
        "questions, and feedback. You may transfer back to the "
        "coordinator if the issue requires a specialist."
    )
    .describe("Handles general inquiries and account questions")
)

coordinator_fluent = (
    Agent("service_coordinator")
    .model("gemini-2.5-flash")
    .instruct(
        "You are the front-line customer service coordinator. Greet the "
        "customer, understand their issue, and route to the right "
        "specialist: billing for payment issues, technical for bugs "
        "and integrations, or general for everything else."
    )
    .transfer_to(billing_isolated)
    .transfer_to(technical_fluent)
    .transfer_to(general_fluent)
    .build()
)

root_agent = billing_explicit
