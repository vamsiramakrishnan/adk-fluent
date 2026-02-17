"""
Gate: Human-in-the-Loop Approval

Converted from cookbook example: 41_gate_approval.py

Usage:
    cd examples
    adk web gate_approval
"""

from adk_fluent import Agent, Pipeline, gate
from dotenv import load_dotenv

load_dotenv()  # loads .env from examples/ (copy .env.example -> .env)

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

root_agent = multi_gate.build()
