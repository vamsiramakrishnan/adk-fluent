"""
Delegate Pattern: LLM-Driven Routing

Converted from cookbook example: 27_agent_tool_pattern.py

Usage:
    cd examples
    adk web agent_tool_pattern
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

math = Agent("math_expert").model("gemini-2.5-flash").instruct("You solve math problems step by step.")
code = Agent("code_expert").model("gemini-2.5-flash").instruct("You write Python code.")

# .agent_tool() wraps each agent as AgentTool — the coordinator's LLM
# decides when to agent_tool (LLM-driven routing, unlike Route which is deterministic)
coordinator_fluent = (
    Agent("coordinator")
    .model("gemini-2.5-flash")
    .instruct("Route tasks to the right specialist.")
    .agent_tool(math)
    .agent_tool(code)
)

root_agent = coordinator_fluent.build()
