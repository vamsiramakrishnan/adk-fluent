"""
ETL Pipeline: Plain Functions as Data Cleaning Steps (>> fn)

Converted from cookbook example: 29_function_steps.py

Usage:
    cd examples
    adk web function_steps
"""

from adk_fluent import Agent, Pipeline
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


# Plain function — receives state dict, returns dict of updates.
# No BaseAgent boilerplate for simple data transformations.
def normalize_currency(state):
    """Strip currency symbols and normalize to plain numbers."""
    raw = state.get("raw_amounts", "")
    cleaned = raw.replace("$", "").replace(",", "").strip()
    return {"normalized_amounts": cleaned}


# >> fn: function becomes a zero-cost workflow node (no LLM call)
etl_pipeline = (
    Agent("financial_extractor")
    .model("gemini-2.5-flash")
    .instruct("Extract financial line items from the uploaded invoice PDF.")
    >> normalize_currency
    >> Agent("report_loader")
    .model("gemini-2.5-flash")
    .instruct("Format the normalized data into a financial summary report.")
)


# Named functions keep their name as the agent name
def truncate_to_limit(state):
    """Enforce a 500-char limit on executive summaries."""
    return {"exec_summary": state.get("text", "")[:500]}


trimmed = Agent("summarizer").model("gemini-2.5-flash") >> truncate_to_limit

# Lambdas get auto-generated names (fn_step_N) — useful for quick transforms
pipeline_with_lambda = (
    Agent("ingester").model("gemini-2.5-flash")
    >> (lambda s: {"upper_title": s.get("title", "").upper()})
    >> Agent("publisher").model("gemini-2.5-flash")
)


# fn >> agent also works (via __rrshift__) — preprocessing before LLM
def sanitize_pii(s):
    """Remove personally identifiable information before LLM processing."""
    return {"cleaned_text": s.get("raw_input", "").strip()}


preprocess_pipeline = sanitize_pii >> Agent("analyzer").model("gemini-2.5-flash")

root_agent = preprocess_pipeline.build()
