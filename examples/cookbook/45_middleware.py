"""Middleware"""

# --- NATIVE ---
from google.adk.agents.llm_agent import LlmAgent

# Native ADK requires implementing BasePlugin with many callbacks
agent_native = LlmAgent(
    name="a",
    model="gemini-2.5-flash",
    instruction="Help.",
)

# --- FLUENT ---
from adk_fluent import Agent, RetryMiddleware, StructuredLogMiddleware

# Built-in middleware with simple configuration
agent_fluent = (
    Agent("a")
    .model("gemini-2.5-flash")
    .instruct("Help.")
    .middleware(RetryMiddleware(max_attempts=3))
    .middleware(StructuredLogMiddleware())
)

# --- ASSERT ---
# Middleware is stored on the builder
assert hasattr(agent_fluent, "_middlewares")
assert len(agent_fluent._middlewares) == 2
assert isinstance(agent_fluent._middlewares[0], RetryMiddleware)
assert isinstance(agent_fluent._middlewares[1], StructuredLogMiddleware)

# .middleware() is available on any builder
from adk_fluent import Pipeline

p = Pipeline("p").middleware(RetryMiddleware())
assert len(p._middlewares) == 1
