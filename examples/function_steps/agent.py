"""
Function Steps: Plain Functions as Workflow Nodes (>> fn)

Converted from cookbook example: 29_function_steps.py

Usage:
    cd examples
    adk web function_steps
"""

from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


# Plain function — receives state dict, returns dict of updates
def merge_research(state):
    return {"research": state.get("web_results", "") + "\n" + state.get("paper_results", "")}


# >> fn: function becomes a zero-cost workflow node (no LLM call)
pipeline_fluent = (
    Agent("researcher").model("gemini-2.5-flash").instruct("Research.")
    >> merge_research
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write.")
)


# Named functions keep their name as the agent name
def trim_to_500(state):
    return {"summary": state.get("text", "")[:500]}


trimmed = Agent("a").model("gemini-2.5-flash") >> trim_to_500

# Lambdas get auto-generated names (fn_step_N)
pipeline_with_lambda = (
    Agent("a").model("gemini-2.5-flash")
    >> (lambda s: {"upper": s.get("text", "").upper()})
    >> Agent("b").model("gemini-2.5-flash")
)


# fn >> agent also works (via __rrshift__)
def preprocess(s):
    return {"cleaned": s.get("raw", "").strip()}


reversed_pipeline = preprocess >> Agent("processor").model("gemini-2.5-flash")

root_agent = reversed_pipeline.build()
