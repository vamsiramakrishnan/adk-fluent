"""
Enterprise Agent with Shared Compliance Preset

Converted from cookbook example: 22_presets.py

Usage:
    cd examples
    adk web presets
"""

from adk_fluent import Agent
from adk_fluent.presets import Preset
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


def audit_before_model(callback_context, llm_request):
    """Log all LLM requests for SOC2 compliance audit trail."""
    pass


def audit_after_model(callback_context, llm_response):
    """Log all LLM responses for compliance review."""
    pass


# Define a reusable compliance preset for all enterprise agents
compliance = Preset(
    model="gemini-2.5-flash",
    before_model=audit_before_model,
    after_model=audit_after_model,
)

# Apply the preset to multiple domain-specific agents with .use()
billing_agent = (
    Agent("billing_agent").instruct("Handle billing inquiries, invoices, and payment disputes.").use(compliance)
)

hr_agent = (
    Agent("hr_agent").instruct("Answer employee questions about benefits, PTO, and company policies.").use(compliance)
)

root_agent = hr_agent.build()
