"""
Analytics Data Quality: State Contract Assertions with expect()

Converted from cookbook example: 36_expect_assertions.py

Usage:
    cd examples
    adk web expect_assertions
"""

from adk_fluent import Agent, Pipeline, expect
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

# expect(): assert a state contract at a pipeline step.
# In analytics, data quality gates prevent garbage-in-garbage-out.
analytics_pipeline = (
    Agent("metric_calculator")
    .model("gemini-2.5-flash")
    .instruct("Compute key business metrics: revenue, churn rate, and LTV from raw data.")
    .writes("metrics")
    >> expect(lambda s: "metrics" in s, "Metrics must be computed before dashboard generation")
    >> Agent("dashboard_generator")
    .model("gemini-2.5-flash")
    .instruct("Generate an executive dashboard with charts and insights from the metrics.")
)

# Multiple quality gates in a data pipeline — catch issues at each stage
validated_pipeline = (
    Agent("data_ingester")
    .model("gemini-2.5-flash")
    .instruct("Ingest raw event data from the warehouse and extract user behavior events.")
    >> expect(lambda s: "events" in s, "Ingestion must produce events data")
    >> Agent("aggregator")
    .model("gemini-2.5-flash")
    .instruct("Aggregate events into daily/weekly/monthly cohort metrics.")
    >> expect(lambda s: len(s.get("events", "")) > 0, "Events data must not be empty after aggregation")
    >> Agent("report_builder")
    .model("gemini-2.5-flash")
    .instruct("Build the final analytics report with trend analysis and recommendations.")
)

root_agent = validated_pipeline.build()
