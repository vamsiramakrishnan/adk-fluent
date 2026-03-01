"""
Guardrails with .guard()

Converted from cookbook example: 12_guards.py

Usage:
    cd examples
    adk web guards
"""


# --- Tools & Callbacks ---


def pii_filter(callback_context, llm_request):
    """Filter PII from requests."""
    return None


from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# One call registers both before and after:
builder = Agent("secure").model("gemini-2.5-flash").instruct("Be secure.").guard(pii_filter)

root_agent = builder.build()
