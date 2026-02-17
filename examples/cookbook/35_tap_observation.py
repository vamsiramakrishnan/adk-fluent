"""Tap: Pure Observation Steps (No State Mutation)"""

# --- NATIVE ---
# Native ADK requires subclassing BaseAgent for a pure observation step:
from google.adk.agents.base_agent import BaseAgent as NativeBaseAgent
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent


class LogState(NativeBaseAgent):
    """Custom agent just to print state without modifying it."""
    async def _run_async_impl(self, ctx):
        print(dict(ctx.session.state))
        # yield nothing -- pure observation


researcher = LlmAgent(name="researcher", model="gemini-2.5-flash", instruction="Research.")
logger = LogState(name="logger")
writer = LlmAgent(name="writer", model="gemini-2.5-flash", instruction="Write.")

pipeline_native = SequentialAgent(
    name="pipeline", sub_agents=[researcher, logger, writer]
)

# --- FLUENT ---
from adk_fluent import Agent, Pipeline, tap

# tap(): creates a pure observation step -- reads state, never mutates
# Perfect for logging, metrics, debugging
pipeline_fluent = (
    Agent("researcher").model("gemini-2.5-flash").instruct("Research.")
    >> tap(lambda s: print("State after research:", s))
    >> Agent("writer").model("gemini-2.5-flash").instruct("Write.")
)

# Named functions keep their name
def log_draft(state):
    print(f"Draft length: {len(state.get('draft', ''))}")

pipeline_with_named_tap = (
    Agent("writer").model("gemini-2.5-flash").instruct("Write a draft.")
    >> tap(log_draft)
    >> Agent("editor").model("gemini-2.5-flash").instruct("Edit the draft.")
)

# .tap() method on any builder -- convenience for inline chaining
pipeline_method = (
    Agent("analyzer").model("gemini-2.5-flash").instruct("Analyze.")
    .tap(lambda s: print("Analysis done"))
)

# --- ASSERT ---
from adk_fluent._base import _TapBuilder

# tap() creates a _TapBuilder
t = tap(lambda s: None)
assert isinstance(t, _TapBuilder)

# >> tap() creates a Pipeline with 3 steps
assert isinstance(pipeline_fluent, Pipeline)
built = pipeline_fluent.build()
assert len(built.sub_agents) == 3

# Named function keeps its name
named = tap(log_draft)
assert named._config["name"] == "log_draft"

# Lambda gets sanitized name
anon = tap(lambda s: None)
assert anon._config["name"].startswith("tap_")
assert anon._config["name"].isidentifier()

# .tap() method returns a Pipeline (self >> tap_step)
assert isinstance(pipeline_method, Pipeline)
