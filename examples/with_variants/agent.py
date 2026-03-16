"""
A/B Prompt Testing for Marketing Copy with .with_()

Converted from cookbook example: 23_with_variants.py

Usage:
    cd examples
    adk web with_variants
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Base marketing copywriter agent
base_copywriter = (
    Agent("copywriter")
    .model("gemini-2.5-flash")
    .instruct("Write compelling marketing copy for product launches. Focus on benefits, not features.")
)

# with_() creates independent copies with overrides -- perfect for A/B testing
variant_a = base_copywriter.with_(
    name="copywriter_formal",
    instruct="Write formal, authoritative marketing copy for enterprise products. "
    "Use data-driven language and industry terminology.",
)
variant_b = base_copywriter.with_(
    name="copywriter_casual",
    instruct="Write casual, conversational marketing copy for consumer products. Use humor and relatable language.",
)

# Original is unchanged -- variants are fully independent
assert base_copywriter._config["name"] == "copywriter"
assert base_copywriter._config["model"] == "gemini-2.5-flash"

root_agent = variant_b.build()
