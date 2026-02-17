"""
Agent with Tools

Converted from cookbook example: 02_agent_with_tools.py

Usage:
    cd examples
    adk web agent_with_tools
"""


# --- Tools & Callbacks ---

def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny in {city}"

def get_time(timezone: str) -> str:
    """Get current time."""
    return f"3:00 PM in {timezone}"

from adk_fluent import Agent

agent_fluent = (
    Agent("assistant")
    .model("gemini-2.5-flash")
    .instruct("You help with weather and time.")
    .tool(get_weather)
    .tool(get_time)
    .build()
)

root_agent = agent_fluent
