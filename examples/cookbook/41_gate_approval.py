"""Gate: Legal Document Review with Human Approval"""

# --- NATIVE ---
# Native ADK requires a custom BaseAgent with EventActions(escalate=True)
# to pause a pipeline for human approval:
#
#   from google.adk.agents.base_agent import BaseAgent
#   from google.adk.events.event import Event
#   from google.adk.events.event_actions import EventActions
#   from google.genai import types
#
#   class LegalApprovalGate(BaseAgent):
#       async def _run_async_impl(self, ctx):
#           if ctx.session.state.get("liability_risk") == "high":
#               if not ctx.session.state.get("_gate_approved"):
#                   ctx.session.state["_gate_pending"] = True
#                   yield Event(
#                       invocation_id=ctx.invocation_id,
#                       author=self.name, branch=ctx.branch,
#                       content=types.Content(role="model",
#                           parts=[types.Part(text="Senior counsel approval required.")]),
#                       actions=EventActions(escalate=True),
#                   )
#
# This is ~25 lines of boilerplate per approval gate.

# --- FLUENT ---
from adk_fluent import Agent, Pipeline, gate

# Scenario: A legal document review pipeline where AI drafts contracts,
# but high-risk clauses require human attorney sign-off before finalization.

# gate(): pause pipeline when condition is met, wait for human approval
contract_pipeline = (
    Agent("clause_analyzer")
    .model("gemini-2.5-flash")
    .instruct("Analyze the contract clauses and assess liability risk level.")
    .outputs("liability_risk")
    >> gate(
        lambda s: s.get("liability_risk") == "high",
        message="High liability risk detected. Senior counsel approval required before proceeding.",
    )
    >> Agent("contract_finalizer").model("gemini-2.5-flash").instruct("Finalize the contract with approved terms.")
)

# Custom gate key for tracking specific approval states
compliance_review = (
    Agent("compliance_checker").model("gemini-2.5-flash").instruct("Check regulatory compliance of the proposed terms.")
    >> gate(
        lambda s: True,
        message="Compliance officer must review before filing.",
        gate_key="_compliance_gate",
    )
    >> Agent("filing_agent")
    .model("gemini-2.5-flash")
    .instruct("File the approved documents with the regulatory authority.")
)

# Multiple gates in a pipeline -- multi-stage legal review
multi_stage_review = (
    Agent("contract_drafter").model("gemini-2.5-flash").instruct("Draft the merger agreement based on term sheet.")
    >> gate(
        lambda s: s.get("deal_value_usd", 0) > 10_000_000,
        message="Deal exceeds $10M threshold. Board approval required.",
    )
    >> Agent("risk_disclosures")
    .model("gemini-2.5-flash")
    .instruct("Generate required risk disclosures for the agreement.")
    >> gate(
        lambda s: s.get("cross_border") == "yes",
        message="Cross-border deal requires international counsel sign-off.",
    )
)

# --- ASSERT ---
from adk_fluent._base import _GateBuilder, BuilderBase

# gate() creates a _GateBuilder
g = gate(lambda s: True, message="Test")
assert isinstance(g, _GateBuilder)
assert isinstance(g, BuilderBase)

# Stores predicate and message
assert g._message == "Test"

# Default message when none specified
g_default = gate(lambda s: True)
assert g_default._message == "Approval required"

# Custom gate key
g_custom = gate(lambda s: True, gate_key="_compliance_gate")
assert g_custom._gate_key == "_compliance_gate"

# Auto-generated gate key
g_auto = gate(lambda s: True)
assert g_auto._gate_key.startswith("_gate_")

# Builds as BaseAgent (implements _run_async_impl)
built = g.build()
assert hasattr(built, "_run_async_impl")

# Composable in pipeline
assert isinstance(contract_pipeline, Pipeline)
built_pipeline = contract_pipeline.build()
assert len(built_pipeline.sub_agents) == 3
