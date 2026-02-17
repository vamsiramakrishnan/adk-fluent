"""
Agent Cloning with .clone()

Converted from cookbook example: 10_cloning.py

Usage:
    cd examples
    adk web cloning
"""

from adk_fluent import Agent
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

base = Agent("base").model("gemini-2.5-flash").instruct("Be helpful.")

math_agent = base.clone("math").instruct("Solve math problems.")
code_agent = base.clone("code").instruct("Write Python code.")

root_agent = code_agent.build()
