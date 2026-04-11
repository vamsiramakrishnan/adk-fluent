"""ETL Pipeline: Plain Functions as Data Cleaning Steps (>> fn)"""

# --- NATIVE ---
# Native ADK requires subclassing BaseAgent for any custom logic node.
# In an ETL pipeline, every data cleaning step becomes a full class:
from google.adk.agents.base_agent import BaseAgent as NativeBaseAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent


class NormalizeCurrency(NativeBaseAgent):
    """Custom agent just to normalize currency values to USD."""

    async def _run_async_impl(self, ctx):
        raw = ctx.session.state.get("raw_amounts", "")
        # Strip currency symbols and normalize
        cleaned = raw.replace("$", "").replace(",", "").strip()
        ctx.session.state["normalized_amounts"] = cleaned
        # yield nothing


extractor = LlmAgent(name="extractor", model="gemini-2.5-flash", instruction="Extract financial data.")
normalizer = NormalizeCurrency(name="normalize_currency")
loader = LlmAgent(name="loader", model="gemini-2.5-flash", instruction="Load into report.")

pipeline_native = SequentialAgent(name="etl_pipeline", sub_agents=[extractor, normalizer, loader])

# --- FLUENT ---
from adk_fluent import Agent, Pipeline


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

# --- ASSERT ---
# >> fn creates a Pipeline
assert isinstance(etl_pipeline, Pipeline)
built = etl_pipeline.build()
assert len(built.sub_agents) == 3

# Named functions use their name
built_trimmed = trimmed.build()
assert built_trimmed.sub_agents[1].name == "truncate_to_limit"

# Lambda gets a valid identifier name
built_lambda = pipeline_with_lambda.build()
name = built_lambda.sub_agents[1].name
assert name.isidentifier()  # Not "<lambda>"

# fn >> agent works
assert isinstance(preprocess_pipeline, Pipeline)
built_rev = preprocess_pipeline.build()
assert len(built_rev.sub_agents) == 2
