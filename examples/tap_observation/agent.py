"""
Tap: Pure Observation Steps (No State Mutation)

Converted from cookbook example: 35_tap_observation.py

Usage:
    cd examples
    adk web tap_observation
"""

from adk_fluent import Agent, Pipeline, tap
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# tap(): creates a pure observation step -- reads state, never mutates
# Perfect for logging, metrics, debugging
pipeline_fluent = (
    Agent("researcher").model("gemini-2.5-flash").instruct("Research.")
    >> tap(lambda s: print("State after research:", s))
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write.")
)


# Named functions keep their name
def log_draft(state):
    print(f"Draft length: {len(state.get('draft', ''))}")


pipeline_with_named_tap = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write a draft.")
    >> tap(log_draft)
    >> Agent("editor").model("gemini-2.5-flash").instruct("Edit the draft.")
)

# .tap() method on any builder -- convenience for inline chaining
pipeline_method = Agent("analyzer").model("gemini-2.5-flash").instruct("Analyze.").tap(lambda s: print("Analysis done"))

root_agent = pipeline_method.build()
