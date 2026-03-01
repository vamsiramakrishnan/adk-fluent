"""
Insurance Claim Processing: Structured Data Pipelines

Demonstrates structured output schemas and the @ operator for typed
agent responses.  The scenario: an insurance company processes claims
through a pipeline -- first ingesting claim details into a structured
form, then assessing risk, then summarizing the outcome.

Converted from cookbook example: 53_structured_schemas.py

Usage:
    cd examples
    adk web structured_schemas
"""


# --- Tools & Callbacks ---

from pydantic import BaseModel


class ClaimIntake(BaseModel):
    claimant_name: str
    policy_number: str
    incident_date: str
    description: str


class RiskAssessment(BaseModel):
    risk_level: str
    flags: list[str]
    recommended_action: str


from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Explicit builder chain: .returns() + .writes()
intake_fluent = (
    Agent("intake_agent")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a claims intake specialist. Extract the claimant name, "
        "policy number, incident date, and description from the raw "
        "claim submission. Return structured JSON only."
    )
    .returns(ClaimIntake)
    .writes("intake_data")
)

risk_fluent = (
    Agent("risk_agent")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a risk assessor. Analyze the claim intake data and "
        "determine the risk level (low/medium/high), any red flags, "
        "and a recommended action (approve/investigate/deny)."
    )
    .returns(RiskAssessment)
    .writes("risk_report")
)

# The @ operator -- shorthand for .returns() in expressions
base_agent = (
    Agent("intake_agent").model("gemini-2.5-flash").instruct("Extract claim details and return structured JSON.")
)
typed_agent = base_agent @ ClaimIntake  # immutable: returns a new builder

# Full pipeline using >> operator
summary_agent = (
    Agent("summary_agent")
    .model("gemini-2.5-flash")
    .instruct("Produce a plain-language summary of the claim and its risk assessment for the claims adjuster.")
)
pipeline = intake_fluent >> risk_fluent >> summary_agent

root_agent = pipeline.build()
