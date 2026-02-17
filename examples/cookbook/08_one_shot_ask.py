"""One-Shot Execution with .ask()"""

# --- NATIVE ---
# Native ADK requires 15+ lines:
#   from google.adk.agents.llm_agent import LlmAgent
#   from google.adk.runners import InMemoryRunner
#   from google.genai import types
#   import asyncio
#
#   agent = LlmAgent(name="q", model="gemini-2.5-flash", instruction="Answer concisely.")
#   runner = InMemoryRunner(agent=agent, app_name="app")
#
#   async def run():
#       session = await runner.session_service.create_session(app_name="app", user_id="u")
#       content = types.Content(role="user", parts=[types.Part(text="What is 2+2?")])
#       async for event in runner.run_async(user_id="u", session_id=session.id, new_message=content):
#           if event.content and event.content.parts:
#               return event.content.parts[0].text
#
#   result = asyncio.run(run())

# --- FLUENT ---
from adk_fluent import Agent

# One line:
# result = Agent("q").model("gemini-2.5-flash").instruct("Answer concisely.").ask("What is 2+2?")

# Builder mechanics verification (no LLM call):
builder = Agent("q").model("gemini-2.5-flash").instruct("Answer concisely.")

# --- ASSERT ---
assert hasattr(builder, "ask")
assert callable(builder.ask)
assert hasattr(builder, "ask_async")
assert callable(builder.ask_async)
