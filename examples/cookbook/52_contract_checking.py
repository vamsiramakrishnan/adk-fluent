"""Contract Checking: Catch Data Flow Bugs Before Runtime"""

# --- NATIVE ---
# In native ADK, if Agent B reads {summary} from state but Agent A never
# writes it, you discover this at runtime when the template renders as
# a literal "{summary}" string — or worse, silently produces garbage.
# There's no static analysis to catch these wiring errors.

# --- FLUENT ---
from adk_fluent import Agent, S
from adk_fluent.testing import check_contracts

MODEL = "gemini-2.5-flash"

# === Scenario 1: Valid research pipeline ===
# Researcher outputs "findings" and "sources", writer reads them via {template}.

research_pipeline = Agent("researcher").model(MODEL).instruct(
    "Research the given topic thoroughly. Cite your sources."
).outputs("findings") >> Agent("writer").model(MODEL).instruct(
    "Write a report based on the research.\nFindings: {findings}"
)

valid_issues = check_contracts(research_pipeline.to_ir())
valid_errors = [i for i in valid_issues if isinstance(i, dict) and i.get("level") == "error"]

# === Scenario 2: Broken pipeline — missing upstream output ===
# Summarizer reads {analysis} but nobody writes it.

broken_pipeline = (
    Agent("collector").model(MODEL).instruct("Collect data from available sources.").outputs("raw_data")
    >> Agent("summarizer").model(MODEL).instruct("Summarize the analysis: {analysis}")  # Bug: should be {raw_data}
)

broken_issues = check_contracts(broken_pipeline.to_ir())

# === Scenario 3: Build modes ===

# Default (advisory): logs warnings but doesn't block the build
advisory_built = broken_pipeline.build()

# Strict: raises ValueError on contract errors — use in CI pipelines
strict_built = research_pipeline.strict().build()

# Unchecked: skip contract checking entirely — for prototyping
unchecked_built = broken_pipeline.unchecked().build()

# === Scenario 4: Full pipeline with capture + contracts ===

order_pipeline = (
    S.capture("customer_request")
    >> Agent("parser").model(MODEL).instruct("Parse the order: {customer_request}").outputs("order_details")
    >> Agent("fulfillment").model(MODEL).instruct("Process the parsed order.\nOrder details: {order_details}")
)

order_issues = check_contracts(order_pipeline.to_ir())
order_errors = [i for i in order_issues if isinstance(i, dict) and i.get("level") == "error"]

# --- ASSERT ---
# Valid pipeline passes contract check
assert len(valid_errors) == 0

# Broken pipeline catches the missing {analysis} key
assert len(broken_issues) > 0

# Advisory mode still builds (warnings only)
assert advisory_built is not None

# Strict mode succeeds for valid pipeline
assert strict_built is not None

# Unchecked mode succeeds even with violations
assert unchecked_built is not None

# Full pipeline with capture passes contracts
assert len(order_errors) == 0
