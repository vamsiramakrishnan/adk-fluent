"""
Context Engineering: Customer Support Pipeline

Converted from cookbook example: 49_context_engineering.py

Usage:
    cd examples
    adk web context_engineering
"""

from adk_fluent import Agent, S, C
from adk_fluent._routing import Route
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

MODEL = "gemini-2.5-flash"

# Customer support pipeline: capture → classify → route → respond
# Each agent sees exactly the context it needs — nothing more.

support_pipeline = (
    S.capture("customer_message")
    >> Agent("classifier")
    .model(MODEL)
    .instruct(
        "Classify the customer's message into one of: billing, technical, general.\nCustomer said: {customer_message}"
    )
    .context(C.none())  # No history needed — just the captured message
    .writes("category")
    >> Route("category")
    .eq(
        "billing",
        Agent("billing_agent")
        .model(MODEL)
        .instruct(
            "You are a billing specialist. Help the customer with their billing issue.\n"
            "Customer message: {customer_message}"
        )
        .context(C.from_state("customer_message")),
    )
    .eq(
        "technical",
        Agent("tech_agent")
        .model(MODEL)
        .instruct(
            "You are a technical support engineer. Diagnose and resolve the issue.\n"
            "Customer message: {customer_message}\n"
            "Urgency: {urgency}"
        )
        .context(C.from_state("customer_message", "urgency") + C.window(n=3)),
    )
    .otherwise(
        Agent("general_agent")
        .model(MODEL)
        .instruct("Help the customer with their general inquiry.")
        .context(C.user_only())  # See only what the customer said
    )
)

built = support_pipeline.build()

root_agent = built
