"""Inline Testing with .test()"""

# --- NATIVE ---
# Native ADK has no inline testing. You must write separate test files
# with full Runner/Session setup for each agent test.

# --- FLUENT ---
from adk_fluent import Agent

# Chain tests directly into agent definition:
# agent = (
#     Agent("qa").model("gemini-2.5-flash")
#     .instruct("Answer math questions.")
#     .test("What is 2+2?", contains="4")
#     .test("What is 10*10?", contains="100")
#     .build()
# )

builder = Agent("qa").model("gemini-2.5-flash").instruct("Answer math.")

# --- ASSERT ---
assert hasattr(builder, "test")
assert callable(builder.test)
import inspect
sig = inspect.signature(builder.test)
assert "prompt" in sig.parameters
assert "contains" in sig.parameters
assert "matches" in sig.parameters
assert "equals" in sig.parameters
