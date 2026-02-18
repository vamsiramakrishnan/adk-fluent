"""
Presets: Reusable Configuration Bundles

Converted from cookbook example: 22_presets.py

Usage:
    cd examples
    adk web presets
"""

from adk_fluent import Agent
from adk_fluent.presets import Preset
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


def log_before(callback_context, llm_request):
    """Log before model calls."""
    pass


def log_after(callback_context, llm_response):
    """Log after model calls."""
    pass


# Define reusable presets
production = Preset(
    model="gemini-2.5-flash",
    before_model=log_before,
    after_model=log_after,
)

# Apply to any builder with .use()
agent_a = Agent("service_a").instruct("Handle service A requests.").use(production)

agent_b = Agent("service_b").instruct("Handle service B requests.").use(production)

root_agent = agent_b.build()
