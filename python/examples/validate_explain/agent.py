"""
Introspection & Debugging -- validate(), explain(), inspect()

Demonstrates the introspection methods that help debug and understand
agent configurations before deployment. The scenario: a compliance
team reviewing an insurance claims pipeline to verify correct wiring
before going live.

Converted from cookbook example: 25_validate_explain.py

Usage:
    cd examples
    adk web validate_explain
"""

from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Build a multi-stage insurance claims pipeline
claims_pipeline = (
    Agent("intake_agent")
    .model("gemini-2.5-flash")
    .instruct("Receive and log the incoming insurance claim with policy number and incident details.")
    .describe("Front-desk claim intake")
    .writes("claim_data")
    >> Agent("adjuster")
    .model("gemini-2.5-flash")
    .instruct("Assess the claim: verify coverage, estimate damages, and recommend payout.")
    .describe("Claims adjuster")
    .writes("assessment")
    >> Agent("reviewer")
    .model("gemini-2.5-flash")
    .instruct("Review the adjuster's assessment for accuracy and compliance with policy terms.")
    .describe("Senior reviewer")
)

# 1. validate() -- check configuration before building
intake = Agent("intake_agent").model("gemini-2.5-flash").instruct("Receive claims.")
validation = intake.validate()

# 2. show() -- human-readable summary for team review
explanation = claims_pipeline.show()

# 3. show("plain") -- full config values for debugging
inspection = claims_pipeline.show("plain")

# 4. Copy-on-write -- frozen builders fork safely
base = Agent("agent").model("gemini-2.5-flash").instruct("Base instruction.")
variant_a = base >> Agent("downstream_a")  # base is now frozen
variant_b = base.instruct("Modified instruction.")  # forks a new clone

root_agent = variant_b.build()
