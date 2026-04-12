"""
Customer Onboarding: Conditional Loops with * until(pred) Operator

Real-world use case: Customer onboarding flow that collects required information
iteratively until all fields are complete. Used by fintech and insurance
applications for guided data collection.

In other frameworks: LangGraph requires conditional_edges with a custom routing
function to implement loop-until semantics (~30 lines). adk-fluent uses
* until(predicate) for declarative conditional loops.

Converted from cookbook example: 30_until_operator.py

Usage:
    cd examples
    adk web until_operator
"""

from adk_fluent import Agent, Pipeline, until
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# until() creates a spec for the * operator.
# In a customer onboarding flow, we loop until all verification steps pass.
identity_verified = until(lambda s: s.get("identity_status") == "verified", max=5)

# agent * until(pred) — loop the verification flow until identity is confirmed
onboarding_loop = (
    Agent("document_checker")
    .model("gemini-2.5-flash")
    .instruct("Review the uploaded identity documents for completeness and clarity.")
    .writes("identity_status")
    >> Agent("verification_agent")
    .model("gemini-2.5-flash")
    .instruct("Cross-reference document data against external databases. Report verification status.")
) * identity_verified

# Default max is 10 — used for compliance checks that may take several rounds
compliance_check = (
    Agent("kyc_screener").model("gemini-2.5-flash").instruct("Screen customer against KYC/AML watchlists.")
    >> Agent("risk_assessor")
    .model("gemini-2.5-flash")
    .instruct("Assess customer risk level based on screening results.")
) * until(lambda s: s.get("kyc_clear"))

# Works in larger expressions: full customer onboarding pipeline
full_onboarding = (
    Agent("intake_agent").model("gemini-2.5-flash").instruct("Collect customer information and upload instructions.")
    >> (
        Agent("document_validator")
        .model("gemini-2.5-flash")
        .instruct("Validate documents meet format and quality requirements.")
        >> Agent("identity_verifier")
        .model("gemini-2.5-flash")
        .instruct("Verify identity using biometric and document matching.")
    )
    * until(lambda s: s.get("verification_passed"), max=3)
    >> Agent("welcome_agent").model("gemini-2.5-flash").instruct("Send welcome package and account activation details.")
)

# int * agent still works — fixed retry count for simple cases
document_retry = Agent("doc_requester").model("gemini-2.5-flash").instruct("Request missing documents.") * 3

root_agent = document_retry.build()
