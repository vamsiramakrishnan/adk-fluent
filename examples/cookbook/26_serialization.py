"""Deployment Pipeline: Serialize Agent Configs with to_dict and to_yaml"""

# --- NATIVE ---
# Native ADK agents are Pydantic models with model_dump(), but this
# serializes the BUILT agent, not the builder configuration.
# In a CI/CD pipeline, you want to inspect and version-control the
# builder config — not the runtime object. There's no way to
# reconstruct a builder from a serialized native agent.

# --- FLUENT ---
from adk_fluent import Agent

# A ticket routing agent used in a customer support deployment pipeline.
# The DevOps team serializes configs for version control and review.
ticket_router = (
    Agent("ticket_router")
    .model("gemini-2.5-flash")
    .instruct(
        "Classify incoming support tickets by urgency (P0-P3) and "
        "route to the appropriate engineering team based on the product area."
    )
    .output_key("routing_decision")
)

# Serialize to dict — inspect config in deployment dashboards
config_snapshot = ticket_router.to_dict()

# Serialize to YAML — store in version control alongside infrastructure code
yaml_manifest = ticket_router.to_yaml()

# --- ASSERT ---
# to_dict produces expected structure matching the deployment config
assert config_snapshot["_type"] == "Agent"
assert config_snapshot["config"]["name"] == "ticket_router"
assert config_snapshot["config"]["model"] == "gemini-2.5-flash"
assert "urgency" in config_snapshot["config"]["instruction"]
assert config_snapshot["config"]["output_key"] == "routing_decision"

# Internal fields are excluded from serialized output (security)
ticket_router._config["_internal"] = "db_connection_string"
clean = ticket_router.to_dict()
assert "_internal" not in clean["config"]

# YAML contains human-readable config for code review
assert "ticket_router" in yaml_manifest
assert "gemini-2.5-flash" in yaml_manifest

# from_dict and from_yaml were removed: callables can't round-trip
assert not hasattr(Agent, "from_dict")
assert not hasattr(Agent, "from_yaml")
