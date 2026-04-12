"""
Senior Architect Delegates to Junior Specialists (LLM-Driven Routing)

Converted from cookbook example: 27_agent_tool_pattern.py

Usage:
    cd examples
    adk web agent_tool_pattern
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Junior specialists — each focused on a specific domain
db_expert = (
    Agent("database_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a database architecture specialist. Design schemas, "
        "optimize queries, and recommend indexing strategies."
    )
)

frontend_expert = (
    Agent("frontend_specialist")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a frontend architecture specialist. Design component "
        "hierarchies, state management patterns, and performance optimizations."
    )
)

# .agent_tool() wraps each agent as AgentTool — the senior architect's LLM
# decides when to agent_tool (LLM-driven routing, unlike Route which is deterministic)
senior_architect = (
    Agent("senior_architect")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a senior software architect. Analyze incoming architecture "
        "requests and agent_tool to the appropriate specialist based on the "
        "technical domain involved."
    )
    .agent_tool(db_expert)
    .agent_tool(frontend_expert)
)

root_agent = senior_architect.build()
