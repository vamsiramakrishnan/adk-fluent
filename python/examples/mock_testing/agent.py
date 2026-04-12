"""
Mock Testing: Customer Onboarding Pipeline with Deterministic Mocks

Converted from cookbook example: 37_mock_testing.py

Usage:
    cd examples
    adk web mock_testing
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Scenario: Customer onboarding pipeline with three stages:
#   1. KYC verification -- checks identity documents
#   2. Risk assessment -- evaluates financial risk profile
#   3. Account provisioning -- creates the customer account

# .mock(list): cycle through scripted responses for repeatable tests
kyc_verifier = (
    Agent("kyc_verifier")
    .model("gemini-2.5-flash")
    .instruct("Verify the customer's identity documents and return approval status.")
    .writes("kyc_status")
    .mock(["KYC: approved", "KYC: pending review"])
)

# .mock(callable): dynamic responses based on the LLM request context
risk_assessor = (
    Agent("risk_assessor")
    .model("gemini-2.5-flash")
    .instruct("Evaluate the customer's financial risk profile.")
    .writes("risk_level")
    .mock(lambda req: "risk_level: low")
)

# Chainable -- .mock() returns self so it composes with other builder methods
account_provisioner = (
    Agent("account_provisioner")
    .model("gemini-2.5-flash")
    .mock(["Account ACT-10042 created successfully."])
    .instruct("Provision a new bank account for the approved customer.")
    .writes("account_id")
)

# Full onboarding pipeline with all agents mocked for integration testing
onboarding_pipeline = kyc_verifier >> risk_assessor >> account_provisioner

root_agent = onboarding_pipeline.build()
