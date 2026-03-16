"""
Product Launch Coordinator -- Team Coordinator Pattern

Demonstrates an LLM agent that delegates to specialized sub-agents.
The scenario: a product launch coordinator that routes tasks to
marketing, engineering, and legal teams based on the request.

Pipeline topology:
    launch_coordinator
        |-- marketing
        |-- engineering
        '-- legal

Converted from cookbook example: 07_team_coordinator.py

Usage:
    cd examples
    adk web team_coordinator
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

coordinator_fluent = (
    Agent("launch_coordinator")
    .model("gemini-2.5-flash")
    .instruct(
        "You coordinate product launches. Analyze each request and "
        "delegate to the right team: marketing for campaigns and "
        "messaging, engineering for release readiness and deployment, "
        "or legal for compliance and licensing reviews."
    )
    .sub_agent(
        Agent("marketing")
        .model("gemini-2.5-flash")
        .instruct("Draft marketing campaigns, press releases, and social media strategies for the product launch.")
    )
    .sub_agent(
        Agent("engineering")
        .model("gemini-2.5-flash")
        .instruct("Review technical readiness: CI/CD pipelines, load testing results, and deployment checklists.")
    )
    .sub_agent(
        Agent("legal")
        .model("gemini-2.5-flash")
        .instruct(
            "Review licensing terms, privacy compliance (GDPR/CCPA), and terms-of-service updates for the launch."
        )
    )
    .build()
)

root_agent = coordinator_fluent
