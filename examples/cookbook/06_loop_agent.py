"""Loop Agent"""

# --- NATIVE ---
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.loop_agent import LoopAgent

loop_native = LoopAgent(
    name="refine",
    max_iterations=3,
    sub_agents=[
        LlmAgent(name="critic", model="gemini-2.5-flash", instruction="Critique."),
        LlmAgent(name="reviser", model="gemini-2.5-flash", instruction="Revise."),
    ],
)

# --- FLUENT ---
from adk_fluent import Agent, Loop

loop_fluent = (
    Loop("refine")
    .max_iterations(3)
    .step(Agent("critic").model("gemini-2.5-flash").instruct("Critique."))
    .step(Agent("reviser").model("gemini-2.5-flash").instruct("Revise."))
    .build()
)

# --- ASSERT ---
assert type(loop_native) == type(loop_fluent)
assert loop_fluent.max_iterations == 3
assert len(loop_fluent.sub_agents) == 2
