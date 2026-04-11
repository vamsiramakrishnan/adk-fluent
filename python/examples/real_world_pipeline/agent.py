"""
Investment Analysis Pipeline: Full Expression Language in Production

Real-world use case: Investment analysis pipeline for portfolio managers.
Classifies assets, routes to specialized analysts, and performs quality
review before delivery. Replaces manual triage and review cycles that
typically span multiple teams and days of back-and-forth.

In other frameworks: LangGraph requires StateGraph with conditional_edges
for routing (~50 lines). adk-fluent uses Route() and >> to express the
same topology declaratively.

Pipeline topology:
    asset_classifier
        >> Route("asset_class")
            ├─ "equity"       -> equity_screener
            ├─ "fixed_income" -> credit_analyst >> rate_modeler
            └─ "alternative"  -> ( quant_modeler | market_sentiment ) >> risk_aggregator
        >> ( portfolio_reviewer >> analysis_refiner ) * until(approved)
        >> report_generator  [gated: only if approved]

Converted from cookbook example: 28_real_world_pipeline.py

Usage:
    cd examples
    adk web real_world_pipeline
"""

from adk_fluent import Agent, Pipeline
from adk_fluent._routing import Route
from adk_fluent.presets import Preset
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)


# Shared production preset — every agent in the pipeline logs for compliance
def compliance_log(callback_context, llm_response):
    """Log all model responses for SEC/FINRA audit trail."""
    pass


production = Preset(model="gemini-2.5-flash", after_model=compliance_log)

# Step 1: Classify the investment request by asset class
asset_classifier = (
    Agent("asset_classifier")
    .instruct(
        "Classify the investment request into one of: 'equity', 'fixed_income', "
        "or 'alternative'. Consider the asset type, risk profile, and market context."
    )
    .writes("asset_class")
    .use(production)
)

# Step 2: Route to the appropriate analysis team
equity_analysis = (
    Agent("equity_screener")
    .instruct("Screen equities using fundamental analysis: P/E ratio, revenue growth, moat.")
    .use(production)
)

fixed_income_analysis = Agent("credit_analyst").instruct("Analyze credit risk, yield curves, and duration.").use(
    production
) >> Agent("rate_modeler").instruct("Model interest rate scenarios and their impact on bond prices.").use(production)

alternative_analysis = (
    Agent("quant_modeler").instruct("Build quantitative models for alternative assets.").use(production)
    | Agent("market_sentiment").instruct("Analyze market sentiment from news and social media.").use(production)
) >> Agent("risk_aggregator").instruct("Aggregate risk factors from quantitative and sentiment analysis.").use(
    production
)

# Step 3: Quality review loop — portfolio manager reviews until satisfied
quality_review = (
    Agent("portfolio_reviewer")
    .instruct("Review the investment analysis for completeness and accuracy. Rate quality.")
    .writes("review_quality")
    .use(production)
    >> Agent("analysis_refiner")
    .instruct("Refine the analysis based on reviewer feedback. Address gaps.")
    .use(production)
).loop_until(lambda s: s.get("review_quality") == "approved", max_iterations=3)

# Step 4: Generate client-ready report (only if approved)
report_generator = (
    Agent("report_generator")
    .instruct(
        "Generate a client-ready investment memo with executive summary, "
        "thesis, risks, and recommended position sizing."
    )
    .proceed_if(lambda s: s.get("review_quality") == "approved")
    .use(production)
)

# Compose the full investment analysis pipeline
pipeline = (
    asset_classifier
    >> Route("asset_class")
    .eq("equity", equity_analysis)
    .eq("fixed_income", fixed_income_analysis)
    .eq("alternative", alternative_analysis)
    >> quality_review
    >> report_generator
)

root_agent = pipeline.build()
