"""Serialization: to_dict, to_yaml (Inspection Only)"""

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

# Serialize to dict (inspection only -- callables can't round-trip)
data = agent.to_dict()

# Serialize to YAML
yaml_str = agent.to_yaml()

# --- ASSERT ---
# to_dict produces expected structure
assert data["_type"] == "Agent"
assert data["config"]["name"] == "classifier"
assert data["config"]["model"] == "gemini-2.5-flash"
assert data["config"]["instruction"] == "Classify inputs into categories."
assert data["config"]["output_key"] == "category"

# Internal fields are excluded
agent._config["_internal"] = "secret"
clean = agent.to_dict()
assert "_internal" not in clean["config"]

# YAML contains the config
assert "classifier" in yaml_str
assert "gemini-2.5-flash" in yaml_str

# from_dict and from_yaml were removed: callables can't round-trip
assert not hasattr(Agent, "from_dict")
assert not hasattr(Agent, "from_yaml")
