"""Serialization: to_dict, from_dict, to_yaml"""

# --- NATIVE ---
# Native ADK agents are Pydantic models with model_dump(), but this
# serializes the BUILT agent, not the builder configuration.
# There's no way to reconstruct a builder from a serialized agent.

# --- FLUENT ---
from adk_fluent import Agent

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

# --- ASSERT ---
# to_dict produces expected structure
assert data["_type"] == "Agent"
assert data["config"]["name"] == "classifier"
assert data["config"]["model"] == "gemini-2.5-flash"
assert data["config"]["instruction"] == "Classify inputs into categories."
assert data["config"]["output_key"] == "category"

# from_dict restores config
assert restored._config["name"] == "classifier"
assert restored._config["model"] == "gemini-2.5-flash"

# YAML roundtrip
assert "classifier" in yaml_str
assert "gemini-2.5-flash" in yaml_str
assert from_yaml._config["name"] == "classifier"
