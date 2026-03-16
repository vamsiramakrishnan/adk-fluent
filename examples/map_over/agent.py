"""
Map Over: Batch Processing Customer Feedback with Iteration

Converted from cookbook example: 39_map_over.py

Usage:
    cd examples
    adk web map_over
"""

from adk_fluent import Agent, Pipeline, map_over
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# Scenario: A customer success platform ingests feedback from multiple channels.
# Each feedback entry needs individual sentiment analysis before aggregation.

# map_over(): iterate an agent over each item in a state list
# For each item in state["feedback_entries"], runs the sentiment analyzer
feedback_mapper = map_over(
    "feedback_entries",
    Agent("sentiment_analyzer")
    .model("gemini-2.5-flash")
    .instruct("Analyze the sentiment of the customer feedback in _item. Rate as positive, neutral, or negative."),
    output_key="sentiment_scores",
)

# Custom item_key and output_key for processing support tickets
ticket_mapper = map_over(
    "support_tickets",
    Agent("priority_classifier")
    .model("gemini-2.5-flash")
    .instruct("Classify the urgency of the support ticket in _ticket. Assign P1, P2, or P3."),
    item_key="_ticket",
    output_key="priority_assignments",
)

# map_over in a full feedback processing pipeline:
#   1. Collect feedback from all channels
#   2. Analyze each piece individually
#   3. Generate an executive summary
feedback_pipeline = (
    Agent("feedback_collector")
    .model("gemini-2.5-flash")
    .instruct("Collect customer feedback from all channels.")
    .writes("feedback_entries")
    >> map_over(
        "feedback_entries",
        Agent("sentiment_analyzer").model("gemini-2.5-flash").instruct("Analyze sentiment of this feedback entry."),
    )
    >> Agent("summary_writer")
    .model("gemini-2.5-flash")
    .instruct("Write an executive summary of the sentiment analysis results.")
)

root_agent = feedback_pipeline.build()
