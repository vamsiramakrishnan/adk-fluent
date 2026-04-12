"""
Domain Expert Agent via @agent Decorator

Converted from cookbook example: 24_agent_decorator.py

Usage:
    cd examples
    adk web agent_decorator
"""

from adk_fluent.decorators import agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


@agent("pharma_advisor", model="gemini-2.5-flash")
def pharma_advisor():
    """You are a pharmaceutical advisor. Help healthcare professionals check drug interactions and dosage guidelines."""
    pass


@pharma_advisor.tool
def lookup_drug_interaction(drug_a: str, drug_b: str) -> str:
    """Check for known interactions between two drugs."""
    return f"Checking interaction between {drug_a} and {drug_b}"


@pharma_advisor.on("before_model")
def log_query(callback_context, llm_request):
    """Log every query for regulatory compliance."""
    pass


# The decorator returns a builder, not a built agent.
# Build when ready to deploy:
built = pharma_advisor.build()

root_agent = built
