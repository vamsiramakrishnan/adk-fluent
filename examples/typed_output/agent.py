"""
Typed Output Contracts: @ Operator

Converted from cookbook example: 31_typed_output.py

Usage:
    cd examples
    adk web typed_output
"""

from pydantic import BaseModel

# --- Tools & Callbacks ---


class ReportSchema(BaseModel):
    title: str
    body: str
    confidence: float


from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# @ binds a Pydantic model as the output schema
writer_fluent = Agent("writer").model("gemini-2.5-flash").instruct("Write a report.") @ ReportSchema

# @ is immutable — original unchanged
base = Agent("base").model("gemini-2.5-flash").instruct("Analyze.")
typed = base @ ReportSchema
# base has no schema, typed does


class SummarySchema(BaseModel):
    summary: str
    key_points: list[str]


# Composes with >> — typed agent feeds into pipeline
pipeline = (
    Agent("researcher").model("gemini-2.5-flash").instruct("Research the topic.")
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write summary.") @ SummarySchema
    >> Agent("editor").model("gemini-2.5-flash").instruct("Polish the summary.")
)

# @ preserves all existing config
detailed = (
    Agent("analyst").model("gemini-2.5-flash").instruct("Analyze data thoroughly.").outputs("analysis") @ ReportSchema
)

root_agent = detailed.build()
