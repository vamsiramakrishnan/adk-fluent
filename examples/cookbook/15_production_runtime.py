"""Production Runtime Setup"""

# --- NATIVE ---
# Native ADK production setup requires multiple objects:
#   from google.adk.agents.llm_agent import LlmAgent
#   from google.adk.runners import Runner
#   from google.adk.sessions.in_memory_session_service import InMemorySessionService
#
#   agent = LlmAgent(name="prod", model="gemini-2.5-flash", instruction="Production agent.")
#   session_service = InMemorySessionService()
#   runner = Runner(agent=agent, app_name="prod_app", session_service=session_service)

# --- FLUENT ---
from adk_fluent import Agent

# The fluent API reduces runtime setup too:
agent = (
    Agent("prod")
    .model("gemini-2.5-flash")
    .instruct("Production agent.")
    .describe("A production-ready agent with tools and callbacks.")
)

# --- ASSERT ---
assert agent._config["name"] == "prod"
assert agent._config["model"] == "gemini-2.5-flash"
assert agent._config["instruction"] == "Production agent."
