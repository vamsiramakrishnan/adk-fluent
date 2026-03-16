"""
Capture and Route: IT Helpdesk Triage

Real-world use case: IT helpdesk ticket capture and routing system. Captures
incoming messages into state, classifies urgency, and routes to appropriate
support tiers.

In other frameworks: LangGraph requires custom state capture via TypedDict
updates and conditional_edges for routing. adk-fluent uses S.capture() for
state injection and Route() for declarative branching.

Pipeline topology:
    S.capture("ticket")
        >> triage [save_as: priority]
        >> Route("priority")
            ├─ "p1" -> incident_commander
            ├─ "p2" -> senior_support
            └─ else -> support_bot

Converted from cookbook example: 50_capture_and_route.py

Usage:
    cd examples
    adk web capture_and_route
"""

from adk_fluent import Agent, S
from adk_fluent._routing import Route
from adk_fluent.testing import check_contracts
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

MODEL = "gemini-2.5-flash"

# IT Helpdesk: capture ticket → classify priority → route to team
helpdesk = (
    S.capture("ticket")
    >> Agent("triage")
    .model(MODEL)
    .instruct(
        "You are an IT helpdesk triage agent.\n"
        "Read the support ticket and classify it.\n"
        "Ticket: {ticket}\n"
        "Output the priority level: p1, p2, or p3."
    )
    .writes("priority")
    >> Route("priority")
    .eq(
        "p1",
        Agent("incident_commander")
        .model(MODEL)
        .instruct(
            "CRITICAL INCIDENT.\nOriginal ticket: {ticket}\nCoordinate immediate response. Page on-call engineer."
        ),
    )
    .eq(
        "p2",
        Agent("senior_support")
        .model(MODEL)
        .instruct("Priority ticket.\nTicket: {ticket}\nInvestigate and provide a resolution plan within 4 hours."),
    )
    .otherwise(
        Agent("support_bot")
        .model(MODEL)
        .instruct("Routine support request.\nTicket: {ticket}\nProvide self-service instructions or FAQ links.")
    )
)

# Verify data contracts before deployment
issues = check_contracts(helpdesk.to_ir())
contract_errors = [i for i in issues if isinstance(i, dict) and i.get("level") == "error"]

built = helpdesk.build()

root_agent = built
