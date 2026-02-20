"""Insurance Claim Processing: Structured Data Pipelines

Demonstrates structured output schemas and the @ operator for typed
agent responses.  The scenario: an insurance company processes claims
through a pipeline -- first ingesting claim details into a structured
form, then assessing risk, then summarizing the outcome.
"""

# --- NATIVE ---
from pydantic import BaseModel
from google.adk.agents.llm_agent import LlmAgent

class ClaimIntake(BaseModel):
    claimant_name: str
    policy_number: str
    incident_date: str
    description: str

class RiskAssessment(BaseModel):
    risk_level: str
    flags: list[str]
    recommended_action: str

intake_native = LlmAgent(
    name="intake_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a claims intake specialist. Extract the claimant name, "
        "policy number, incident date, and description from the raw "
        "claim submission. Return structured JSON only."
    ),
    output_schema=ClaimIntake,
    output_key="intake_data",
)

risk_native = LlmAgent(
    name="risk_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a risk assessor. Analyze the claim intake data and "
        "determine the risk level (low/medium/high), any red flags, "
        "and a recommended action (approve/investigate/deny)."
    ),
    output_schema=RiskAssessment,
    output_key="risk_report",
)

# --- FLUENT ---
from adk_fluent import Agent, Pipeline

# Explicit builder chain: .output_schema() + .outputs()
intake_fluent = (
    Agent("intake_agent")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a claims intake specialist. Extract the claimant name, "
        "policy number, incident date, and description from the raw "
        "claim submission. Return structured JSON only."
    )
    .output_schema(ClaimIntake)
    .outputs("intake_data")
)

risk_fluent = (
    Agent("risk_agent")
    .model("gemini-2.5-flash")
    .instruct(
        "You are a risk assessor. Analyze the claim intake data and "
        "determine the risk level (low/medium/high), any red flags, "
        "and a recommended action (approve/investigate/deny)."
    )
    .output_schema(RiskAssessment)
    .outputs("risk_report")
)

# The @ operator -- shorthand for .output_schema() in expressions
base_agent = Agent("intake_agent").model("gemini-2.5-flash").instruct(
    "Extract claim details and return structured JSON."
)
typed_agent = base_agent @ ClaimIntake  # immutable: returns a new builder

# Full pipeline using >> operator
summary_agent = (
    Agent("summary_agent")
    .model("gemini-2.5-flash")
    .instruct(
        "Produce a plain-language summary of the claim and its risk "
        "assessment for the claims adjuster."
    )
)
pipeline = intake_fluent >> risk_fluent >> summary_agent

# --- ASSERT ---

# 1. output_schema is set correctly via .output_schema()
built_intake = intake_fluent.build()
assert built_intake.output_schema == ClaimIntake
assert built_intake.output_key == "intake_data"

built_risk = risk_fluent.build()
assert built_risk.output_schema == RiskAssessment
assert built_risk.output_key == "risk_report"

# 2. Native and fluent produce equivalent agents
assert type(intake_native) == type(built_intake)
assert intake_native.output_schema == built_intake.output_schema
assert intake_native.output_key == built_intake.output_key

# 3. @ operator sets output_schema on the new builder
built_typed = typed_agent.build()
assert built_typed.output_schema == ClaimIntake

# 4. @ operator is immutable -- original agent is unchanged
built_base = base_agent.build()
assert built_base.output_schema is None

# 5. Pipeline is a Pipeline builder and builds correctly
assert isinstance(pipeline, Pipeline)
built_pipeline = pipeline.build()
assert len(built_pipeline.sub_agents) == 3
assert built_pipeline.sub_agents[0].name == "intake_agent"
assert built_pipeline.sub_agents[1].name == "risk_agent"
assert built_pipeline.sub_agents[2].name == "summary_agent"
