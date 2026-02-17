"""
Serialization: to_dict, from_dict, to_yaml

Converted from cookbook example: 26_serialization.py

Usage:
    cd examples
    adk web serialization
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

agent = (
    Agent("classifier")
    .model("gemini-2.5-flash")
    .instruct("Classify inputs into categories.")
    .output_key("category")
)

# Serialize to dict
data = agent.to_dict()

# Reconstruct from dict (config only, not callables)
restored = Agent.from_dict(data)

# Serialize to YAML
yaml_str = agent.to_yaml()

# Reconstruct from YAML
from_yaml = Agent.from_yaml(yaml_str)

root_agent = agent.build()
