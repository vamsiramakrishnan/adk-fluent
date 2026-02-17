"""
Team Coordinator Pattern

Converted from cookbook example: 07_team_coordinator.py

Usage:
    cd examples
    adk web team_coordinator
"""

from adk_fluent import Agent

coordinator_fluent = (
    Agent("team_lead")
    .model("gemini-2.5-flash")
    .instruct("Coordinate the team. Delegate to the right member.")
    .member(Agent("frontend").model("gemini-2.5-flash").instruct("Build UI."))
    .member(Agent("backend").model("gemini-2.5-flash").instruct("Build APIs."))
    .build()
)

root_agent = coordinator_fluent
