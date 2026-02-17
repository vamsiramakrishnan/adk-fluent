"""Dict >> Routing Shorthand"""

# --- NATIVE ---
# Native ADK has no concise syntax for intent-based routing.
# You'd wire up a coordinator LlmAgent with sub_agents,
# which uses LLM calls to decide routing — slow and expensive
# for deterministic decisions.

# --- FLUENT ---
from adk_fluent import Agent, Pipeline

# Step 1: Classifier outputs a key to session state
classifier = (
    Agent("classify")
    .model("gemini-2.5-flash")
    .instruct("Classify the user request as 'booking', 'info', or 'complaint'.")
    .outputs("intent")  # alias for .output_key("intent")
)

# Step 2: Dict >> creates deterministic routing (zero LLM calls for routing)
booker = Agent("booker").model("gemini-2.5-flash").instruct("Book flights.")
info = Agent("info_agent").model("gemini-2.5-flash").instruct("Provide info.")
support = Agent("support").model("gemini-2.5-flash").instruct("Handle complaints.")

pipeline = classifier >> {
    "booking": booker,
    "info": info,
    "complaint": support,
}

# --- ASSERT ---
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.llm_agent import LlmAgent

# Result is a Pipeline
assert isinstance(pipeline, Pipeline)

# Pipeline has 2 steps: classifier + route agent
assert len(pipeline._lists["sub_agents"]) == 2

# The route agent is deterministic (BaseAgent, NOT LlmAgent)
route_agent = pipeline._lists["sub_agents"][1]
assert isinstance(route_agent, BaseAgent)
assert not isinstance(route_agent, LlmAgent)

# Route agent has the 3 branch agents
assert len(route_agent.sub_agents) == 3
