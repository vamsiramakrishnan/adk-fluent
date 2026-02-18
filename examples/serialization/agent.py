"""
Serialization: to_dict, to_yaml (Inspection Only)

Converted from cookbook example: 26_serialization.py

Usage:
    cd examples
    adk web serialization
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

agent = (
    Agent("classifier").model("gemini-2.5-flash").instruct("Classify inputs into categories.").output_key("category")
)

# Serialize to dict (inspection only -- callables can't round-trip)
data = agent.to_dict()

# Serialize to YAML
yaml_str = agent.to_yaml()

root_agent = agent.build()
