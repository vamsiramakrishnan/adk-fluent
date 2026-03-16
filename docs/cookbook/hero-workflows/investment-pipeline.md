# Investment Analysis Pipeline — Route, Loop, and Conditional Delivery

> **Modules in play:** `Route` deterministic branching, `>>` sequential,
> `|` parallel, `loop_until` quality review, `proceed_if` conditional gating,
> `Preset` shared configuration

## The Real-World Problem

Your portfolio management team handles three asset classes — equities, fixed
income, and alternatives — each requiring different analysis workflows. Today,
a human triages each request to the right team. Fixed income needs a credit
analyst *then* a rate modeler (sequential). Alternatives need a quant modeler
*and* sentiment analyzer running in parallel, then a risk aggregator. After
analysis, a portfolio reviewer iterates until quality is "approved," and only
then does a client-ready report get generated.

You need: instant routing by asset class (no LLM waste), per-class analysis
topologies (sequential, parallel, or hybrid), bounded quality iteration, and
a gated final deliverable.

## The Fluent Solution

```python
from adk_fluent import Agent, Pipeline
from adk_fluent._routing import Route
from adk_fluent.presets import Preset


# Shared preset — every agent logs for SEC/FINRA compliance
def compliance_log(callback_context, llm_response):
    """Audit trail for all model responses."""
    pass

production = Preset(model="gemini-2.5-flash", after_model=compliance_log)

# Step 1: Classify asset type
asset_classifier = (
    Agent("asset_classifier")
    .instruct("Classify as 'equity', 'fixed_income', or 'alternative'.")
    .writes("asset_class")
    .use(production)
)

# Step 2: Per-class analysis topologies
equity_analysis = (
    Agent("equity_screener")
    .instruct("Screen equities: P/E ratio, revenue growth, moat.")
    .use(production)
)

fixed_income_analysis = (
    Agent("credit_analyst")
    .instruct("Analyze credit risk, yield curves, duration.")
    .use(production)
    >> Agent("rate_modeler")
    .instruct("Model interest rate scenarios and bond price impact.")
    .use(production)
)

alternative_analysis = (
    Agent("quant_modeler")
    .instruct("Build quantitative models for alternative assets.")
    .use(production)
    | Agent("market_sentiment")
    .instruct("Analyze sentiment from news and social media.")
    .use(production)
) >> Agent("risk_aggregator").instruct("Aggregate risk factors.").use(production)

# Step 3: Quality review loop — iterate until approved
quality_review = (
    Agent("portfolio_reviewer")
    .instruct("Review for completeness and accuracy. Rate quality.")
    .writes("review_quality")
    .use(production)
    >> Agent("analysis_refiner")
    .instruct("Refine based on feedback. Address gaps.")
    .use(production)
).loop_until(lambda s: s.get("review_quality") == "approved", max_iterations=3)

# Step 4: Generate report ONLY if approved
report_generator = (
    Agent("report_generator")
    .instruct("Generate client-ready investment memo with thesis and risks.")
    .proceed_if(lambda s: s.get("review_quality") == "approved")
    .use(production)
)

# THE SYMPHONY
pipeline = (
    asset_classifier
    >> Route("asset_class")
       .eq("equity", equity_analysis)
       .eq("fixed_income", fixed_income_analysis)
       .eq("alternative", alternative_analysis)
    >> quality_review
    >> report_generator
)
```

## The Interplay Breakdown

**Why `Route()` instead of LLM delegation?**
The classifier already wrote `"equity"` or `"fixed_income"` to state. Sending
that string to another LLM to "decide" which team to call is pure waste.
`Route("asset_class").eq("equity", ...)` dispatches in microseconds with zero
API cost. Adding a new asset class (e.g., "crypto") is one `.eq()` line — no
prompt engineering, no retraining.

**Why different topologies per route?**
Each asset class has a structurally different analysis workflow:
- **Equity**: single screener (one agent)
- **Fixed income**: sequential `>>` — credit analysis *must* precede rate modeling
- **Alternative**: parallel `|` (quant + sentiment) *then* sequential `>>` aggregation

This is impossible in frameworks that force uniform topology. adk-fluent lets
each route branch have its own composition.

**Why `Preset` for compliance?**
Every agent in a financial pipeline needs an audit trail. Without `Preset`,
you'd copy-paste `.model("gemini-2.5-flash").after_model(compliance_log)` on
every single agent. `Preset` applies shared configuration via `.use(production)` —
change the model or logging once, it propagates everywhere.

**Why `loop_until` with `max_iterations=3`?**
Quality review is inherently iterative — some analyses need one pass, others three.
A fixed number of rounds is wasteful or insufficient. `loop_until(approved)`
makes iteration adaptive. The `max_iterations=3` cap prevents the reviewer from
endlessly rejecting, ensuring the pipeline always terminates.

**Why `proceed_if` on the report generator?**
If the review loop exhausts all 3 iterations without approval, generating a
client report would deliver substandard analysis. `proceed_if(approved)` gates
the final deliverable — if not approved after 3 rounds, the pipeline exits
without producing a report, signaling that human intervention is needed.

## Running on Different Backends

::::{tab-set}
:::{tab-item} ADK (default)
```python
response = pipeline.ask("Analyze NVIDIA as a potential portfolio addition")
```
:::
:::{tab-item} Temporal (in dev)
```python
from temporalio.client import Client
client = await Client.connect("localhost:7233")

# Route() is deterministic — replays identically (zero cost)
# Review loop iterations are individually checkpointed
durable = pipeline.engine("temporal", client=client, task_queue="invest")
response = await durable.ask_async("Analyze NVIDIA as a potential portfolio addition")
```
:::
:::{tab-item} asyncio (in dev)
```python
response = await pipeline.engine("asyncio").ask_async("Analyze NVIDIA")
```
:::
::::

## Pipeline Topology

```
asset_classifier ──► Route("asset_class")
                      ├─ "equity"       → equity_screener
                      ├─ "fixed_income" → credit_analyst ──► rate_modeler
                      └─ "alternative"  → (quant_modeler | market_sentiment) ──► risk_aggregator
                     ──► (portfolio_reviewer >> analysis_refiner) * until(approved)
                         ──► report_generator [gated: approved only]
```
