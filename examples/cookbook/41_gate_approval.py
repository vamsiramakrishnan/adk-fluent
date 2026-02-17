"""Gate: Human-in-the-Loop Approval"""

# --- NATIVE ---
# Native ADK requires a custom BaseAgent with EventActions(escalate=True)
# to pause a pipeline for human approval:
#
#   from google.adk.agents.base_agent import BaseAgent
#   from google.adk.events.event import Event
#   from google.adk.events.event_actions import EventActions
#   from google.genai import types
#
#   class ApprovalGate(BaseAgent):
#       async def _run_async_impl(self, ctx):
#           if ctx.session.state.get("risk") == "high":
#               if not ctx.session.state.get("_gate_approved"):
#                   ctx.session.state["_gate_pending"] = True
#                   yield Event(
#                       invocation_id=ctx.invocation_id,
#                       author=self.name, branch=ctx.branch,
#                       content=types.Content(role="model", parts=[types.Part(text="Approve?")]),
#                       actions=EventActions(escalate=True),
#                   )
#
# This is ~25 lines of boilerplate per gate.

# --- FLUENT ---
from adk_fluent import Agent, Pipeline, gate

# gate(): pause pipeline when condition is met, wait for human approval
# Uses ADK's escalate mechanism under the hood
pipeline = (
    Agent("analyzer").model("gemini-2.5-flash").instruct("Analyze risk.").outputs("risk")
    >> gate(lambda s: s.get("risk") == "high", message="Approve high-risk action?")
    >> Agent("executor").model("gemini-2.5-flash").instruct("Execute the action.")
)

# Custom gate key for tracking approval state
pipeline_custom = (
    Agent("a").model("gemini-2.5-flash").instruct("Step A.")
    >> gate(lambda s: True, message="Continue?", gate_key="_step_a_gate")
    >> Agent("b").model("gemini-2.5-flash").instruct("Step B.")
)

# Multiple gates in a pipeline
multi_gate = (
    Agent("draft").model("gemini-2.5-flash").instruct("Draft proposal.")
    >> gate(lambda s: s.get("sensitive") == "yes", message="Approve sensitive content?")
    >> Agent("publish").model("gemini-2.5-flash").instruct("Publish.")
    >> gate(lambda s: s.get("public") == "yes", message="Approve public release?")
)

# --- ASSERT ---
from adk_fluent._base import _GateBuilder, BuilderBase

# gate() creates a _GateBuilder
g = gate(lambda s: True, message="Test")
assert isinstance(g, _GateBuilder)
assert isinstance(g, BuilderBase)

# Stores predicate and message
assert g._message == "Test"

# Default message
g_default = gate(lambda s: True)
assert g_default._message == "Approval required"

# Custom gate key
g_custom = gate(lambda s: True, gate_key="_my_gate")
assert g_custom._gate_key == "_my_gate"

# Auto-generated gate key
g_auto = gate(lambda s: True)
assert g_auto._gate_key.startswith("_gate_")

# Builds as BaseAgent
built = g.build()
assert hasattr(built, "_run_async_impl")

# Composable in pipeline
assert isinstance(pipeline, Pipeline)
built_pipeline = pipeline.build()
assert len(built_pipeline.sub_agents) == 3
