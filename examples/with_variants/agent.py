"""
Immutable Variants with .with_()

Converted from cookbook example: 23_with_variants.py

Usage:
    cd examples
    adk web with_variants
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

base = (
    Agent("assistant")
    .model("gemini-2.5-flash")
    .instruct("You are a helpful assistant.")
)

# with_() creates an independent copy with overrides
creative = base.with_(name="creative", model="gemini-2.5-pro")
fast = base.with_(name="fast", instruct="You are fast and concise.")

# Original is unchanged
assert base._config["name"] == "assistant"
assert base._config["model"] == "gemini-2.5-flash"

root_agent = fast.build()
