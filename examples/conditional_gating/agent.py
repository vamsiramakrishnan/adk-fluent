"""
Fraud Detection Pipeline with Conditional Gating

Converted from cookbook example: 19_conditional_gating.py

Usage:
    cd examples
    adk web conditional_gating
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# proceed_if: the fraud investigator only runs for high-risk transactions
fraud_investigator = (
    Agent("fraud_investigator")
    .model("gemini-2.5-flash")
    .instruct(
        "Perform deep fraud investigation. Check transaction patterns, "
        "verify merchant history, and flag suspicious activity."
    )
    .proceed_if(lambda s: s.get("risk_level") == "high")
)

# Full fraud detection pipeline:
# 1. Score the transaction risk
# 2. Only investigate if risk is high
# 3. Only notify compliance if investigation found fraud
risk_scorer = (
    Agent("risk_scorer")
    .model("gemini-2.5-flash")
    .instruct("Analyze the transaction and assign a risk level: 'low', 'medium', or 'high'.")
    .writes("risk_level")
)

compliance_notifier = (
    Agent("compliance_notifier")
    .model("gemini-2.5-flash")
    .instruct("Generate a compliance report and notify the fraud team.")
    .proceed_if(lambda s: s.get("fraud_confirmed") == "yes")
)

pipeline = risk_scorer >> fraud_investigator >> compliance_notifier

root_agent = pipeline.build()
