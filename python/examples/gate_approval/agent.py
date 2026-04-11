"""
Gate: Legal Document Review with Human Approval

Converted from cookbook example: 41_gate_approval.py

Usage:
    cd examples
    adk web gate_approval
"""

from adk_fluent import Agent, Pipeline, gate
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Scenario: A legal document review pipeline where AI drafts contracts,
# but high-risk clauses require human attorney sign-off before finalization.

# gate(): pause pipeline when condition is met, wait for human approval
contract_pipeline = (
    Agent("clause_analyzer")
    .model("gemini-2.5-flash")
    .instruct("Analyze the contract clauses and assess liability risk level.")
    .writes("liability_risk")
    >> gate(
        lambda s: s.get("liability_risk") == "high",
        message="High liability risk detected. Senior counsel approval required before proceeding.",
    )
    >> Agent("contract_finalizer").model("gemini-2.5-flash").instruct("Finalize the contract with approved terms.")
)

# Custom gate key for tracking specific approval states
compliance_review = (
    Agent("compliance_checker").model("gemini-2.5-flash").instruct("Check regulatory compliance of the proposed terms.")
    >> gate(
        lambda s: True,
        message="Compliance officer must review before filing.",
        gate_key="_compliance_gate",
    )
    >> Agent("filing_agent")
    .model("gemini-2.5-flash")
    .instruct("File the approved documents with the regulatory authority.")
)

# Multiple gates in a pipeline -- multi-stage legal review
multi_stage_review = (
    Agent("contract_drafter").model("gemini-2.5-flash").instruct("Draft the merger agreement based on term sheet.")
    >> gate(
        lambda s: s.get("deal_value_usd", 0) > 10_000_000,
        message="Deal exceeds $10M threshold. Board approval required.",
    )
    >> Agent("risk_disclosures")
    .model("gemini-2.5-flash")
    .instruct("Generate required risk disclosures for the agreement.")
    >> gate(
        lambda s: s.get("cross_border") == "yes",
        message="Cross-border deal requires international counsel sign-off.",
    )
)

root_agent = multi_stage_review.build()
