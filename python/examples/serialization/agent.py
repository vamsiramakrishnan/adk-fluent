"""
Deployment Pipeline: Serialize Agent Configs with to_dict and to_yaml

Converted from cookbook example: 26_serialization.py

Usage:
    cd examples
    adk web serialization
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# A ticket routing agent used in a customer support deployment pipeline.
# The DevOps team serializes configs for version control and review.
ticket_router = (
    Agent("ticket_router")
    .model("gemini-2.5-flash")
    .instruct(
        "Classify incoming support tickets by urgency (P0-P3) and "
        "route to the appropriate engineering team based on the product area."
    )
    .writes("routing_decision")
)

# Serialize to dict — inspect config in deployment dashboards
config_snapshot = ticket_router.to_dict()

# Serialize to YAML — store in version control alongside infrastructure code
yaml_manifest = ticket_router.to_yaml()

root_agent = yaml_manifest.build()
