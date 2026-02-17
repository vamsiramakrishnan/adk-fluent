"""
Race: First-to-Finish Wins

Converted from cookbook example: 42_race.py

Usage:
    cd examples
    adk web race
"""

from adk_fluent import Agent, Pipeline, race
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# race(): run agents concurrently, keep only the first to finish
# Perfect for: fastest model wins, parallel strategies, timeout fallbacks
fast = Agent("fast").model("gemini-2.0-flash").instruct("Quick answer.")
thorough = Agent("thorough").model("gemini-2.5-pro").instruct("Detailed answer.")

winner = race(fast, thorough)

# Three-way race
creative = Agent("creative").model("gemini-2.5-flash-lite").instruct("Creative answer.")
precise = Agent("precise").model("gemini-2.5-flash").instruct("Precise answer.")
concise = Agent("concise").model("gemini-2.0-flash").instruct("Brief answer.")

best_first = race(creative, precise, concise)

# Race in a pipeline
pipeline = (
    Agent("classifier").model("gemini-2.5-flash").instruct("Classify.")
    >> race(
        Agent("strategy_a").model("gemini-2.5-flash").instruct("Strategy A."),
        Agent("strategy_b").model("gemini-2.5-flash").instruct("Strategy B."),
    )
    >> Agent("formatter").model("gemini-2.5-flash").instruct("Format result.")
)

root_agent = pipeline.build()
