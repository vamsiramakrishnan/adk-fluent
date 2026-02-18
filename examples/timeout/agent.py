"""
Timeout: Time-Bound Agent Execution

Converted from cookbook example: 40_timeout.py

Usage:
    cd examples
    adk web timeout
"""

from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# .timeout(seconds): wrap any agent with a time limit
# Raises asyncio.TimeoutError if the agent exceeds the limit
fast_agent = Agent("fast_responder").model("gemini-2.5-flash").instruct("Answer quickly.").timeout(30)

# Timeout in a pipeline -- only the slow step is time-bounded
pipeline = (
    Agent("classifier").model("gemini-2.5-flash").instruct("Classify.")
    >> Agent("researcher").model("gemini-2.5-pro").instruct("Deep research.").timeout(60)
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write summary.")
)

# Timeout on a whole pipeline
bounded_pipeline = (
    Agent("a").model("gemini-2.5-flash").instruct("Step A.") >> Agent("b").model("gemini-2.5-flash").instruct("Step B.")
).timeout(120)

root_agent = bounded_pipeline.build()
