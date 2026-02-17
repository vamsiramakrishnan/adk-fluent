"""
Map Over: Iterate an Agent Over List Items

Converted from cookbook example: 39_map_over.py

Usage:
    cd examples
    adk web map_over
"""

from adk_fluent import Agent, Pipeline, map_over
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# map_over(): iterate an agent over each item in a state list
# For each item in state["documents"], runs the summarizer agent
mapper = map_over(
    "documents",
    Agent("summarizer").model("gemini-2.5-flash").instruct("Summarize the document in _item."),
    output_key="summaries",
)

# Custom item_key and output_key
custom_mapper = map_over(
    "emails",
    Agent("classifier").model("gemini-2.5-flash").instruct("Classify the email in _current."),
    item_key="_current",
    output_key="classifications",
)

# map_over in a pipeline
pipeline = (
    Agent("fetcher").model("gemini-2.5-flash").instruct("Fetch documents.").outputs("documents")
    >> map_over("documents", Agent("summarizer").model("gemini-2.5-flash").instruct("Summarize."))
    >> Agent("compiler").model("gemini-2.5-flash").instruct("Compile summaries.")
)

root_agent = pipeline.build()
