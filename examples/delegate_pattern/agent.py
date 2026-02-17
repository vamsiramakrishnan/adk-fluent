"""
Delegate Pattern: LLM-Driven Routing

Converted from cookbook example: 27_delegate_pattern.py

Usage:
    cd examples
    adk web delegate_pattern
"""

from adk_fluent import Agent

math = Agent("math_expert").model("gemini-2.5-flash").instruct("You solve math problems step by step.")
code = Agent("code_expert").model("gemini-2.5-flash").instruct("You write Python code.")

# .delegate() wraps each agent as AgentTool — the coordinator's LLM
# decides when to delegate (LLM-driven routing, unlike Route which is deterministic)
coordinator_fluent = (
    Agent("coordinator")
    .model("gemini-2.5-flash")
    .instruct("Route tasks to the right specialist.")
    .delegate(math)
    .delegate(code)
)

root_agent = coordinator_fluent.build()
